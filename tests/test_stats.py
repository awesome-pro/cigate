"""Tests for the statistical-correction core.

The point estimates are asserted exactly; the analytic CI is frozen against the paper's
worked example; the bootstrap is cross-checked against the analytic CI at large n.
"""

from __future__ import annotations

import numpy as np
import pytest

from cigate.stats import (
    JudgeTooWeak,
    analytic_ci,
    bootstrap_ci,
    estimate_axis,
    rogan_gladen,
)


# --------------------------------------------------------------------------- #
# Point estimator — exact worked examples
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "tpr, tnr, p_obs, expected",
    [
        (0.90, 0.70, 0.78, 0.80),       # E1: recovers true 0.8
        (0.90, 0.85, 0.70, 0.7333333),  # E2: typical
        (0.80, 0.60, 0.30, 0.0),        # E3: clips low
        (0.85, 0.80, 0.95, 1.0),        # E4: clips high
    ],
)
def test_rogan_gladen_point(tpr, tnr, p_obs, expected):
    assert rogan_gladen(p_obs, tpr, tnr) == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("tpr, tnr", [(0.50, 0.50), (0.40, 0.50), (0.30, 0.30)])
def test_rogan_gladen_too_weak_raises(tpr, tnr):
    with pytest.raises(JudgeTooWeak):
        rogan_gladen(0.7, tpr, tnr)


# --------------------------------------------------------------------------- #
# Analytic CI — frozen golden from arXiv:2511.21140 worked example
# --------------------------------------------------------------------------- #
def test_analytic_ci_paper_example():
    # confidence_interval(p=0.78, q0/TNR=0.70, q1/TPR=0.90, n=1000, m0=250, m1=250, alpha=0.05)
    low, high = analytic_ci(0.78, 0.70, 0.90, n=1000, m0=250, m1=250, alpha=0.05)
    assert low == pytest.approx(0.7338, abs=2e-4)
    assert high == pytest.approx(0.8720, abs=2e-4)
    # The corrected point estimate sits inside the interval.
    assert low < rogan_gladen(0.78, 0.90, 0.70) < high


def test_analytic_ci_widens_with_confidence():
    lo90, hi90 = analytic_ci(0.78, 0.70, 0.90, 1000, 250, 250, alpha=0.10)
    lo95, hi95 = analytic_ci(0.78, 0.70, 0.90, 1000, 250, 250, alpha=0.05)
    lo99, hi99 = analytic_ci(0.78, 0.70, 0.90, 1000, 250, 250, alpha=0.01)
    assert (hi90 - lo90) < (hi95 - lo95) < (hi99 - lo99)


def test_analytic_ci_smaller_calibration_is_wider():
    wide = analytic_ci(0.78, 0.70, 0.90, 1000, 25, 25, alpha=0.05)
    tight = analytic_ci(0.78, 0.70, 0.90, 1000, 2500, 2500, alpha=0.05)
    assert (wide[1] - wide[0]) > (tight[1] - tight[0])


# --------------------------------------------------------------------------- #
# Bootstrap cross-check: agrees with analytic at large n
# --------------------------------------------------------------------------- #
def _make_calibration(tpr, tnr, m1, m0, seed=1):
    rng = np.random.default_rng(seed)
    pos = (rng.random(m1) < tpr).astype(int)            # judge pass on truly-pass
    neg = (rng.random(m0) < (1 - tnr)).astype(int)      # judge pass on truly-fail
    return pos, neg


def _make_eval(theta_true, tpr, tnr, n, seed=2):
    rng = np.random.default_rng(seed)
    truth = (rng.random(n) < theta_true).astype(int)
    pred = np.where(
        truth == 1,
        (rng.random(n) < tpr).astype(int),
        (rng.random(n) < (1 - tnr)).astype(int),
    )
    return pred


