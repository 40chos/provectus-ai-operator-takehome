"""Tests for the bounded DOM-action layer against the real portal (free --
no Anthropic calls). Covers each action in isolation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from portal_client import _sanitize  # noqa: E402


def test_list_vendors_names_are_clean(portal):
    vendors = portal.list_vendors()
    assert len(vendors) == 6
    ids = {v["vendor_id"] for v in vendors}
    assert ids == {"V1", "V2", "V3", "V4", "V5", "V6"}
    # name must NOT include the "V1 — " id prefix (regression test for the
    # bug caught during manual sanity-check: option text was being used
    # verbatim instead of split).
    names = {v["name"] for v in vendors}
    assert "Cedar Office" in names
    assert not any(n.startswith("V") and "—" in n for n in names)


def test_select_vendor_valid_id_returns_original_address(portal):
    addr = portal.select_vendor("V1")
    assert addr == {"line1": "1 Example Road", "city": "Sampleton", "postal_code": "00100", "country": "Exampleland"}


def test_select_vendor_unknown_id_returns_none(portal):
    assert portal.select_vendor("V999") is None


def test_read_drafts_starts_empty_after_reset(portal):
    assert portal.read_drafts() == []


def test_fill_and_submit_creates_one_draft(portal):
    portal.select_vendor("V1")
    status = portal.fill_and_submit("T-1", "1 A St", "City", "00001", "Country")
    assert "saved" in status.lower()
    drafts = portal.read_drafts()
    assert len(drafts) == 1
    assert drafts[0]["request_id"] == "T-1"
    assert drafts[0]["vendor_id"] == "V1"


def test_duplicate_request_id_rejected_by_portal_itself(portal):
    portal.select_vendor("V1")
    portal.fill_and_submit("T-1", "1 A St", "City", "00001", "Country")
    status2 = portal.fill_and_submit("T-1", "DIFFERENT", "City2", "99999", "Country2")
    assert "already exists" in status2.lower()
    drafts = portal.read_drafts()
    assert len(drafts) == 1
    # original address must be unchanged, not overwritten by the second attempt
    assert drafts[0]["address"]["line1"] == "1 A St"


def test_fail_switch_blocks_exactly_one_save(portal):
    portal.select_vendor("V1")
    portal.set_fail_switch(True)
    status1 = portal.fill_and_submit("T-2", "1 A St", "City", "00001", "Country")
    assert "failure" in status1.lower()
    assert portal.read_drafts() == []
    # checkbox auto-unchecks after firing -- second attempt must succeed
    status2 = portal.fill_and_submit("T-2", "1 A St", "City", "00001", "Country")
    assert "saved" in status2.lower()
    assert len(portal.read_drafts()) == 1


def test_original_vendor_record_never_mutated_by_a_save(portal):
    before = portal.select_vendor("V1")
    portal.fill_and_submit("T-3", "Changed Line", "Changed City", "00000", "Changed Country")
    after = portal.select_vendor("V1")
    assert before == after


def test_sanitize_strips_invisible_and_control_chars():
    # Built via chr() rather than pasted literals so the invisible
    # characters under test are unambiguous in the test source itself.
    zero_width_space = chr(0x200B)
    bell = chr(0x07)
    dirty = f"Cedar{zero_width_space} Office{bell}"
    assert _sanitize(dirty) == "Cedar Office"


def test_sanitize_keeps_normal_whitespace():
    assert _sanitize("line one\nline two\ttabbed") == "line one\nline two\ttabbed"
