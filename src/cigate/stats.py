"""Statistical correction core — the part most eval tools skip.

Raw LLM-as-judge pass rates are biased: in-domain judge accuracy is only ~75-88%, so
the judge's *observed* pass rate ``p_obs`` is a biased estimate of the *true* pass rate.
We correct it with the Rogan-Gladen estimator using the judge's measured sensitivity
(TPR) and specificity (TNR) on a human-labeled calibration set, and we gate on the
**lower bound of a confidence interval** around the corrected estimate.

Two CI methods are provided:

- :func:`analytic_ci` — adjusted-Wald delta method (Lee, Zeng et al., arXiv:2511.21140).
  Deterministic, correct ~95% coverage even with small calibration sets, and — unlike a
  naive ``judgy``-style bootstrap that holds ``p_obs`` fixed — it includes the
  ``p(1-p)/n`` sampling term from the evaluated set. This is the **default gating CI**.
- :func:`bootstrap_ci` — percentile bootstrap that resamples *both* the calibration set
  and the evaluated set. Used as an independent cross-check (they agree at large n).

References:
- M. Rogan & B. Gladen (1978), "Estimating prevalence from the results of a screening test."
- Lee, Zeng, et al. (2025), "How to Correctly Report LLM-as-a-Judge Evaluations" (arXiv:2511.21140).
- judgy: github.com/ai-evals-course/judgy (percentile bootstrap, calibration-only).
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

from .types import AxisEstimate

_EPS = 1e-9


class JudgeTooWeak(ValueError):
    """Raised when TPR + TNR <= 1 — the judge is no better than chance, so the
    Rogan-Gladen correction is undefined (division by <= 0) and we must refuse to gate."""


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


# --------------------------------------------------------------------------- #
# Point estimate
# --------------------------------------------------------------------------- #
def rogan_gladen(p_obs: float, tpr: float, tnr: float) -> float:
    """Bias-corrected true pass rate.

    ``theta = (p_obs + TNR - 1) / (TPR + TNR - 1)`` clipped to ``[0, 1]``.

    - ``tpr`` = sensitivity = P(judge says PASS | truly PASS)
    - ``tnr`` = specificity = P(judge says FAIL | truly FAIL)

    Raises :class:`JudgeTooWeak` if ``tpr + tnr <= 1``.
    """
    denom = tpr + tnr - 1.0
    if denom <= _EPS:
        raise JudgeTooWeak(
            f"TPR ({tpr:.3f}) + TNR ({tnr:.3f}) <= 1: judge no better than chance; "
            "correction undefined."
        )
    return _clip01((p_obs + tnr - 1.0) / denom)


# --------------------------------------------------------------------------- #
# Analytic CI — adjusted-Wald delta method (default gate)
# --------------------------------------------------------------------------- #
def analytic_estimate(
    p: float,
    tnr: float,
    tpr: float,
    n: int,
    m0: int,
    m1: int,
    alpha: float = 0.05,
) -> tuple[float, float, float, float]:
    """Adjusted-Wald delta-method estimate for the corrected pass rate.

    Returns ``(center, se, ci_low, ci_high)``. The ``se`` (standard error of the
    corrected estimate) is what the two-sample drop test in the gate needs.

    Combines all three uncertainty sources: ``p(1-p)/n`` (evaluated sample),
    ``q0(1-q0)/m0`` (specificity), ``q1(1-q1)/m1`` (sensitivity).
    """
    z = float(norm.ppf(1 - alpha / 2))
    z2 = z * z

    # Pseudo-count (adjusted-Wald) small-sample correction.
    p_a = (n * p + z2 / 2) / (n + z2)
    q0_a = (m0 * tnr + 1) / (m0 + 2)
    q1_a = (m1 * tpr + 1) / (m1 + 2)
    n_a = n + z2
    m0_a = m0 + 2
    m1_a = m1 + 2

    denom = q0_a + q1_a - 1.0
    if denom <= _EPS:
        raise JudgeTooWeak(
            f"Adjusted TPR+TNR-1 <= 0 (q0={q0_a:.3f}, q1={q1_a:.3f}); cannot form CI."
        )

    theta = (p_a + q0_a - 1.0) / denom
    # Ratio-estimator bias-correction term.
    dtheta = 2 * z2 * (
        -(1 - theta) * q0_a * (1 - q0_a) / m0_a + theta * q1_a * (1 - q1_a) / m1_a
    )
    var = (
        p_a * (1 - p_a) / n_a
        + (1 - theta) ** 2 * q0_a * (1 - q0_a) / m0_a
        + theta**2 * q1_a * (1 - q1_a) / m1_a
    )
    se = math.sqrt(var) / denom
    center = theta + dtheta
    return center, se, _clip01(center - z * se), _clip01(center + z * se)


def analytic_ci(
    p: float, tnr: float, tpr: float, n: int, m0: int, m1: int, alpha: float = 0.05,
) -> tuple[float, float]:
    """Adjusted-Wald delta-method CI ``(low, high)`` — see :func:`analytic_estimate`."""
    _, _, low, high = analytic_estimate(p, tnr, tpr, n, m0, m1, alpha)
    return low, high


# --------------------------------------------------------------------------- #
# Bootstrap CI — resamples BOTH sets (independent cross-check)
# --------------------------------------------------------------------------- #
def bootstrap_ci(
    eval_preds: np.ndarray,
    calib_pos_preds: np.ndarray,
    calib_neg_preds: np.ndarray,
    alpha: float = 0.05,
    iterations: int = 20000,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap CI resampling the evaluated set *and* the calibration set.

    Args:
        eval_preds:       0/1 judge predictions on the evaluated sample.
        calib_pos_preds:  0/1 judge predictions on truly-PASS calibration cases.
        calib_neg_preds:  0/1 judge predictions on truly-FAIL calibration cases.
    """
    rng = np.random.default_rng(seed)
    n = len(eval_preds)
    m1 = len(calib_pos_preds)
    m0 = len(calib_neg_preds)
    if n == 0 or m1 == 0 or m0 == 0:
        raise ValueError("bootstrap_ci needs non-empty eval set and both calibration classes.")

    samples = np.empty(iterations, dtype=float)
    k = 0
    for _ in range(iterations):
        p_b = rng.choice(eval_preds, n, replace=True).mean()
        tpr_b = rng.choice(calib_pos_preds, m1, replace=True).mean()
        tnr_b = 1.0 - rng.choice(calib_neg_preds, m0, replace=True).mean()
        denom = tpr_b + tnr_b - 1.0
        if denom <= _EPS:
            continue
        samples[k] = _clip01((p_b + tnr_b - 1.0) / denom)
        k += 1
    if k == 0:
        raise JudgeTooWeak("No valid bootstrap resamples (judge ~ chance on every draw).")
    lo, hi = np.percentile(samples[:k], [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return _clip01(float(lo)), _clip01(float(hi))


# --------------------------------------------------------------------------- #
# Deterministic (code) axes: exact proportion CI, no bias correction needed
# --------------------------------------------------------------------------- #
def binomial_estimate(
    axis: str, eval_preds: np.ndarray, confidence_level: float = 0.95
) -> AxisEstimate:
    """Agresti-Coull proportion estimate for a deterministic (code-owned) axis.

    Code checks are unbiased (TPR=TNR=1), so there is nothing to correct — the only
    uncertainty is sampling. We report an adjusted-Wald proportion interval and a
    standard error compatible with the gate's two-sample drop test.
    """
    eval_preds = np.asarray(eval_preds, dtype=int)
    n = len(eval_preds)
    if n == 0:
        return AxisEstimate(axis, 0.0, 0.0, 0.0, 1.0, 0, 1.0, 1.0,
                            gateable=False, note="no evaluated cases", se=0.0)
    k = int(eval_preds.sum())
    p = k / n
    z = float(norm.ppf(1 - (1 - confidence_level) / 2))
    n_a = n + z * z
    p_a = (k + z * z / 2) / n_a
    se = math.sqrt(p_a * (1 - p_a) / n_a)
    return AxisEstimate(
        axis=axis, observed_pass_rate=p, corrected=_clip01(p_a),
        ci_low=_clip01(p_a - z * se), ci_high=_clip01(p_a + z * se),
        n=n, tpr=1.0, tnr=1.0, gateable=True,
        note="deterministic (binomial CI, no correction)", se=se,
    )


# --------------------------------------------------------------------------- #
# High-level: estimate one axis from raw judge/truth arrays
# --------------------------------------------------------------------------- #
def estimate_axis(
    axis: str,
    eval_preds: np.ndarray,
    calib_preds: np.ndarray,
    calib_truth: np.ndarray,
    confidence_level: float = 0.95,
    min_calibration_per_class: int = 20,
    max_gateable_width: float = 0.9,
) -> AxisEstimate:
    """Corrected pass-rate estimate + CI for one axis, from raw 0/1 arrays.

    Args:
        eval_preds:   judge predictions (1=pass) on the evaluated sample for this axis.
        calib_preds:  judge predictions (1=pass) on the calibration set for this axis.
        calib_truth:  human ground truth (1=pass) on the calibration set, aligned to ``calib_preds``.

    The returned :class:`AxisEstimate` carries ``gateable=False`` (with a ``note``) when
    the judge is too weak (TPR+TNR<=1), a calibration class is missing, or the CI is so
    wide it carries no signal — the gate must then decline to block on this axis.
    """
    eval_preds = np.asarray(eval_preds, dtype=int)
    calib_preds = np.asarray(calib_preds, dtype=int)
    calib_truth = np.asarray(calib_truth, dtype=int)
    alpha = 1 - confidence_level

    n = len(eval_preds)
    pos = calib_truth == 1
    neg = calib_truth == 0
    m1, m0 = int(pos.sum()), int(neg.sum())

    if n == 0:
        return AxisEstimate(axis, 0.0, 0.0, 0.0, 1.0, 0, 0.0, 0.0,
                            gateable=False, note="no evaluated cases on this axis")
    if m1 == 0 or m0 == 0:
        return AxisEstimate(axis, float(eval_preds.mean()), 0.0, 0.0, 1.0, n, 0.0, 0.0,
                            gateable=False,
                            note=f"calibration missing a class (m1={m1}, m0={m0})")

    p_obs = float(eval_preds.mean())
    tpr = float(calib_preds[pos].mean())
    tnr = float(1.0 - calib_preds[neg].mean())

    note = ""
    if min(m0, m1) < min_calibration_per_class:
        note = f"small calibration set (m0={m0}, m1={m1}); CI may be wide. "

    try:
        corrected = rogan_gladen(p_obs, tpr, tnr)
        _, se, ci_low, ci_high = analytic_estimate(p_obs, tnr, tpr, n, m0, m1, alpha)
    except JudgeTooWeak as e:
        return AxisEstimate(axis, p_obs, 0.0, 0.0, 1.0, n, tpr, tnr,
                            gateable=False, note=str(e))

    gateable = bool((ci_high - ci_low) <= max_gateable_width)
    if not gateable:
        note += "CI too wide to gate (insufficient signal)."

    return AxisEstimate(
        axis=axis, observed_pass_rate=p_obs, corrected=corrected,
        ci_low=ci_low, ci_high=ci_high, n=n, tpr=tpr, tnr=tnr,
        gateable=gateable, note=note.strip(), se=se,
    )
