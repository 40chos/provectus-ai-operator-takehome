"""Tests for agent.py's controller logic -- the part that reports signals
and enforces hard invariants (retry cap, duplicate veto, field validation).

These exercise _execute_tool directly, simulating exactly the tool calls a
model would make, against the REAL portal (free). This validates every
controller decision path deterministically and without spending any
Anthropic API budget -- the model's own reasoning quality was already
validated by the live run transcripts in logs/ and logs_extended/ from the
earlier paid run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import MAX_SAVE_ATTEMPTS, _ControllerState, _execute_tool, _missing_fields, _resolve_vendor  # noqa: E402


def _state(request_id="T"):
    return _ControllerState(request_id=request_id)


# --- _missing_fields -------------------------------------------------

def test_missing_fields_all_present():
    assert _missing_fields("a", "b", "c", "d") == []


def test_missing_fields_detects_empty_string():
    assert _missing_fields("a", "", "c", "d") == ["city"]


def test_missing_fields_detects_whitespace_only():
    assert _missing_fields("a", "b", "   ", "d") == ["postal_code"]


def test_missing_fields_detects_multiple():
    assert set(_missing_fields("", "", "c", "d")) == {"line1", "city"}


# --- _resolve_vendor ---------------------------------------------------

def test_resolve_vendor_by_exact_id(portal):
    result = _resolve_vendor(portal, "V1")
    assert result["match"]["vendor_id"] == "V1"
    assert result["original_address"]["city"] == "Sampleton"


def test_resolve_vendor_unique_partial_name(portal):
    result = _resolve_vendor(portal, "Juniper")
    assert result["match"]["vendor_id"] == "V5"


def test_resolve_vendor_ambiguous_name_reports_both_not_one(portal):
    result = _resolve_vendor(portal, "Northstar Supplies")
    assert result.get("ambiguous") is True
    ids = {c["vendor_id"] for c in result["candidates"]}
    assert ids == {"V2", "V3"}


def test_resolve_vendor_unknown_reports_not_found(portal):
    result = _resolve_vendor(portal, "V999")
    assert result.get("not_found") is True


def test_resolve_vendor_unknown_name_reports_not_found(portal):
    result = _resolve_vendor(portal, "Totally Fictional Vendor Name")
    assert result.get("not_found") is True


# --- _execute_tool: attempt_save validation & vetoes --------------------

def test_attempt_save_reports_validation_error_for_missing_field(portal):
    state = _state()
    out = _execute_tool(
        "attempt_save",
        {"request_id": "A1", "vendor_id": "V1", "line1": "x", "city": "y", "postal_code": "", "country": "z"},
        portal,
        state,
    )
    assert out.get("validation_error") is True
    assert "postal_code" in out["missing_fields"]
    assert state.save_attempts == 0  # controller must not touch the browser at all


def test_attempt_save_vetoes_repeated_identical_missing_field(portal):
    state = _state()
    args = {"request_id": "A2", "vendor_id": "V1", "line1": "x", "city": "y", "postal_code": "", "country": "z"}
    first = _execute_tool("attempt_save", args, portal, state)
    assert first.get("validation_error") is True
    second = _execute_tool("attempt_save", args, portal, state)
    assert second.get("vetoed") is True


def test_attempt_save_vetoes_unknown_vendor(portal):
    state = _state()
    out = _execute_tool(
        "attempt_save",
        {"request_id": "A3", "vendor_id": "V999", "line1": "x", "city": "y", "postal_code": "z", "country": "w"},
        portal,
        state,
    )
    assert out.get("vetoed") is True
    assert portal.read_drafts() == []


def test_attempt_save_succeeds_and_increments_attempt_counter(portal):
    state = _state()
    out = _execute_tool(
        "attempt_save",
        {"request_id": "A4", "vendor_id": "V1", "line1": "x", "city": "y", "postal_code": "z", "country": "w"},
        portal,
        state,
    )
    assert out["attempt_number"] == 1
    assert state.save_attempts == 1
    assert len(portal.read_drafts()) == 1


def test_attempt_save_hard_cap_after_max_attempts(portal):
    state = _state()
    state.save_attempts = MAX_SAVE_ATTEMPTS  # simulate having already used up the retry
    out = _execute_tool(
        "attempt_save",
        {"request_id": "A5", "vendor_id": "V1", "line1": "x", "city": "y", "postal_code": "z", "country": "w"},
        portal,
        state,
    )
    assert out.get("vetoed") is True
    assert portal.read_drafts() == []  # the veto must happen BEFORE touching the browser


def test_fail_switch_then_retry_end_to_end_via_controller(portal):
    state = _state()
    portal.set_fail_switch(True)
    args = {"request_id": "A6", "vendor_id": "V1", "line1": "x", "city": "y", "postal_code": "z", "country": "w"}
    first = _execute_tool("attempt_save", args, portal, state)
    assert first["looked_like_failure"] is True
    assert state.had_failure is True
    second = _execute_tool("attempt_save", args, portal, state)
    assert second["looked_like_failure"] is False
    assert len(portal.read_drafts()) == 1
    assert state.save_attempts == 2


# --- _execute_tool: check_existing_draft / duplicates -------------------

def test_check_existing_draft_false_when_none_exists(portal):
    state = _state()
    out = _execute_tool("check_existing_draft", {"request_id": "NOPE"}, portal, state)
    assert out["exists"] is False


def test_check_existing_draft_true_after_a_save(portal):
    state = _state()
    _execute_tool(
        "attempt_save",
        {"request_id": "DUP-X", "vendor_id": "V1", "line1": "x", "city": "y", "postal_code": "z", "country": "w"},
        portal,
        state,
    )
    out = _execute_tool("check_existing_draft", {"request_id": "DUP-X"}, portal, state)
    assert out["exists"] is True
    assert out["draft"]["request_id"] == "DUP-X"


# --- Controller-level hard invariants that don't rely on the model's
#     discipline (i.e. still enforced even if the model skips the "correct"
#     tool-calling sequence) -------------------------------------------

def test_attempt_save_vetoes_duplicate_even_without_check_existing_draft_call(portal):
    """A model that skips check_existing_draft and goes straight to a second
    attempt_save for an already-saved request_id must still be blocked by
    the controller itself, not only by the portal's own rejection."""
    state = _state()
    args = {"request_id": "DUP-Y", "vendor_id": "V1", "line1": "x", "city": "y", "postal_code": "z", "country": "w"}
    _execute_tool("attempt_save", args, portal, state)
    assert state.save_attempts == 1

    second = _execute_tool(
        "attempt_save",
        {**args, "line1": "DIFFERENT"},
        portal,
        state,
    )
    assert second.get("vetoed") is True
    assert "already exists" in second["reason"]
    # the veto must fire BEFORE incrementing save_attempts or touching the browser again
    assert state.save_attempts == 1
    assert portal.read_drafts()[0]["address"]["line1"] == "x"  # original draft untouched


