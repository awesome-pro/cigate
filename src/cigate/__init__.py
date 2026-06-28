"""CIGate — eval-gated CI/CD for AI products.

Gate merges on the confidence-interval lower bound of a bias-corrected LLM-judge
score, per failure-mode axis. The public surface is intentionally small; most users
interact via the ``cigate`` CLI or the GitHub Action.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .types import (
    AxisEstimate,
    AxisGateResult,
    AxisVerdict,
    Case,
    CaseEval,
    SUTOutput,
)

__all__ = [
    "__version__",
    "Case",
    "SUTOutput",
    "AxisVerdict",
    "CaseEval",
    "AxisEstimate",
    "AxisGateResult",
]
