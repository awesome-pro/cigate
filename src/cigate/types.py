"""Shared data contracts for CIGate.

These are the stable interfaces every other module depends on:

- ``Case``       — one golden-set example the system-under-test must answer.
- ``SUTOutput``  — what the system-under-test returns for a case (product-agnostic).
- ``AxisVerdict``— pass/fail on a single failure-mode axis, plus where it came from.
- ``CaseEval``   — the fully-evaluated result for one case.

The system-under-test (SUT) is any callable ``(question: str, **ctx) -> SUTOutput``.
CIGate never imports the product; it only speaks these types. See ``cigate/sut.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Case:
    """One golden-set example.

    ``truth_labels`` is the per-axis ground truth (True == pass). It is known for
    synthetic cases (we generate them) and for CUAD cases (derived from expert
    annotations). It powers (a) the mock judge's confusion matrix and (b) judge
    calibration. It is absent/empty for cases where no ground truth exists.
    """

    id: str
    question: str
    axes: list[str] = field(default_factory=list)          # axes this case exercises (stratification)
    gold_doc_ids: list[str] = field(default_factory=list)   # ground-truth source docs
    reference_answer: str | None = None
    in_corpus: bool = True                                  # is the question answerable from the corpus?
    truth_labels: dict[str, bool] = field(default_factory=dict)  # axis -> ground-truth pass/fail
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SUTOutput:
    """Product-agnostic output of the system-under-test for one case."""

    text: str
    citations: list[str] = field(default_factory=list)      # doc ids the answer cites
    retrieved_ids: list[str] = field(default_factory=list)  # doc ids retrieved (for retrieval_miss)
    prompt_version: str = "unknown"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class AxisVerdict:
    """Pass/fail on one axis for one case."""

    axis: str
    passed: bool
    source: str = "judge"   # "code" | "judge"
    rationale: str = ""


@dataclass
class CaseEval:
    """Fully-evaluated result for one case."""

    case_id: str
    output: SUTOutput
    verdicts: dict[str, AxisVerdict] = field(default_factory=dict)   # combined per-axis verdict
    judge_raw: dict[str, bool] = field(default_factory=dict)         # raw judge pass per axis (for correction)
    truth: dict[str, bool] = field(default_factory=dict)            # ground-truth pass per axis if known
    cost_usd: float = 0.0


@dataclass
class AxisEstimate:
    """Bias-corrected pass-rate estimate for one axis with a confidence interval."""

    axis: str
    observed_pass_rate: float        # raw judge pass rate p_obs
    corrected: float                 # Rogan-Gladen point estimate (clipped to [0,1])
    ci_low: float
    ci_high: float
    n: int                           # number of evaluated cases on this axis
    tpr: float                       # judge sensitivity used for correction
    tnr: float                       # judge specificity used for correction
    gateable: bool = True            # False if the judge is too weak / CI too wide to gate
    note: str = ""
    se: float = 0.0                  # standard error of the corrected estimate (for the drop test)


@dataclass
class AxisGateResult:
    """Per-axis gate decision vs baseline."""

    axis: str
    estimate: AxisEstimate
    baseline_corrected: float | None
    delta: float | None              # corrected - baseline_corrected
    regressed: bool
    reason: str = ""
