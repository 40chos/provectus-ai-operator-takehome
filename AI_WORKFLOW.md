# AI workflow used during this exercise

(This file follows the starter pack's `ai-workflow/README.template.md` structure. The
companion `manifest.json` at the repo root is the completed `manifest.template.json`.)

## Tools and models

- **Development-time coding assistant**: Claude Code (model `claude-sonnet-5`), used
  interactively for the entire build. Run in manual mode throughout -- every proposed
  diff was reviewed before being accepted, consistent with how I use it in production
  work generally (I don't run coding assistants in auto-apply mode for anything that
  touches logic, only for pure boilerplate). No other coding assistant, plugin, or
  extension was used.
- **The application's own model integration** (what is actually being assessed): the
  Anthropic Python SDK (`anthropic==2.8.0`), model `claude-sonnet-5`, called via
  `messages.create()` with `tools=` (tool-use/function-calling) in `agent.py`.
  `max_tokens=1024`. This SDK version's `messages.create()` does not expose a
  `temperature`/`top_p` parameter (confirmed via `inspect.signature()` at build time,
  not assumed) -- so the API's own default sampling behavior is used; this was not a
  deliberate choice to disable sampling control, the parameter simply isn't present in
  this SDK surface.

## Configuration files

No Claude Code skills, subagents, hooks, or MCP tool configs were created or used for
this exercise -- see `manifest.json` categories marked `not-used`. The only
exercise-specific configuration is the application's own prompt/tool definitions,
which live directly in source (`agent.py`): `SYSTEM_PROMPT` (embeds the verbatim
domain rules from `domain.md`) and `TOOLS` (the bounded tool-use schema). These are
version-controlled in this repo's git history rather than exported elsewhere, per the
template's "preserve relevant versions through Git history" guidance -- see commit log.

`.env.example` documents the one environment variable used (`MODEL_API_KEY`); `.env`
itself (containing the real key) is git-ignored and was supplied by the candidate, not
by Provectus (confirmed with the recruiter that API access is not provided for this
exercise).

## One workflow example

**Instruction given to the assistant**: "Implement the idempotency check before any
save attempt -- the portal must never produce two drafts for the same request_id."

**What it affected**: `agent.py`'s `check_existing_draft` tool and the `attempt_save`
validation path.

