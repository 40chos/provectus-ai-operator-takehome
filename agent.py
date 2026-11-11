"""Per-request Claude tool-use loop driving the bounded portal actions.

Design principle (see plan doc): the controller REPORTS signals
(ambiguity, missing fields, unknown vendor, save failure) -- it does not
pre-decide the outcome. The model reads the report and independently
decides whether to ask for clarification, retry, or finish. The
controller only HARD-VETOES actions that would violate a hard invariant
(more than one retry, resubmitting with the same missing field,
re-saving over an existing request_id) -- that is a safety backstop,
not the primary decision path.
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from anthropic import Anthropic, APIStatusError, RateLimitError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from portal_client import PortalClient

MODEL = "claude-sonnet-5"
MAX_STEPS = 10
MAX_SAVE_ATTEMPTS = 2  # = "at most one retry" (business rule -- see domain.md rule 4)

# Transport-layer retry for transient API errors (429/529), separate from and
# not counted against the business-level MAX_SAVE_ATTEMPTS above. 2026
# production guidance: exponential backoff starting ~1-2s, doubling, capped,
# plus jitter to avoid thundering-herd on shared-key retries; respect
# Retry-After when the API supplies one.
API_MAX_RETRIES = 5
API_BACKOFF_BASE_S = 1.5
API_BACKOFF_CAP_S = 30.0

# Caching the static prefix (system prompt + tool definitions) is the
# single highest-ROI production optimization for a loop like this one,
# where the same system+tools are resent on every step of every request.
# Two preconditions kept in mind: (1) SYSTEM_PROMPT below must stay fully
# static -- no run-specific values (dates, request IDs, etc.) are
# interpolated into it, which would invalidate the cache on every call;
# per-request data instead goes only into the first user message. (2) the
# system prompt must exceed the model's minimum cacheable block size,
# which it does once the rules text below is included in full.
CACHE_CONTROL = {"type": "ephemeral"}

DOMAIN_RULES = """\
Rules for this exercise (fictional, authoritative -- do not add your own):
1. The portal has six fictional vendors. Select a vendor by its exact ID or an
   unambiguous name. A partial name matching two vendors needs clarification.
2. Address line, city, postal code, and country are required nonempty fields.
   Treat postal codes as text. Only postal-address fields may change.
3. Save proposed changes as drafts. Do not change vendor IDs or names, and do
   not overwrite the original address. The same request ID must not produce
   duplicate drafts.
4. The supplied portal has a switch that fails the next save. Inspect the
   result before retrying; allow at most one retry and verify the saved draft.

Worked example: the request names "Northstar Supplies", while the portal
contains Northstar Supplies East and Northstar Supplies West. Ask for the
vendor ID and leave both records unchanged.
"""

SYSTEM_PROMPT = f"""You are an operator agent for a fictional vendor address-update portal.
You will be given one change request at a time. You must decide, step by
step, how to handle it using only the tools provided.

{DOMAIN_RULES}

Important operating rules:
- Never guess when a vendor name is ambiguous or unknown -- call finish with
  status "needs-information" or "unresolved" instead.
- Never submit a save with an empty required field -- call finish with status
  "needs-information" instead.
- If a save attempt fails, you may retry exactly once after verifying what
  happened. If the retry also fails, call finish with status "failed".
- After any successful save, verify by reading drafts before calling finish.
- If check_existing_draft reports a draft already exists for this request_id,
  do not attempt to save again -- call finish with status "duplicate" and
  leave the existing draft untouched.
- Always end by calling the "finish" tool exactly once. Do not call finish
  more than once.
