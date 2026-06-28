"""Cost model and budget control.

Per-PR eval cost must be bounded (the case study targets < $40/PR). This module prices
token usage and enforces a hard per-run ceiling. The response cache (keyed by
prompt-hash + model) lives in :mod:`cigate.runner`.
"""

from __future__ import annotations

# USD per 1M tokens (input, output). Approximate 2026 list prices; configurable.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
_DEFAULT_PRICE = (3.0, 15.0)


def _rate(model: str) -> tuple[float, float]:
    for key, rate in PRICING.items():
        if key in model:
            return rate
    return _DEFAULT_PRICE


def price(model: str, input_tokens: int, output_tokens: int) -> float:
    rin, rout = _rate(model)
    return (input_tokens * rin + output_tokens * rout) / 1_000_000


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    """Tracks spend across a run and refuses to continue past the ceiling."""

    def __init__(self, max_usd_per_run: float):
        self.max_usd_per_run = max_usd_per_run
        self.spent = 0.0

    def add(self, usd: float) -> None:
        self.spent += usd
        if self.spent > self.max_usd_per_run:
            raise BudgetExceeded(
                f"per-run budget ${self.max_usd_per_run:.2f} exceeded "
                f"(spent ${self.spent:.2f})"
            )

    def remaining(self) -> float:
        return max(0.0, self.max_usd_per_run - self.spent)