**How I checked the result**: the first draft implementation queried `read_drafts()`
for an existing `request_id` match only *after* a save attempt, as a post-hoc check
rather than a pre-condition -- which would have let the model attempt a save, see it
"succeed" on the portal side with a second entry, and only then notice the duplicate,
instead of preventing it. I caught this in manual code review (not via a failing test
-- the original 5 seed requests don't actually exercise this path, which is itself why
I added `seed_extended.json`'s X3a/X3b pair specifically to cover it).

**Correction made**: moved the check to run *before* any `attempt_save` call is
permitted to touch the portal, and added it as an explicit tool
(`check_existing_draft`) the model is instructed to call first for every request --
so the model's own reasoning decides to stop (not a silent controller short-circuit),
with the controller only as a backstop against a model that ignores the existing-draft
report and tries to save anyway. Verified by running `seed_extended.json`'s X3a/X3b
pair: X3a creates the draft, X3b correctly reports `status: duplicate`,
`new_drafts: 0` (see `extended/run-report.json` and `logs_extended/X3b.json`).

## Zero-cost verification (added in a later pass)

A second, independent code-review pass (a separate Claude instance, adversarial,
no shared context with the implementation) was run specifically to find issues
*without* spending any more Anthropic budget on live runs. It found three real
correctness bugs that the first paid run's 10/10 pass had not exercised:

1. **Controller-level duplicate veto was missing.** `attempt_save` relied on
   the model calling `check_existing_draft` first and/or the portal's own
   "already exists" rejection -- nothing in the controller itself blocked a
   second save for a request_id that already has a draft. Fixed: `attempt_save`
   now checks `read_drafts()` for the request_id before ever touching the
   browser, independent of what the model does.
2. **A save could target a different vendor than the one actually resolved**
   for the request -- nothing tied `attempt_save`'s `vendor_id` argument to
   whatever `resolve_vendor` had returned earlier in the same request. Fixed:
   `_ControllerState.resolved_vendor_id` is recorded and `attempt_save` is
   vetoed if the vendor_id doesn't match it.
3. **The missing-fields veto only compared against the immediately previous
   attempt**, so a model alternating between two different incomplete
   submissions (e.g. missing country, then missing city, then missing country
   again) would never trip it. Fixed: the controller now tracks the *set* of
   every missing-fields combination already reported for the request.

It also caught that the transport-retry's `Retry-After` handling read a
non-existent SDK attribute (`e.retry_after`) rather than the actual HTTP
response header, and that `MAX_STEPS` exhaustion unconditionally reported
`status: "failed"` even when a draft had genuinely been saved and verified
earlier in the same run -- both fixed (see `agent.py`).

To make these fixes (and the earlier caching/retry additions) verifiable
without re-spending API budget, a 45-test `pytest` suite was added under
`tests/`:
- `test_portal_client.py` / `test_controller.py` drive the real local portal
  through a real headless browser (Playwright is free; only the Anthropic
  call costs money) to validate every controller invariant above
  deterministically.
- `test_agent_loop.py` uses a small scripted fake Anthropic client (no
  network) to prove two things that would otherwise only be claims: that
  `cache_control`/`system`/`tools` are actually present in every outgoing
  call, and that the `MAX_STEPS` exhaustion path reports status honestly
  based on actual portal state rather than a blind default.

Run `pytest tests/ -v` from `submission/` -- zero Anthropic API calls, zero
cost, safe to run as many times as useful.

## Third pass: deterministic tool-input validation (is_error contract)

A third round of independent, slice-scoped adversarial review (four focused
reviewers -- determinism/validation, secrets/security, Playwright reliability,
observability/testing/structure -- each reviewing only its own slice so
nothing got lost to context limits) found several more real issues, since
confirmed fixed and re-tested:

- **Tool input is now Pydantic-validated, not trusted.** The provider's JSON
  schema is a strong hint, not a guarantee -- a malformed tool_use (missing
  field, wrong type, unexpected extra field) previously crashed the whole
  request with a bare `KeyError`. `agent.py:TOOL_INPUT_MODELS` is now the
  single source of truth: the JSON schema sent to Claude is *generated from*
  these Pydantic models (not hand-duplicated), and every tool_use is
  validated against the same model before any tool logic runs.
- **`is_error` is now set correctly**, per Anthropic's documented tool-error
  convention, with an explicit, reasoned distinction: `resolve_vendor`'s
  `ambiguous`/`not_found` and a genuine portal-reported save failure are NOT
  tool-call errors (the tool executed correctly and is truthfully reporting a
  domain outcome the model must reason about) -- but a Pydantic validation
  failure, an unknown tool name, or a controller veto (duplicate,
  vendor-mismatch, retry-cap) ARE.
- **`finish()`'s status is now actually enforced** against its five-value
  enum (previously an invalid status like `"done"` was silently accepted).
- **Page-derived data sanitization gap closed**: `_sanitize()` was applied to
  the vendor list and status text but NOT to `select_vendor`'s returned
  address or `read_drafts()`'s returned records -- both are now recursively
  sanitized (`portal_client._sanitize_value`).
- **Dead code removed**: an unused `snapshot()` method.
- **Server-lifecycle code deduplicated** between `run.py` and
  `tests/conftest.py` into `server_utils.py` (previously two near-identical
  copies -- a real divergence risk).
- **Run-level cost/latency rollup** added to `run-report.json`/`.md`
  (`run.py:_aggregate_usage`) -- previously only per-step usage existed, with
  nothing summing "what did this run actually cost."
- Explicitly **rejected as inappropriate for this scope** (recorded, not
  silently skipped): a dedicated secrets manager/key-rotation schedule, a CI
  workflow (the test suite depends on a sibling directory path not vendored
  into this repo), a committed mypy config (mypy was run once locally and
  real issues it found were fixed, but not wired up as a shippable gate),
  and role-based Playwright locators (this fixture's ids are already stable,
  descriptive, and fully within the candidate's control -- switching would
  add indirection for a problem this specific page doesn't have).
- Also found and fixed: one subagent in this review round ran `cat .env`
  during its own investigation, which materializes the real API key into
  that subagent's local transcript file. Flagging this transparently rather
  than hiding it; the key should be treated as exposed and rotated out of
  caution, even though the transcript never left the local machine.

Two further crash-safety fixes from this pass, not caught by tests (reasoned
through manually, since they only matter under an actual crash mid-run, which
isn't worth inducing against the real portal): transcripts are now flushed to
disk after every step rather than only once at the very end of a request, so
an exception mid-loop doesn't lose the reasoning trace up to that point; and
`run.py` now catches a per-request exception, records it as `status: "error"`,
and continues with the remaining requests, instead of one bad request
discarding every result already earned in the same batch.

## Reproduce or replay

1. From `submission/`, with a virtualenv containing `requirements.txt` installed and
   Playwright's Chromium downloaded (`python -m playwright install chromium`):
2. Put a real Anthropic key in `.env` as `MODEL_API_KEY=...` (see `.env.example`) --
   needed only to produce a *new* run; replaying saved transcripts does not need it.
3. `python run.py` — runs the original 5 seed requests, writes `run-report.json`,
   `run-report.md`, and per-request transcripts under `logs/`.
4. `python score.py` — compares `run-report.json` against the starter pack's
   `expected-seed-results.json`.
5. `python run.py --seed seed_extended.json --logs logs_extended --out extended` then
   `python score.py --report extended/run-report.json --expected expected_extended.json`
   — runs and scores the 5 additional hand-written cases.
6. **To replay without an API key**: the saved transcripts in `logs/*.json` and
   `logs_extended/*.json` are the raw tool-use traces (every assistant turn and every
   tool result) from an actual run — they can be read directly to inspect what the
   model decided and why, without re-calling the API. There is no automated "replay
   into a live browser" mode; replay here means transcript inspection, which is what
   the template's "inspect one failure" follow-up step calls for.

Both `run.py` and `score.py` start/stop their own local HTTP server (port 8766) for
the portal and manage the Playwright browser lifecycle themselves — no manual server
step required.

## Decisions and limitations

- **DOM-based tool-calling over pixel-based "computer use"**: the starter pack's
  hiring guide explicitly allows DOM-based tools for this option, and the portal is a
  plain static form with no canvas/images, so a screenshot+coordinate approach would
  add latency, cost, and flakiness for no benefit. Playwright reads the DOM directly
  (vendor dropdown options, the `#original`/`#drafts` `<pre>` blocks, the `#status`
  text) and exposes a small bounded tool API to the model, closer to an
  accessibility-tree observation than to screen pixels.
- **Controller reports, model decides**: ambiguity detection, field validation, and
  vendor lookup are all implemented in `agent.py`'s controller code, but deliberately
  as *signals* (e.g. `{"ambiguous": true, "candidates": [...]}`) rather than
  pre-computed verdicts — the model itself must read the signal and choose to call
  `finish(...)`. The controller only hard-vetoes a tool call that would violate a hard
  invariant (a 3rd save attempt, resubmitting with the same missing fields). This was
  a deliberate choice so the transcripts demonstrate actual model judgment, not just
  correct final state.
- **What I'd change with more time**: run more than one repeatability pass over each
  seed (currently verified stable across 3 consecutive runs of the original 5, and
  once over the extended set); add a genuine multi-failure scenario if the portal
  supported it (it only supports failing one save, so the "max 1 retry" cap is only
  exercised at the controller-code level, not by a live double-failure); add a small
  unit-test suite for `portal_client.py` independent of the LLM loop.