"""

# --- Tool input schemas: Pydantic models are the SINGLE SOURCE OF TRUTH.
# The JSON schema sent to Claude (TOOLS, below) is generated FROM these
# models rather than hand-duplicated, so the two can never silently drift
# apart. Every tool_use the model sends is also validated against the
# matching model before _execute_tool touches anything (see run_request) --
# the provider's schema hint is not a guarantee, only a strong suggestion;
# production code must still enforce it deterministically on the way in.


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListVendorsInput(_StrictModel):
    pass


class ResolveVendorInput(_StrictModel):
    vendor_id_or_name: str = Field(min_length=1)


class CheckExistingDraftInput(_StrictModel):
    request_id: str = Field(min_length=1)


class AttemptSaveInput(_StrictModel):
    request_id: str = Field(min_length=1)
    vendor_id: str = Field(min_length=1)
    line1: str
    city: str
    postal_code: str
    country: str


class ReadDraftsInput(_StrictModel):
    pass


FinishStatus = Literal["draft", "needs-information", "unresolved", "duplicate", "failed"]


class FinishInput(_StrictModel):
    status: FinishStatus
    reason: str = Field(min_length=1)


TOOL_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "list_vendors": ListVendorsInput,
    "resolve_vendor": ResolveVendorInput,
    "check_existing_draft": CheckExistingDraftInput,
    "attempt_save": AttemptSaveInput,
    "read_drafts": ReadDraftsInput,
    "finish": FinishInput,
}

TOOL_DESCRIPTIONS = {
    "list_vendors": "List all vendors known to the portal (vendor_id and name).",
    "resolve_vendor": (
        "Resolve a vendor by exact ID or by name/partial name. Reports what "
        "was found -- a single match, multiple ambiguous matches, or no "
        "match. Does not itself decide what you should do about it."
    ),
    "check_existing_draft": "Check whether a draft already exists for a given request_id.",
    "attempt_save": (
        "Attempt to save an address-update draft. Validates required fields "
        "first and reports any problem instead of deciding for you. May be "
        "called at most twice per request (one retry)."
    ),
    "read_drafts": "Read all currently saved drafts, to verify a save succeeded.",
    "finish": "End processing of this request with a final status.",
}


def _schema_from_model(model: type[BaseModel]) -> dict:
    """Anthropic's tool input_schema wants a plain JSON-Schema object -- no
    top-level $defs/title/additionalProperties noise that Pydantic's raw
    model_json_schema() includes by default."""
    schema = model.model_json_schema()
    schema.pop("title", None)
    schema.pop("$defs", None)
    schema.pop("additionalProperties", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
    return schema


def _build_tools() -> list[dict]:
    return [
        {
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "input_schema": _schema_from_model(model),
        }
        for name, model in TOOL_INPUT_MODELS.items()
    ]


TOOLS = _build_tools()


def _create_with_retry(client: Anthropic, **kwargs):
    """Transport-layer retry for 429 (rate limit) / 529 (overloaded) errors.

    This is independent of and not counted against the domain-level
    MAX_SAVE_ATTEMPTS retry cap -- that's a business rule about how many
    times the *portal* may be asked to save; this is infrastructure
    resilience for a *transient API hiccup*, and conflating the two would
    make the business logic depend on network conditions.
    """
    last_exc: Exception = RuntimeError("unreachable: API_MAX_RETRIES must be >= 1")
    for attempt in range(API_MAX_RETRIES):
        try:
            return client.messages.create(**kwargs)
        except RateLimitError as e:
            last_exc = e
            # The SDK does not expose a parsed `retry_after` attribute; the
            # Retry-After header must be read off the raw HTTP response.
            retry_after = None
            response = getattr(e, "response", None)
            if response is not None:
                header = response.headers.get("retry-after")
                if header is not None:
                    try:
                        retry_after = float(header)
                    except ValueError:
                        retry_after = None
            delay = retry_after if retry_after else min(API_BACKOFF_BASE_S * (2 ** attempt), API_BACKOFF_CAP_S)
        except APIStatusError as e:
            if e.status_code not in (529, 503):
                raise
            last_exc = e
            delay = min(API_BACKOFF_BASE_S * (2 ** attempt), API_BACKOFF_CAP_S)
        delay += random.uniform(0, delay * 0.25)  # jitter
        time.sleep(delay)
    raise last_exc


@dataclass
class RequestOutcome:
    request_id: str
    status: str
    reason: str
    save_attempts: int
    had_failure: bool
    new_drafts: int
    transcript_path: str
    total_usage: dict


@dataclass
class _ControllerState:
    request_id: str
    save_attempts: int = 0
    had_failure: bool = False
    finished: bool = False
    drafts_before: list = field(default_factory=list)
    # Cumulative set of every missing-fields combination already reported,
    # not just the most recent one -- a model alternating between two
    # different incomplete submissions (e.g. missing country, then missing
    # city, then missing country again) must still be caught, not just an
    # immediate verbatim repeat.
    seen_missing_fields: set = field(default_factory=set)
    # The vendor_id resolved via resolve_vendor for THIS request, so a save
    # can't silently target a different vendor than what was looked up.
    resolved_vendor_id: Optional[str] = None
    # Set by _execute_tool's "finish" branch only after Pydantic validation
    # has already guaranteed `status` is one of FinishStatus's literal
    # values -- run_request no longer reads these off the raw, unvalidated
    # block.input itself.
    final_status: Optional[str] = None
    final_reason: Optional[str] = None


def _resolve_vendor(client: PortalClient, vendor_id_or_name: str) -> dict:
    vendors = client.list_vendors()
    by_id = [v for v in vendors if v["vendor_id"] == vendor_id_or_name]
    if by_id:
        original = client.select_vendor(vendor_id_or_name)
        return {"match": by_id[0], "original_address": original}

    needle = vendor_id_or_name.strip().lower()
    by_name = [v for v in vendors if needle in v["name"].lower()]
    if len(by_name) == 1:
        original = client.select_vendor(by_name[0]["vendor_id"])
        return {"match": by_name[0], "original_address": original}
    if len(by_name) > 1:
        return {"ambiguous": True, "candidates": by_name}
    return {"not_found": True}


def _missing_fields(line1: str, city: str, postal_code: str, country: str) -> list[str]:
    values = {"line1": line1, "city": city, "postal_code": postal_code, "country": country}
    return [k for k, v in values.items() if not v or not v.strip()]


@dataclass
class ToolExecutionResult:
    payload: dict
    is_error: bool = False


def _execute_tool(
    name: str,
    tool_input: dict,
    client: PortalClient,
    state: _ControllerState,
) -> ToolExecutionResult:
    # Deterministic gate #1: the provider's JSON-schema hint is not a
    # guarantee. A model can still send a missing/extra/wrong-typed field;
    # validate against the same Pydantic model the schema was generated
    # from before any tool logic runs, so a malformed call degrades into a
    # correctable error instead of a bare KeyError/TypeError crashing the
    # whole request.
    model_cls = TOOL_INPUT_MODELS.get(name)
    if model_cls is None:
        # The model invented a tool name outside TOOLS -- recoverable, not fatal.
        return ToolExecutionResult({"error": f"Unknown tool {name!r}; use only the tools provided."}, is_error=True)

    try:
        validated = model_cls.model_validate(tool_input)
    except ValidationError as e:
        return ToolExecutionResult(
            {"error": "Invalid tool input.", "details": e.errors(include_url=False, include_context=False)},
            is_error=True,
        )

    if name == "list_vendors":
        return ToolExecutionResult({"vendors": client.list_vendors()})

    if name == "resolve_vendor":
        result = _resolve_vendor(client, validated.vendor_id_or_name)
        if "match" in result:
            state.resolved_vendor_id = result["match"]["vendor_id"]
        # ambiguous/not_found are legitimate domain outcomes the model must
        # reason about (the system prompt tells it to expect and act on
        # them) -- not tool-call errors, so is_error stays False.
        return ToolExecutionResult(result)

    if name == "check_existing_draft":
        drafts = client.read_drafts()
        existing = [d for d in drafts if d["request_id"] == validated.request_id]
        return ToolExecutionResult({"exists": bool(existing), "draft": existing[0] if existing else None})

    if name == "read_drafts":
        return ToolExecutionResult({"drafts": client.read_drafts()})

    if name == "attempt_save":
        missing = _missing_fields(validated.line1, validated.city, validated.postal_code, validated.country)
        if missing:
            key = frozenset(missing)
            # Hard veto: refusing to re-submit with ANY missing-fields
            # combination already reported this request (not just the
            # immediately previous one) -- a model alternating between two
            # different incomplete submissions must still be capped, not
            # only a verbatim immediate repeat.
            if key in state.seen_missing_fields:
                return ToolExecutionResult(
                    {"reason": "Already reported a missing-fields problem for this request; call finish instead of retrying."},
                    is_error=True,
                )
            state.seen_missing_fields.add(key)
            # Caused by the model's own incomplete call -- an error the
            # model must correct, per Anthropic's tool-error convention.
            return ToolExecutionResult({"missing_fields": missing}, is_error=True)

        # Hard veto: this request_id already has a saved draft. Enforced in
        # the controller itself (not only via the check_existing_draft tool
        # the model is instructed to call first) so duplicate protection
        # does not depend on the model's own discipline -- domain rule 3
        # ("the same request ID must not produce duplicate drafts") is a
        # hard invariant, not a suggestion.
        existing = [d for d in client.read_drafts() if d["request_id"] == validated.request_id]
        if existing:
            return ToolExecutionResult(
                {
                    "reason": "A draft for this request_id already exists; call finish with status duplicate.",
                    "existing_draft": existing[0],
                },
                is_error=True,
            )

        if state.save_attempts >= MAX_SAVE_ATTEMPTS:
            return ToolExecutionResult(
                {"reason": "Maximum save attempts (1 retry) already used. Call finish."}, is_error=True
            )

        # Hard veto: the vendor_id being saved must be the one this request
        # actually resolved via resolve_vendor -- a model can't look up
        # vendor A and then save against vendor B.
        if state.resolved_vendor_id is not None and validated.vendor_id != state.resolved_vendor_id:
            return ToolExecutionResult(
                {
                    "reason": (
                        f"vendor_id {validated.vendor_id!r} does not match the vendor "
                        f"{state.resolved_vendor_id!r} resolved earlier for this request."
                    )
                },
                is_error=True,
            )

        # Controller only resolves vendor_id -> select on the page; it does not
        # decide ambiguity here (that already happened via resolve_vendor).
        addr = client.select_vendor(validated.vendor_id)
        if addr is None:
            return ToolExecutionResult(
                {"reason": "vendor_id does not exist; call finish(unresolved)."}, is_error=True
            )

        if state.resolved_vendor_id is None:
            # Model skipped resolve_vendor entirely but happened to pass a
            # valid id -- record it now so a later attempt can't switch
            # vendors mid-request either.
            state.resolved_vendor_id = validated.vendor_id

        state.save_attempts += 1
        status_text = client.fill_and_submit(
            validated.request_id, validated.line1, validated.city, validated.postal_code, validated.country
        )
        failed = "failure" in status_text.lower() or "already exists" in status_text.lower()
        if "failure" in status_text.lower():
            state.had_failure = True
        # The tool call itself succeeded -- it correctly executed a save
        # attempt and is truthfully reporting the portal's business-level
        # outcome. A business failure (simulated save failure) is NOT a
        # tool-call error: is_error stays False either way.
        return ToolExecutionResult(
            {"status_text": status_text, "attempt_number": state.save_attempts, "looked_like_failure": failed}
        )

    if name == "finish":
        state.finished = True
        state.final_status = validated.status
        state.final_reason = validated.reason
        return ToolExecutionResult({"acknowledged": True})

    raise AssertionError(f"TOOL_INPUT_MODELS and _execute_tool are out of sync for tool {name!r}")


def run_request(
    client: Anthropic,
    portal: PortalClient,
    request: dict,
    logs_dir: Path,
) -> RequestOutcome:
    request_id = request["request_id"]
    log_label = request.get("label", request_id)
    state = _ControllerState(request_id=request_id, drafts_before=portal.read_drafts())

    user_content = (
        f"New change request:\n{json.dumps(request, indent=2)}\n\n"
        "Decide what to do, step by step, using the tools available."
    )
    messages: list[dict] = [{"role": "user", "content": user_content}]

    transcript: list[dict] = []
    transcript_path = logs_dir / f"{log_label}.json"

    def _flush_transcript():
        # Written after every step, not only at the end -- if an exception
        # propagates out of the loop (browser crash, unexpected API error),
        # whatever reasoning happened up to that point is still on disk for
        # debugging, instead of being silently lost with the in-progress request.
        transcript_path.write_text(json.dumps(transcript, indent=2))

    for step in range(MAX_STEPS):
        t0 = time.monotonic()
        response = _create_with_retry(
            client,
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            cache_control=CACHE_CONTROL,
            messages=messages,
        )
        latency_s = round(time.monotonic() - t0, 3)
        transcript.append(
            {
                "step": step,
                "role": "assistant",
                "content": _serialize(response.content),
                "usage": response.usage.model_dump() if response.usage else None,
                "latency_s": latency_s,
            }
        )
        _flush_transcript()

        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            # model produced only text -- nudge it to use a tool
            messages.append(
                {
                    "role": "user",
                    "content": "Please proceed using one of the available tools.",
                }
            )
            continue

        tool_results = []
        for block in tool_uses:
            result = _execute_tool(block.name, block.input, portal, state)
            transcript.append(
                {
                    "step": step,
                    "role": "tool_result",
                    "tool": block.name,
                    "input": block.input,
                    "output": result.payload,
                    "is_error": result.is_error,
                }
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result.payload),
                    "is_error": result.is_error,
                }
            )

        _flush_transcript()
        messages.append({"role": "user", "content": tool_results})

        if state.finished:
            break

    drafts_after = portal.read_drafts()
    new_drafts = len(drafts_after) - len(state.drafts_before)

    final_status = state.final_status
    final_reason = state.final_reason
    if final_status is None:
        # Step budget exhausted without an explicit finish() call. Don't
        # blindly report "failed" -- check what the portal actually holds,
        # since a save can genuinely have succeeded and been verified in an
        # earlier step, with the model simply not reaching finish() in time
        # (e.g. it spent its last step re-verifying). Scoring on a false
        # "failed" when a correct draft exists would be worse than scoring
        # on an honest "step-limit-reached" outcome that still reports the
        # true new_drafts count.
        if new_drafts > 0:
            final_status = "draft"
            final_reason = (
                f"Step limit ({MAX_STEPS}) reached before the model called finish(), "
                f"but {new_drafts} draft(s) were verified saved in the portal."
            )
        else:
            final_status = "failed"
            final_reason = f"Step limit ({MAX_STEPS}) reached without calling finish() and no draft was saved."

    # final_reason is only still None here if state.final_status were set
    # without state.final_reason, which _execute_tool's "finish" branch
    # never does (both are always set together from the same validated
    # FinishInput) -- this assert documents and enforces that invariant.
    assert final_reason is not None
    _flush_transcript()

    total_usage = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    for entry in transcript:
        usage = entry.get("usage")
        if not usage:
            continue
        for key in total_usage:
            total_usage[key] += usage.get(key, 0) or 0

    return RequestOutcome(
        request_id=log_label,
        status=final_status,
        reason=final_reason,
        save_attempts=state.save_attempts,
        had_failure=state.had_failure,
        new_drafts=new_drafts,
        transcript_path=str(transcript_path),
        total_usage=total_usage,
    )


def _serialize(content_blocks) -> list[dict]:
    out = []
    for b in content_blocks:
        if b.type == "text":
            out.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            out.append({"type": "tool_use", "name": b.name, "input": b.input, "id": b.id})
    return out


def make_client() -> Anthropic:
    api_key = os.environ.get("MODEL_API_KEY")
    if not api_key:
        raise RuntimeError("MODEL_API_KEY not set (see .env.example)")
    return Anthropic(api_key=api_key)
