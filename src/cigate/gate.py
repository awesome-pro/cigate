"""The gate: turn raw per-axis arrays into corrected estimates and a merge decision.

For each axis we compute the bias-corrected pass rate with a confidence interval, then
**block iff the CI lower bound falls more than ``tolerance`` below the baseline**. The
per-axis confidence level is tightened for multiple comparisons (Bonferroni) so running
many axes doesn't inflate the false-block rate.

A single composite score is deliberately avoided: each axis gates independently, so a
gain on one axis can never mask a regression on another.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

from . import stats
from .config import Config
from .runner import RunResult
from .taxonomy import AXIS_BY_KEY
from .types import AxisGateResult


@dataclass
class GateReport:
    results: list[AxisGateResult]
    regressed: bool
    cost_usd: float = 0.0
    meta: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "regressed": self.regressed,
            "cost_usd": round(self.cost_usd, 6),
            "meta": self.meta,
            "axes": {
                r.axis: {
                    "observed": round(r.estimate.observed_pass_rate, 4),
                    "corrected": round(r.estimate.corrected, 4),
                    "ci_low": round(r.estimate.ci_low, 4),
                    "ci_high": round(r.estimate.ci_high, 4),
                    "se": round(r.estimate.se, 4),
                    "n": r.estimate.n,
                    "tpr": round(r.estimate.tpr, 4),
                    "tnr": round(r.estimate.tnr, 4),
                    "gateable": r.estimate.gateable,
                    "baseline": None if r.baseline_corrected is None
                    else round(r.baseline_corrected, 4),
                    "delta": None if r.delta is None else round(r.delta, 4),
                    "regressed": r.regressed,
                    "reason": r.reason,
                    "note": r.estimate.note,
                }
                for r in self.results
            },
        }


def estimate_axes(run: RunResult, cfg: Config) -> dict:
    alpha = 1 - cfg.gate.confidence_level
    n_axes = max(1, len(cfg.axes))
    if cfg.gate.multiple_comparison in ("bonferroni", "bh"):
        conf_adj = 1 - alpha / n_axes
    else:
        conf_adj = cfg.gate.confidence_level

    estimates = {}
    for a in cfg.axes:
        if AXIS_BY_KEY.get(a) and AXIS_BY_KEY[a].evaluator == "code":
            # Deterministic axis: exact proportion CI, no judge-bias correction.
            estimates[a] = stats.binomial_estimate(
                a, np.array(run.eval_preds.get(a, []), dtype=int), conf_adj
            )
        else:
            estimates[a] = stats.estimate_axis(
                a,
                np.array(run.eval_preds.get(a, []), dtype=int),
                np.array(run.calib_preds.get(a, []), dtype=int),
                np.array(run.calib_truth.get(a, []), dtype=int),
                confidence_level=conf_adj,
                min_calibration_per_class=cfg.gate.min_calibration_per_class,
            )
    return estimates


def evaluate_gate(run: RunResult, cfg: Config, baseline: dict | None) -> GateReport:
    """Block iff we are confident the *drop* vs baseline exceeds the tolerance.

    Comparing the current CI lower bound to the baseline *point* would false-block any
    run whose CI is wider than the tolerance (i.e. almost every per-PR sample). Instead
    we run a one-sided two-sample test on the difference: the drop ``baseline - current``
    has standard error ``sqrt(se_cur^2 + se_base^2)``; we block only when the lower bound
    of the drop's confidence interval still exceeds the tolerance. Identical
    distributions give a drop ~0, so they never block regardless of CI width.
    """
    baseline = baseline or {}
    base_axes = baseline.get("axes", baseline)
    estimates = estimate_axes(run, cfg)
    tol = cfg.gate.tolerance

    alpha = 1 - cfg.gate.confidence_level
    n_axes = max(1, len(cfg.axes))
    alpha_adj = alpha / n_axes if cfg.gate.multiple_comparison in ("bonferroni", "bh") else alpha
    z = float(norm.ppf(1 - alpha_adj / 2))

    results: list[AxisGateResult] = []
    regressed_any = False
    for a in cfg.axes:
        est = estimates[a]
        be = base_axes.get(a) if isinstance(base_axes, dict) else None
        base = be.get("corrected") if isinstance(be, dict) else None
        base_se = float(be.get("se", 0.0)) if isinstance(be, dict) else 0.0

        if base is None:
            res = AxisGateResult(a, est, None, None, False, "no baseline (first run)")
        elif not est.gateable:
            res = AxisGateResult(a, est, base, None, False, f"not gateable: {est.note}")
        else:
            delta = est.corrected - base              # signed (negative = regression)
            drop = base - est.corrected
            drop_se = math.sqrt(est.se**2 + base_se**2)
            drop_lower = drop - z * drop_se           # conservative lower bound of the drop
            regressed = bool(drop_lower > tol)
            reason = (
                f"drop {drop:+.3f} (≥{drop_lower:.3f} at {int(100*(1-alpha_adj))}%) exceeds tol {tol:.2f}"
                if regressed else
                f"no significant regression (drop {drop:+.3f}, lower {drop_lower:.3f})"
            )
            res = AxisGateResult(a, est, base, delta, regressed, reason)
        regressed_any |= res.regressed
        results.append(res)

    return GateReport(results=results, regressed=regressed_any, cost_usd=run.cost_usd,
                      meta=run.meta)


def baseline_from_run(run: RunResult, cfg: Config) -> dict:
    """Build a baseline document from a (typically full) run — used by nightly/promote."""
    report = evaluate_gate(run, cfg, baseline=None)
    doc = report.to_json()
    doc["meta"]["is_baseline"] = True
    return doc
