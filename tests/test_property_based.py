"""Stateful property-based fuzzing of the controller (agent.py's
_execute_tool) -- zero Anthropic API calls, zero cost.

Rather than hand-picking individual example scenarios (test_controller.py),
this generates many RANDOM sequences of tool calls -- including adversarial
ones a real model should never produce, but a malicious or confused one
might -- against the real portal, and checks that a small set of hard
invariants holds after every single step, no matter what sequence of calls
got there. This is the kind of fuzzing Anthropic's own engineering blog
has documented for finding edge cases example-based tests miss (see
ai-workflow/README.md for the reference). It only exercises _execute_tool and
portal_client.py directly -- it never constructs an Anthropic client or
makes a network call.

Reuses the session-scoped `browser` fixture from conftest.py rather than
opening a second sync_playwright() context (Playwright's sync API does not
support nested/concurrent contexts in one process).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import MAX_SAVE_ATTEMPTS, _ControllerState, _execute_tool  # noqa: E402
from portal_client import PortalClient  # noqa: E402

from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from conftest import URL  # noqa: E402

# Known vendor ids (V1-V6) plus deliberately invalid ones, so the fuzzer
# exercises both valid and adversarial inputs.
VENDOR_IDS = st.sampled_from(["V1", "V2", "V3", "V4", "V5", "V6", "V999", ""])
REQUEST_IDS = st.sampled_from(["R-A", "R-B"])  # small pool so collisions (duplicate testing) are likely
ADDRESS_FIELDS = st.sampled_from(["", "  ", "x", "42 Fiction Lane"])

_BROWSER = None  # set by test_controller_invariants_hold_under_fuzzing before any example runs


class ControllerStateMachine(RuleBasedStateMachine):
    """Fuzzes _execute_tool with random tool-call sequences and checks that
    the controller's hard invariants hold after every single step --
    regardless of how adversarial or malformed the input sequence is."""

    def __init__(self):
        super().__init__()
        self.page = _BROWSER.new_page()
        self.page.goto(URL)
        self.portal = PortalClient(self.page)
        self.portal.click_reset()
        self.state = _ControllerState(request_id="fuzz")

    def teardown(self):
        self.page.close()

    @rule(vendor_query=VENDOR_IDS)
    def resolve_vendor(self, vendor_query):
        if not vendor_query:
            return  # empty string fails Pydantic's min_length before reaching the controller
        _execute_tool("resolve_vendor", {"vendor_id_or_name": vendor_query}, self.portal, self.state)

    @rule(request_id=REQUEST_IDS)
    def check_existing_draft(self, request_id):
        _execute_tool("check_existing_draft", {"request_id": request_id}, self.portal, self.state)

    @rule(
        request_id=REQUEST_IDS,
        vendor_id=VENDOR_IDS,
        line1=ADDRESS_FIELDS,
        city=ADDRESS_FIELDS,
        postal_code=ADDRESS_FIELDS,
        country=ADDRESS_FIELDS,
    )
    def attempt_save(self, request_id, vendor_id, line1, city, postal_code, country):
        if not vendor_id:
            return  # empty string fails Pydantic's min_length before reaching the controller
        _execute_tool(
            "attempt_save",
            {
                "request_id": request_id,
                "vendor_id": vendor_id,
                "line1": line1,
                "city": city,
                "postal_code": postal_code,
                "country": country,
            },
            self.portal,
            self.state,
        )

    # --- Invariants checked after EVERY rule, regardless of the random
    #     sequence that preceded it -- these are the hard guarantees the
    #     controller must never violate, fuzzing or not.

    @invariant()
    def never_exceeds_the_retry_cap(self):
        assert self.state.save_attempts <= MAX_SAVE_ATTEMPTS

    @invariant()
    def never_duplicates_a_request_id(self):
        drafts = self.portal.read_drafts()
        ids = [d["request_id"] for d in drafts]
        assert len(ids) == len(set(ids)), f"duplicate draft ids found: {ids}"

    @invariant()
    def no_draft_ever_has_a_missing_field(self):
        for d in self.portal.read_drafts():
            for field in ("line1", "city", "postal_code", "country"):
                value = d["address"].get(field, "")
                assert value.strip(), f"draft {d['request_id']} has an empty {field}"

    @invariant()
    def no_draft_ever_targets_an_unresolved_vendor(self):
        # Every vendor_id on a saved draft must be one of the six known
        # portal vendors -- fuzzing with "V999" must never leave a draft
        # behind for a vendor that doesn't exist.
        for d in self.portal.read_drafts():
            assert d["vendor_id"] in {"V1", "V2", "V3", "V4", "V5", "V6"}


def test_controller_invariants_hold_under_fuzzing(browser):
    """Wraps the Hypothesis stateful TestCase in a normal pytest test function
    so it can depend on conftest's session-scoped `browser` fixture directly
    (instead of opening a second, conflicting Playwright context) and so
    pytest's unittest.TestCase auto-collection can't also pick up and run
    the generated TestCase on its own, before `browser` is ever wired in --
    pytest collects any unittest.TestCase subclass reachable from module
    globals regardless of its name, so this is kept as a local variable
    inside the function rather than a module-level one.
    """
    global _BROWSER
    _BROWSER = browser
    hypothesis_case = ControllerStateMachine.TestCase
    hypothesis_case.settings = settings(
        max_examples=25,
        stateful_step_count=10,
        deadline=None,  # real browser calls are slower than Hypothesis's default deadline
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    )
    hypothesis_case("runTest").runTest()
