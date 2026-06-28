"""Auditor pack generator.

Regulated buyers require a quarterly, signed methodology + metrics package. This builds
a self-contained markdown report covering: the gating methodology, the failure-mode
taxonomy, golden-set composition, judge calibration (TPR/TNR + Cohen's kappa), the
current baseline per axis, and the operating SLOs. Auto-generated, so it never drifts
from the code that actually runs.
"""

from __future__ import annotations

from collections import Counter

from .baseline import load_baseline
from .calibrate import calibrate
from .config import Config, load_config
from .goldenset import load_calibration, load_golden
from .taxonomy import AXES


def build_auditor_pack(cfg: Config) -> str:
    golden = load_golden(cfg.goldenset)
    calib = load_calibration(cfg.calibration_set)
    baseline = load_baseline(cfg.baseline_path) or {}
    base_axes = baseline.get("axes", {})
    cal = calibrate(cfg)

    axis_counts = Counter(a for c in golden for a in (c.axes or []))
    ooc = sum(1 for c in golden if not c.in_corpus)

    L = []
    L += [
        "# CIGate Auditor Pack",
        "",
        "_Auto-generated evaluation methodology and metrics package._",
        "",
        "## 1. Methodology",
        "",
        "Every pull request is evaluated against a versioned golden set. Each failure-mode "
        "axis is scored independently; subjective (LLM-judge) axes are **bias-corrected** "
        "(Rogan–Gladen) using the judge's measured sensitivity/specificity on a "
        "human-labeled calibration set, and reported with a confidence interval. A merge "
        "is blocked when a one-sided two-sample test concludes, at the configured "
        f"confidence ({int(100*cfg.gate.confidence_level)}%, Bonferroni-corrected across "
        f"axes), that an axis regressed by more than the tolerance "
        f"({cfg.gate.tolerance:.0%}) versus the `main` baseline. Deterministic (code) axes "
        "use an exact binomial interval (no correction needed).",
        "",
        "## 2. Failure-mode taxonomy",
        "",
        "| Axis | Evaluator | Definition |",
        "|---|---|---|",
    ]
    for a in AXES:
        L.append(f"| `{a.key}` | {a.evaluator} | {a.description} |")

    L += [
        "",
        "## 3. Golden-set composition",
        "",
        f"- Total cases: **{len(golden)}**  (out-of-corpus / abstention cases: {ooc})",
        f"- Calibration items (human-labeled): **{len(calib)}**",
        "",
        "| Axis | Cases exercising it |",
        "|---|---|",
    ]
    for a in AXES:
        L.append(f"| `{a.key}` | {axis_counts.get(a.key, 0)} |")

    L += [
        "",
        "## 4. Judge calibration (current)",
        "",
        "| Axis | TPR (sens.) | TNR (spec.) | Accuracy | Cohen's κ | Status |",
        "|---|---|---|---|---|---|",
    ]
    for a_key, d in cal["axes"].items():
        if d.get("deterministic"):
            L.append(f"| `{a_key}` | — | — | — | — | deterministic |")
        else:
            status = "⚠️ drift" if d["drift_flag"] else "ok"
            L.append(f"| `{a_key}` | {d['tpr']} | {d['tnr']} | {d['accuracy']} | "
                     f"{d['kappa']} | {status} |")

    L += [
        "",
        "_Re-calibration triggers when accuracy < 80% or κ < 0.70._",
        "",
        "## 5. Current baseline (corrected pass rate per axis)",
        "",
        "| Axis | Corrected | 95% CI | n |",
        "|---|---|---|---|",
    ]
    if base_axes:
        for a_key, d in base_axes.items():
            ci = f"[{d.get('ci_low', 0):.2f}, {d.get('ci_high', 1):.2f}]"
            L.append(f"| `{a_key}` | {d.get('corrected', '—')} | {ci} | {d.get('n', '—')} |")
    else:
        L.append("| _no baseline committed yet_ | | | |")

    L += [
        "",
        "## 6. Operating SLOs",
        "",
        "| Metric | Target |",
        "|---|---|",
        f"| Eval cost per PR (p95) | < ${cfg.budget.max_usd_per_run:.0f} |",
        "| Block rate | 5–12% |",
        "| Judge inter-rater κ | > 0.70 |",
        "| Held-out replay accuracy MoM delta | < 3 points |",
        "| Production regression escapes | < 1 / quarter |",
        "",
        "---",
        "_Signed: ____________________  Date: _____________________",
    ]
    return "\n".join(L)


def run_auditor(args) -> int:
    cfg = load_config(args.config)
    md = build_auditor_pack(cfg)
    with open(args.out, "w") as f:
        f.write(md)
    print(f"[cigate report --auditor] -> {args.out}")
    return 0
