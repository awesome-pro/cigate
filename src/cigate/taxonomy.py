"""Failure-mode taxonomy — the axes CIGate gates on.

The case study's central lesson: gate on *per-axis* corrected scores, never a single
composite. A composite hides regressions (a format-compliance gain can mask a
hallucination regression). Each axis below gates independently with its own
confidence interval.

``evaluator`` records who owns the axis:
- "code"  — deterministic, cheap, no LLM (schema/regex/citation/gold-doc checks)
- "judge" — subjective, needs the LLM-as-judge (and thus statistical correction)
- "both"  — a deterministic signal *and* a judge signal are combined (AND)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Axis:
    key: str
    description: str
    evaluator: str  # "code" | "judge" | "both"


AXES: list[Axis] = [
    Axis(
        "hallucination",
        "Answer asserts claims not grounded in the retrieved policy/contract documents.",
        "judge",
    ),
    Axis(
        "retrieval_miss",
        "A relevant gold document was not retrieved, or the answer omits needed context.",
        "both",
    ),
    Axis(
        "citation_error",
        "Citations are missing, malformed, or point to the wrong source vs the gold docs.",
        "both",
    ),
    Axis(
        "refusal",
        "Wrongly refuses an answerable question, or fails to abstain when out-of-corpus.",
        "judge",
    ),
    Axis(
        "format_violation",
        "Output violates the required answer/citation schema or formatting contract.",
        "code",
    ),
]

AXIS_BY_KEY: dict[str, Axis] = {a.key: a for a in AXES}
ALL_AXIS_KEYS: list[str] = [a.key for a in AXES]


def axes_for_evaluator(kind: str) -> list[str]:
    """Axis keys handled (at least in part) by the given evaluator kind ('code' or 'judge')."""
    return [a.key for a in AXES if a.evaluator == kind or a.evaluator == "both"]
