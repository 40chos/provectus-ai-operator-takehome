"""Deterministic, code-enforced hard cost cap for a run -- not an estimate.

Every real Anthropic API call's actual usage is priced and summed here.
Before issuing the NEXT call anywhere in a run, the caller must check
`would_exceed()`; if true, the run stops immediately rather than hoping
the estimate holds. The cap is global across every request in a run, not
per-request, since the user set one hard budget for the whole batch.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# USD per 1M tokens, Claude Sonnet 5 (confirmed against current published
# Anthropic pricing, not assumed): base input/output, plus the two prompt-
# caching rates (5-minute TTL write, and cache read).
PRICE_PER_MTOK = {
    "input_tokens": 2.0,
    "output_tokens": 10.0,
    "cache_creation_input_tokens": 2.5,
    "cache_read_input_tokens": 0.2,
}

HARD_COST_CAP_USD = 0.20

# Upper bound on what a single remaining call could possibly cost, given
# max_tokens=1024 output and a generous worst-case input size for this
# small tool-calling loop -- used as a safety margin so the pre-call check
# can never be defeated by one last call pushing the total over the cap.
MAX_SINGLE_CALL_COST_USD = 0.03


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class CostTracker:
    total_usd: float = 0.0
    calls: int = 0
    cap_usd: float = HARD_COST_CAP_USD
    _per_key: dict = field(default_factory=lambda: {k: 0 for k in PRICE_PER_MTOK})

    def would_exceed(self) -> bool:
        """Call BEFORE issuing the next API request."""
        return self.total_usd + MAX_SINGLE_CALL_COST_USD > self.cap_usd

    def add(self, usage: dict) -> float:
        """Call AFTER a real API response with its actual usage dict.
        Returns the cost of this call."""
        cost = 0.0
        for key, price_per_mtok in PRICE_PER_MTOK.items():
            tokens = (usage or {}).get(key) or 0
            self._per_key[key] += tokens
            cost += tokens / 1_000_000 * price_per_mtok
        self.total_usd += cost
        self.calls += 1
        return cost

    def summary(self) -> dict:
        return {
            "total_usd": round(self.total_usd, 6),
            "calls": self.calls,
            "cap_usd": self.cap_usd,
            "tokens": dict(self._per_key),
        }
