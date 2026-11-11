"""Tests for the deterministic hard cost cap -- pure math, no API calls."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from cost_tracker import PRICE_PER_MTOK, CostTracker  # noqa: E402


def test_add_computes_cost_from_real_pricing():
    tracker = CostTracker()
    cost = tracker.add({"input_tokens": 1000, "output_tokens": 500, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})
    expected = 1000 / 1_000_000 * PRICE_PER_MTOK["input_tokens"] + 500 / 1_000_000 * PRICE_PER_MTOK["output_tokens"]
    assert abs(cost - expected) < 1e-9
    assert abs(tracker.total_usd - expected) < 1e-9
    assert tracker.calls == 1


def test_add_handles_missing_and_none_usage_keys():
    tracker = CostTracker()
    tracker.add({"input_tokens": 100})  # output/cache keys absent
    tracker.add({"input_tokens": None, "output_tokens": 50})  # explicit None
    assert tracker.calls == 2
    assert tracker.total_usd > 0


def test_would_exceed_false_when_well_under_cap():
    tracker = CostTracker(cap_usd=0.20)
    assert tracker.would_exceed() is False


def test_would_exceed_true_once_near_cap():
    tracker = CostTracker(cap_usd=0.20)
    tracker.total_usd = 0.19  # within MAX_SINGLE_CALL_COST_USD (0.03) of the cap
    assert tracker.would_exceed() is True


def test_would_exceed_leaves_safety_margin_not_exact_cap():
    # Must trip BEFORE total_usd actually reaches cap_usd, since the check
    # runs before a call whose cost isn't known yet (margin = $0.03).
    tracker = CostTracker(cap_usd=0.20)
    tracker.total_usd = 0.16
    assert tracker.would_exceed() is False
    tracker.total_usd = 0.171
    assert tracker.would_exceed() is True


def test_summary_reports_cap_and_totals():
    tracker = CostTracker()
    tracker.add({"input_tokens": 1000, "output_tokens": 100})
    summary = tracker.summary()
    assert summary["calls"] == 1
    assert summary["cap_usd"] == 0.20
    assert summary["tokens"]["input_tokens"] == 1000
