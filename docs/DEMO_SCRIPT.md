# CIGate — 2–3 minute demo script

A shot-by-shot script for a Loom / screen recording. Everything runs in deterministic
**mock mode** ($0, no API key), so the demo is fully reproducible and the PR check goes
**red then green** for free.

**Total runtime:** ~2:30. **Setup before you hit record:** clone the repo, `cd` in,
create the venv, and run `pip install -e ".[dev]"` (so install latency isn't on camera).
Have two browser tabs ready: the regression PR and the safe-change PR (created with
`scripts/demo.sh`). Use a large terminal font.

---

## ⏱ If you only watch one part (the 25-second highlight)

> **00:55 – 01:20.** Run `BUILD_FLAVOR=regressed cigate gate`, then immediately
> `BUILD_FLAVOR=good cigate gate`. Point at the two outputs side by side: same pipeline,
> same cost ($0.00), but `hallucination` and `citation_error` go **REGRESSED** on the
> first and every axis is **ok** on the second.
>
> **Say:** "Same gate, two builds. The regression is isolated to the exact two axes the
> prompt change hurt — and a clean build passes cleanly. That's the whole product:
> per-axis, bias-corrected, blocks only when it's statistically sure."

Pin this clip as the thumbnail / opening hook.

---

## Beat sheet

### 0:00 – 0:15 — Hook
**On screen:** the README title block (`🚦 CIGate — Gate your CI/CD on the confidence
interval, not the vibes`).

**Say:** "Teams shipping AI features change a prompt, and quality silently regresses on
one slice of traffic — no test goes red. In the case study this is built from, that drift
cost a $4M renewal. CIGate is a merge gate that catches it."

### 0:15 – 0:35 — The gap
**On screen:** scroll to the README section "The gap nobody fills."

**Say:** "Promptfoo, Braintrust, Langfuse, DeepEval all gate on the raw LLM-judge score.
But in-domain judge accuracy is only 75 to 88 percent — that number is biased. So you
either over-block and people route around the gate, or under-block and real regressions
ship. CIGate gates on the bias-corrected pass rate's confidence-interval lower bound — per
failure-mode axis."

### 0:35 – 0:55 — Establish the baseline
**On screen:** terminal.

```bash
cigate baseline --promote
```

**Point at:** the line `[cigate baseline] promoted full run -> .cigate/baseline.json`.

**Say:** "First I promote a known-good full run as the committed baseline. Every PR gets
compared against this."

### 0:55 – 1:20 — The money shot (red, then green) ← highlight
**On screen:** terminal, run both back to back.

```bash
BUILD_FLAVOR=regressed cigate gate     # the bad prompt change
BUILD_FLAVOR=good      cigate gate     # a safe change
```

**Point at:** in the first output, the per-axis summary lines where `hallucination` and
`citation_error` read `REGRESSED`, and `cost=$0.00 regressed=True`. Then in the second,
every axis reads `ok` and `regressed=False`.

**Say (the highlight lines):** "Same gate, two builds, both at zero dollars. The regression
is isolated to the exact two axes the change hurt — a single composite score would have
hidden it. The clean build passes."

### 1:20 – 1:45 — Why it's trustworthy
**On screen:** open `report.md` (the generated PR comment) or `docs/samples/pr_comment_regressed.md`.

**Point at:** the table columns — `Raw judge` vs `Corrected` vs `95% CI` vs `Baseline` vs
`Δ`.

**Say:** "Here's the PR comment it posts. Raw judge says 45% on hallucination; after
Rogan–Gladen bias correction and the adjusted-Wald confidence interval, we're confident
the true drop exceeds tolerance versus baseline. It's a two-sample drop test, so identical
builds never false-block — which is what makes it safe to mark as a required check."

### 1:45 – 2:10 — On a real PR
**On screen:** switch to the browser. Show the **regression PR** with the red ❌ required
check and the sticky CIGate comment, then the **safe-change PR** with the green ✅ check.

**Say:** "And this is it running for real on GitHub. The friendly-prompt PR is blocked
with a per-axis explanation; the cosmetic change merges. No API key needed — the demo CI
runs in mock mode for zero dollars."

### 2:10 – 2:30 — Close
**On screen:** back to terminal.

```bash
pytest -q          # 26 tests, all green, $0
```

**Say:** "Twenty-six tests, all green, zero cost — including a cross-check of the
confidence interval against the judgy library. Point it at your own product with one
config file. Repo's in the description — it's MIT."

**On screen:** end card with `github.com/awesome-pro/cigate`.

---

## Optional B-roll (if you want a 3:00 cut)

- `cigate calibrate` — show the judge's measured TPR/TNR and Cohen's κ per axis.
- `streamlit run dashboard/app.py` — the per-axis / calibration / live-gate dashboard
  (requires `pip install -e ".[dashboard]"`).
- `cigate report --auditor` — the generated auditor pack (methodology + metrics package).

## Quick-reference: every command in this demo

```bash
pip install -e ".[dev]"               # one-time setup (do before recording)
cigate baseline --promote             # 0:35
BUILD_FLAVOR=regressed cigate gate    # 0:55  → blocks
BUILD_FLAVOR=good      cigate gate    # 1:05  → passes
pytest -q                             # 2:10  → 26 tests, $0
# B-roll:
cigate calibrate
cigate report --auditor
streamlit run dashboard/app.py
```
