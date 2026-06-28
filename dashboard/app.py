"""CIGate dashboard — per-axis quality, judge calibration, and gate behavior.

Run with:  streamlit run dashboard/app.py   (requires `pip install 'cigate[dashboard]'`)

Reads the committed baseline and computes calibration live (mock mode is instant/$0).
A button runs a regressed vs. clean gate so you can see the gate fire on demand.
"""

from __future__ import annotations

import os
from collections import Counter

import pandas as pd
import streamlit as st

os.environ.setdefault("CIGATE_MOCK", "1")

from cigate.baseline import load_baseline  # noqa: E402
from cigate.calibrate import calibrate  # noqa: E402
from cigate.config import load_config  # noqa: E402
from cigate.gate import baseline_from_run, evaluate_gate  # noqa: E402
from cigate.goldenset import load_golden  # noqa: E402
from cigate.runner import run  # noqa: E402

st.set_page_config(page_title="CIGate", layout="wide")
st.title("🚦 CIGate — eval-gated CI/CD")
st.caption("Gate your CI/CD on the confidence interval, not the vibes.")

cfg = load_config(os.environ.get("CIGATE_CONFIG", "evalconfig.yaml"))

col1, col2, col3 = st.columns(3)

# ---- Golden-set composition -------------------------------------------------
golden = load_golden(cfg.goldenset)
axis_counts = Counter(a for c in golden for a in (c.axes or []))
with col1:
    st.subheader("Golden set")
    st.metric("Cases", len(golden))
    st.bar_chart(pd.DataFrame.from_dict(axis_counts, orient="index", columns=["cases"]))

# ---- Judge calibration ------------------------------------------------------
cal = calibrate(cfg)
rows = [
    {"axis": a, "TPR": d.get("tpr"), "TNR": d.get("tnr"),
     "accuracy": d.get("accuracy"), "kappa": d.get("kappa"),
     "drift": "⚠️" if d.get("drift_flag") else "ok"}
    for a, d in cal["axes"].items() if not d.get("deterministic")
]
with col2:
    st.subheader("Judge calibration")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Re-calibrate when accuracy < 80% or κ < 0.70.")

# ---- Baseline per axis ------------------------------------------------------
baseline = load_baseline(cfg.baseline_path) or {}
base_axes = baseline.get("axes", {})
with col3:
    st.subheader("Baseline (corrected)")
    if base_axes:
        df = pd.DataFrame([
            {"axis": a, "corrected": d.get("corrected"),
             "ci_low": d.get("ci_low"), "ci_high": d.get("ci_high")}
            for a, d in base_axes.items()
        ]).set_index("axis")
        st.bar_chart(df[["corrected"]])
    else:
        st.info("No baseline committed yet. Run `cigate baseline --promote`.")

# ---- Live gate demo ---------------------------------------------------------
st.divider()
st.subheader("Run the gate")
flavor = st.radio("Build flavor", ["good", "regressed"], horizontal=True)
if st.button("Evaluate this build vs baseline"):
    os.environ["BUILD_FLAVOR"] = "good"
    base = load_baseline(cfg.baseline_path) or baseline_from_run(run(cfg, fraction=1.0), cfg)
    os.environ["BUILD_FLAVOR"] = flavor
    report = evaluate_gate(run(cfg, fraction=0.5), cfg, base)

    if report.regressed:
        st.error(f"❌ Merge blocked — {sum(r.regressed for r in report.results)} axis regression(s)")
    else:
        st.success("✅ No regression — merge allowed")

    st.dataframe(pd.DataFrame([
        {"axis": r.axis, "raw": round(r.estimate.observed_pass_rate, 3),
         "corrected": round(r.estimate.corrected, 3),
         "ci_low": round(r.estimate.ci_low, 3), "ci_high": round(r.estimate.ci_high, 3),
         "baseline": None if r.baseline_corrected is None else round(r.baseline_corrected, 3),
         "verdict": "🔴 REGRESSED" if r.regressed else ("⚪️ n/a" if not r.estimate.gateable else "🟢 ok")}
        for r in report.results
    ]), hide_index=True, use_container_width=True)