def test_bootstrap_agrees_with_analytic_large_n():
    tpr, tnr = 0.90, 0.85
    pos, neg = _make_calibration(tpr, tnr, m1=4000, m0=4000)
    eval_preds = _make_eval(0.70, tpr, tnr, n=8000)
    p = eval_preds.mean()
    a_lo, a_hi = analytic_ci(p, tnr, tpr, len(eval_preds), len(neg), len(pos), 0.05)
    b_lo, b_hi = bootstrap_ci(eval_preds, pos, neg, alpha=0.05, iterations=4000, seed=3)
    assert a_lo == pytest.approx(b_lo, abs=0.02)
    assert a_hi == pytest.approx(b_hi, abs=0.02)


# --------------------------------------------------------------------------- #
# High-level estimate_axis: recovers the true pass rate from a biased judge
# --------------------------------------------------------------------------- #
def test_estimate_axis_recovers_true_rate():
    # Asymmetric judge (high specificity, lower sensitivity) -> sizeable raw bias.
    # Expected raw p_obs = 0.55*0.75 + 0.45*0.07 = 0.444, ~0.11 below the true 0.55.
    tpr, tnr, theta_true = 0.75, 0.93, 0.55
    pos, neg = _make_calibration(tpr, tnr, m1=4000, m0=4000, seed=10)
    calib_preds = np.concatenate([pos, neg])
    calib_truth = np.concatenate([np.ones(len(pos), int), np.zeros(len(neg), int)])
    eval_preds = _make_eval(theta_true, tpr, tnr, n=8000, seed=11)

    est = estimate_axis("hallucination", eval_preds, calib_preds, calib_truth)
    assert est.gateable
    # raw observed rate is biased away from the truth...
    assert abs(est.observed_pass_rate - theta_true) > 0.05
    # ...but the corrected estimate recovers it, and the CI brackets the truth.
    assert est.corrected == pytest.approx(theta_true, abs=0.03)
    assert est.ci_low <= theta_true <= est.ci_high
    assert est.tpr == pytest.approx(tpr, abs=0.03)
    assert est.tnr == pytest.approx(tnr, abs=0.03)


def test_estimate_axis_not_gateable_when_judge_weak():
    # Judge ~ chance: TPR+TNR ~ 1 -> not gateable, no raise.
    pos, neg = _make_calibration(0.52, 0.50, m1=500, m0=500, seed=20)
    calib_preds = np.concatenate([pos, neg])
    calib_truth = np.concatenate([np.ones(len(pos), int), np.zeros(len(neg), int)])
    eval_preds = _make_eval(0.6, 0.52, 0.50, n=500, seed=21)
    est = estimate_axis("hallucination", eval_preds, calib_preds, calib_truth)
    assert not est.gateable
    assert est.note


def test_estimate_axis_handles_missing_class_and_empty():
    calib_preds = np.array([1, 1, 1])
    calib_truth = np.array([1, 1, 1])  # no negatives
    est = estimate_axis("citation_error", np.array([1, 0, 1]), calib_preds, calib_truth)
    assert not est.gateable and "class" in est.note

    empty = estimate_axis("refusal", np.array([]), calib_preds, calib_truth)
    assert not empty.gateable


# --------------------------------------------------------------------------- #
# Optional: cross-check against the `judgy` library if installed
# --------------------------------------------------------------------------- #
def test_crosscheck_judgy_if_available():
    judgy = pytest.importorskip("judgy")
    tpr, tnr = 0.90, 0.85
    pos, neg = _make_calibration(tpr, tnr, m1=2000, m0=2000, seed=30)
    eval_preds = _make_eval(0.7, tpr, tnr, n=4000, seed=31)
    # judgy: test_labels/test_preds == the *calibration* set; unlabeled_preds == evaluated set.
    test_labels = np.concatenate([np.ones(len(pos), int), np.zeros(len(neg), int)])
    test_preds = np.concatenate([pos, neg])
    theta, lo, hi = judgy.estimate_success_rate(
        test_labels=test_labels.tolist(),
        test_preds=test_preds.tolist(),
        unlabeled_preds=eval_preds.tolist(),
    )
    ours = rogan_gladen(eval_preds.mean(), tpr_hat := test_preds[test_labels == 1].mean(),
                        1 - test_preds[test_labels == 0].mean())
    assert ours == pytest.approx(theta, abs=0.02)
