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
from typing import Optional

from anthropic import Anthropic, APIStatusError, RateLimitError

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

TOOLS = [
    {
        "name": "list_vendors",
        "description": "List all vendors known to the portal (vendor_id and name).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "resolve_vendor",
        "description": (
            "Resolve a vendor by exact ID or by name/partial name. Reports what "
            "was found -- a single match, multiple ambiguous matches, or no "
            "match. Does not itself decide what you should do about it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_id_or_name": {"type": "string"},
            },
            "required": ["vendor_id_or_name"],
        },
    },
    {
        "name": "check_existing_draft",
        "description": "Check whether a draft already exists for a given request_id.",
        "input_schema": {
            "type": "object",
            "properties": {"request_id": {"type": "string"}},
            "required": ["request_id"],
        },
    },
    {
        "name": "attempt_save",
        "description": (
            "Attempt to save an address-update draft. Validates required fields "
            "first and reports any problem instead of deciding for you. May be "
            "called at most twice per request (one retry)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "vendor_id": {"type": "string"},
                "line1": {"type": "string"},
                "city": {"type": "string"},
                "postal_code": {"type": "string"},
                "country": {"type": "string"},
            },
            "required": ["request_id", "vendor_id", "line1", "city", "postal_code", "country"],
        },
    },
    {
        "name": "read_drafts",
        "description": "Read all currently saved drafts, to verify a save succeeded.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "finish",
        "description": "End processing of this request with a final status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["draft", "needs-information", "unresolved", "duplicate", "failed"],
                },
                "reason": {"type": "string"},
            },
            "required": ["status", "reason"],
        },
    },
]


def _create_with_retry(client: Anthropic, **kwargs):
    """Transport-layer retry for 429 (rate limit) / 529 (overloaded) errors.

    This is independent of and not counted against the domain-level
    MAX_SAVE_ATTEMPTS retry cap -- that's a business rule about how many
    times the *portal* may be asked to save; this is infrastructure
    resilience for a *transient API hiccup*, and conflating the two would
    make the business logic depend on network conditions.
    """
    last_exc = None
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


def _execute_tool(
    name: str,
    tool_input: dict,
    client: PortalClient,
    state: _ControllerState,
) -> dict:
    if name == "list_vendors":
        return {"vendors": client.list_vendors()}

    if name == "resolve_vendor":
        result = _resolve_vendor(client, tool_input["vendor_id_or_name"])
        if "match" in result:
            state.resolved_vendor_id = result["match"]["vendor_id"]
        return result

    if name == "check_existing_draft":
        drafts = client.read_drafts()
        existing = [d for d in drafts if d["request_id"] == tool_input["request_id"]]
        return {"exists": bool(existing), "draft": existing[0] if existing else None}

    if name == "read_drafts":
        return {"drafts": client.read_drafts()}

    if name == "attempt_save":
        missing = _missing_fields(
            tool_input["line1"], tool_input["city"], tool_input["postal_code"], tool_input["country"]
        )
        if missing:
            key = frozenset(missing)
            # Hard veto: refusing to re-submit with ANY missing-fields
            # combination already reported this request (not just the
            # immediately previous one) -- a model alternating between two
            # different incomplete submissions must still be capped, not
            # only a verbatim immediate repeat.
            if key in state.seen_missing_fields:
                return {
                    "vetoed": True,
                    "reason": "Already reported a missing-fields problem for this request; call finish instead of retrying.",
                }
            state.seen_missing_fields.add(key)
            return {"validation_error": True, "missing_fields": missing}

        # Hard veto: this request_id already has a saved draft. Enforced in
        # the controller itself (not only via the check_existing_draft tool
        # the model is instructed to call first) so duplicate protection
        # does not depend on the model's own discipline -- domain rule 3
        # ("the same request ID must not produce duplicate drafts") is a
        # hard invariant, not a suggestion.
        existing = [d for d in client.read_drafts() if d["request_id"] == tool_input["request_id"]]
        if existing:
            return {
                "vetoed": True,
                "reason": "A draft for this request_id already exists; call finish with status duplicate.",
                "existing_draft": existing[0],
            }

        if state.save_attempts >= MAX_SAVE_ATTEMPTS:
            return {
                "vetoed": True,
                "reason": "Maximum save attempts (1 retry) already used. Call finish.",
            }

        # Hard veto: the vendor_id being saved must be the one this request
        # actually resolved via resolve_vendor -- a model can't look up
        # vendor A and then save against vendor B.
        if state.resolved_vendor_id is not None and tool_input["vendor_id"] != state.resolved_vendor_id:
            return {
                "vetoed": True,
                "reason": (
                    f"vendor_id {tool_input['vendor_id']!r} does not match the vendor "
                    f"{state.resolved_vendor_id!r} resolved earlier for this request."
                ),
            }

        # Controller only resolves vendor_id -> select on the page; it does not
        # decide ambiguity here (that already happened via resolve_vendor).
        addr = client.select_vendor(tool_input["vendor_id"])
        if addr is None:
            return {"vetoed": True, "reason": "vendor_id does not exist; call finish(unresolved)."}

        if state.resolved_vendor_id is None:
            # Model skipped resolve_vendor entirely but happened to pass a
            # valid id -- record it now so a later attempt can't switch
            # vendors mid-request either.
            state.resolved_vendor_id = tool_input["vendor_id"]

        state.save_attempts += 1
        status_text = client.fill_and_submit(
            tool_input["request_id"],
            tool_input["line1"],
            tool_input["city"],
            tool_input["postal_code"],
            tool_input["country"],
        )
        failed = "failure" in status_text.lower() or "already exists" in status_text.lower()
        if "failure" in status_text.lower():
            state.had_failure = True
        return {
            "status_text": status_text,
            "attempt_number": state.save_attempts,
            "looked_like_failure": failed,
        }

    if name == "finish":
        state.finished = True
        return {"acknowledged": True}

    raise ValueError(f"Unknown tool: {name}")


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
    messages = [{"role": "user", "content": user_content}]

    transcript = []
    final_status = None
    final_reason = None

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
                {"step": step, "role": "tool_result", "tool": block.name, "input": block.input, "output": result}
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )
            if block.name == "finish":
                final_status = block.input.get("status", "failed")
                final_reason = block.input.get("reason", "")

        messages.append({"role": "user", "content": tool_results})

        if state.finished:
            break

    drafts_after = portal.read_drafts()
    new_drafts = len(drafts_after) - len(state.drafts_before)

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

    transcript_path = logs_dir / f"{log_label}.json"
    transcript_path.write_text(json.dumps(transcript, indent=2))

    return RequestOutcome(
        request_id=log_label,
        status=final_status,
        reason=final_reason,
        save_attempts=state.save_attempts,
        had_failure=state.had_failure,
        new_drafts=new_drafts,
        transcript_path=str(transcript_path),
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
