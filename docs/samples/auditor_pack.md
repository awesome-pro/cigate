# CIGate Auditor Pack

_Auto-generated evaluation methodology and metrics package._

## 1. Methodology

Every pull request is evaluated against a versioned golden set. Each failure-mode axis is scored independently; subjective (LLM-judge) axes are **bias-corrected** (Rogan–Gladen) using the judge's measured sensitivity/specificity on a human-labeled calibration set, and reported with a confidence interval. A merge is blocked when a one-sided two-sample test concludes, at the configured confidence (95%, Bonferroni-corrected across axes), that an axis regressed by more than the tolerance (2%) versus the `main` baseline. Deterministic (code) axes use an exact binomial interval (no correction needed).

## 2. Failure-mode taxonomy

| Axis | Evaluator | Definition |
|---|---|---|
| `hallucination` | judge | Answer asserts claims not grounded in the retrieved policy/contract documents. |
| `retrieval_miss` | both | A relevant gold document was not retrieved, or the answer omits needed context. |
| `citation_error` | both | Citations are missing, malformed, or point to the wrong source vs the gold docs. |
| `refusal` | judge | Wrongly refuses an answerable question, or fails to abstain when out-of-corpus. |
| `format_violation` | code | Output violates the required answer/citation schema or formatting contract. |

## 3. Golden-set composition

- Total cases: **300**  (out-of-corpus / abstention cases: 60)
- Calibration items (human-labeled): **200**

| Axis | Cases exercising it |
|---|---|
| `hallucination` | 120 |
| `retrieval_miss` | 75 |
| `citation_error` | 105 |
| `refusal` | 70 |
| `format_violation` | 300 |

## 4. Judge calibration (current)

| Axis | TPR (sens.) | TNR (spec.) | Accuracy | Cohen's κ | Status |
|---|---|---|---|---|---|
| `format_violation` | — | — | — | — | deterministic |
| `hallucination` | 0.9315 | 0.8333 | 0.905 | 0.7604 | ok |
| `retrieval_miss` | 0.9191 | 0.8594 | 0.9 | 0.7721 | ok |
| `citation_error` | 0.9412 | 1.0 | 0.97 | 0.94 | ok |
| `refusal` | 0.9231 | 0.9545 | 0.93 | 0.8114 | ok |

_Re-calibration triggers when accuracy < 80% or κ < 0.70._

## 5. Current baseline (corrected pass rate per axis)

| Axis | Corrected | 95% CI | n |
|---|---|---|---|
| `hallucination` | 0.9893 | [0.90, 1.00] | 300 |
| `retrieval_miss` | 1.0 | [0.91, 1.00] | 300 |
| `citation_error` | 1.0 | [0.93, 1.00] | 300 |
| `refusal` | 0.9319 | [0.84, 1.00] | 300 |
| `format_violation` | 0.9892 | [0.97, 1.00] | 300 |

## 6. Operating SLOs

| Metric | Target |
|---|---|
| Eval cost per PR (p95) | < $40 |
| Block rate | 5–12% |
| Judge inter-rater κ | > 0.70 |
| Held-out replay accuracy MoM delta | < 3 points |
| Production regression escapes | < 1 / quarter |

---
_Signed: ____________________  Date: _____________________