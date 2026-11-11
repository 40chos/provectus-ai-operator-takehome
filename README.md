# Business UI Operator — submission

An AI agent that reads a fictional vendor-address portal and drafts address
updates for a set of change requests, handling ambiguous vendor names, missing
required fields, unknown vendors, a simulated save failure with retry, and
request-id idempotency — per `tasks/computer-use/domain.md` in the starter
pack.

See `ai-workflow/README.md` and `ai-workflow/manifest.json` for the required AI-configuration
documentation (separate graded criterion).

## How to run

```bash
cd submission
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env   # then fill in MODEL_API_KEY with your own Anthropic key
```

Run the offline test suite first (zero Anthropic API calls, zero cost --
Playwright/browser usage is free, only the Anthropic call costs money and
these tests never make one):

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Includes a stateful property-based fuzzing test (`tests/test_property_based.py`,
via Hypothesis) that generates random, including adversarial, sequences of
controller calls and checks hard invariants hold after every step -- see
`ai-workflow/README.md` for details.

Run the original 5 seed requests (this does call the Anthropic API):

```bash
python run.py
python score.py
```

Run the 5 additional hand-written cases:

```bash
python run.py --seed seed_extended.json --logs logs_extended --out extended
python score.py --report extended/run-report.json --expected expected_extended.json
```

Both commands start/stop their own local HTTP server for the portal and their
own Playwright browser — no manual steps needed. `run.py` resets the portal's
fictional drafts once at the start of each invocation.

## Rules recap (see `domain.md` for the authoritative version)

1. Select a vendor by exact ID or an unambiguous name; an ambiguous partial
   name needs clarification.
2. Address line, city, postal code, country are required nonempty fields;
   only these may change.
3. Save as drafts; never overwrite the original vendor record; the same
   request ID must never produce two drafts.
4. The portal has a one-shot "fail next save" switch — inspect the result,
   allow at most one retry, verify the saved draft afterward.

## Results

Original 5 seed requests — 5/5 pass, stable across 3 consecutive runs:

| Request | Status | Notes |
|---|---|---|
| R1 | `draft` | clean case |
| R2 | `needs-information` | "Northstar Supplies" matches 2 vendors |
| R3 | `needs-information` | postal_code empty |
| R4 | `unresolved` | V999 unknown |
| R5 | `draft` (matches `draft-after-one-retry-or-failed`) | 1 simulated failure, 1 retry, verified |

Extended cases (`seed_extended.json`) — 5/5 pass:

| Label | Status | Notes |
|---|---|---|
| X1 | `draft` | "Juniper" — unambiguous partial match |
| X2 | `needs-information` | country empty |
| X3a | `draft` | first save for request_id DUP-1 |
| X3b | `duplicate` | same request_id DUP-1 resubmitted, correctly rejected |
| X4 | `draft` | second independent fail-once/retry scenario |

Full per-request reasoning transcripts: `logs/*.json` and `logs_extended/*.json`.
`run-report.md` / `extended/run-report.md` give a one-paragraph-per-request
human summary.

## Documented ambiguity / judgment calls

- `expected-seed-results.json`'s R5 status string
  (`draft-after-one-retry-or-failed`) is a single label covering two possible
  valid outcomes (succeeds after retry, or fails after exhausting the retry).
  `score.py` maps the agent's actual terminal state onto this label rather
  than requiring an exact string match — documented inline in `score.py`.
- The portal can only simulate **one** failed save per toggle of the "fail"
  checkbox; a genuine two-consecutive-failures scenario isn't reproducible
  live against this portal, so the hard "no 3rd attempt" cap is enforced
  unconditionally in `agent.py`'s controller code rather than being exercised
  by a live double-failure (see `ai-workflow/README.md`'s limitations section).
- No other domain rule was reinterpreted; all 4 rules and the worked example
  are embedded verbatim in `agent.py`'s `SYSTEM_PROMPT`.