def test_attempt_save_vetoes_saving_against_a_different_vendor_than_resolved(portal):
    state = _state()
    _execute_tool("resolve_vendor", {"vendor_id_or_name": "V1"}, portal, state)
    assert state.resolved_vendor_id == "V1"

    out = _execute_tool(
        "attempt_save",
        {"request_id": "SWAP-1", "vendor_id": "V2", "line1": "x", "city": "y", "postal_code": "z", "country": "w"},
        portal,
        state,
    )
    assert out.get("vetoed") is True
    assert "V2" in out["reason"] and "V1" in out["reason"]
    assert portal.read_drafts() == []


def test_attempt_save_cumulative_missing_fields_veto_catches_alternating_combos(portal):
    """A model alternating between two different incomplete submissions
    (missing country, then missing city, then missing country again) must
    still trip the veto on the repeat, even though it's not the
    immediately-previous combination."""
    state = _state()
    base = {"request_id": "ALT-1", "vendor_id": "V1", "line1": "x", "city": "y", "postal_code": "z", "country": "w"}

    missing_country = _execute_tool("attempt_save", {**base, "country": ""}, portal, state)
    assert missing_country.get("validation_error") is True

    missing_city = _execute_tool("attempt_save", {**base, "city": ""}, portal, state)
    assert missing_city.get("validation_error") is True

    repeat_missing_country = _execute_tool("attempt_save", {**base, "country": ""}, portal, state)
    assert repeat_missing_country.get("vetoed") is True
    assert portal.read_drafts() == []
