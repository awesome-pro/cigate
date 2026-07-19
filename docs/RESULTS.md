# Results - cross-provider run


- **Product under test:** OpenAI **`gpt-5.6-terra`** answers real contract/insurance questions.
- **Judge:** Anthropic **`claude-sonnet-5`** scores each answer per failure-mode axis.
- **Data:** questions and the retrieval corpus are derived from **CUAD** (Contract
  Understanding Atticus Dataset - real commercial contracts with expert clause annotations, CC BY 4.0).

Reproduce with your own keys: `cp .env.example .env` (add both keys) → `bash scripts/real_eval.sh`.
Raw outputs live alongside this file in [`docs/results/`](./results/).

---

## 1. Judge calibration vs CUAD expert labels

Before trusting the judge, we measure its bias against **166 expert-labeled CUAD items**.
This is the differentiator: the correction's confusion matrix is *measured from real bias*,
not assumed. (`docs/results/cuad_calibration_real.json`)

| Axis | n | TPR (sensitivity) | TNR (specificity) | Accuracy | Cohen's κ | Verdict |
|---|---|---|---|---|---|---|
| `hallucination` | 166 | 0.822 | 1.000 | 0.874 | **0.728** | ✅ trustworthy (κ ≥ 0.7) |
| `citation_error` | 166 | 0.696 | 1.000 | 0.831 | 0.671 | ⚠️ flagged for review |
| `refusal` | 166 | 0.575 | 1.000 | 0.693 | 0.429 | ⚠️ flagged for review |
| `retrieval_miss` | 166 | 0.021 | 0.667 | 0.301 | −0.281 | ⚠️ flagged - near-zero agreement |
| `format_violation` | - | - | - | - | - | deterministic code axis (no judge bias) |

**Read this the right way - the flags firing is the system working.** Calibration's job is to
tell you *which axes you can trust*. Here it says: the judge is reliable on `hallucination`
(κ = 0.73), and it should **not** be blindly trusted on the other axes for this dataset.
`retrieval_miss` in particular shows near-zero agreement - in a real workflow that's a red
flag to reconcile the judge rubric or the axis's label definition before gating on it, exactly
the failure mode blind LLM-judge gates miss. A naive tool that gates on the raw judge score
would have trusted all four axes equally.

---

## 2. The gate catches a real regression (and lets a safe change through)

We promote a baseline from the good answer prompt (`answer_v1`), then gate two changes: a
**degraded** prompt (`answer_v2`, drops the grounding/citation constraints) and a **safe**
re-run of the good prompt. Same product, same judge, same 40 real questions.

### ❌ Regressed build → **BLOCKED** (`docs/results/real_regressed_report.md`)

`prompt=answer_v2` · `judge=claude-sonnet-5` · `sample=40/40` · **cost = $0.39**

| Axis | Raw judge | Corrected | 95% CI | Baseline | Δ | Verdict |
|---|---|---|---|---|---|---|
| `hallucination` | 78.8% | 78.8% | [52.5%, 96.9%] | 100.0% | −21.2 pp | ok |
| `retrieval_miss` | 75.8% | 74.0% | [21.0%, 100.0%] | 100.0% | −26.0 pp | ok |
| `citation_error` | 24.2% | 24.2% | [2.1%, 48.1%] | 93.9% | **−69.7 pp** | 🔴 **REGRESSED** |
| `refusal` | 97.0% | 100.0% | [86.1%, 100.0%] | 100.0% | +0.0 pp | ok |
| `format_violation` | 100.0% | 91.6% | [80.3%, 100.0%] | 91.6% | −0.0 pp | ok |

The degraded prompt dropped citations; `citation_error`'s corrected pass rate collapsed from
**0.939 → 0.242**, and even its CI *upper* bound (0.481) sits far below baseline - a
statistically confident regression, so the merge is blocked. Note `hallucination` and
`retrieval_miss` also dropped, but their intervals are still too wide to gate on at n=40 - the
gate correctly stays silent on those rather than raising a shaky alarm.

### ✅ Safe build → **PASSES** (`docs/results/real_good_report.md`)

`prompt=answer_v1` · `judge=claude-sonnet-5` · `sample=40/40` · **cost = $0.32**

Every axis is within tolerance of baseline; no regression, merge allowed. Same pipeline, same
cost envelope - the gate simply doesn't fire on a healthy change.

---

## 3. Cost

| Item | Cost | Notes |
|---|---|---|
| Gate a PR (40 cases, regressed) | **$0.39** | per-PR cost |
| Gate a PR (40 cases, safe) | **$0.32** | per-PR cost |
| Promote baseline (one-time / periodic) | $0.61 | |
| Judge calibration vs 166 CUAD items (periodic) | ~$0.40 | run when the judge model changes |
| **Total for this whole run** | **~$1.7** | end to end |

A real PR gate costs **well under a dollar** - far inside the case study's < $40/PR target - and
runs in ~2 minutes with 8-way concurrency.

---

*Models and prices are July 2026 (`gpt-5.6-terra` = $2.50/$15 per 1M tokens; `claude-sonnet-5`
= $3/$15). Mock mode reproduces the same red/green flip offline for $0 - see `scripts/try_local.sh`.*
