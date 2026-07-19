<!-- cigate-report -->
## ❌ **CIGate: merge blocked** — 1 axis regression(s)

`prompt=answer_v2` · `judge=claude-sonnet-5` · `sample=40/40` · `cost=$0.39`

| | Axis | Raw judge | Corrected | 95% CI | Baseline | Δ | Verdict |
|---|---|---|---|---|---|---|---|
| 🟢 | `hallucination` | 78.8% | 78.8% | [52.5%, 96.9%] | 100.0% | -21.2 pp | ok |
| 🟢 | `retrieval_miss` | 75.8% | 74.0% | [21.0%, 100.0%] | 100.0% | -26.0 pp | ok |
| 🔴 | `citation_error` | 24.2% | 24.2% | [2.1%, 48.1%] | 93.9% | -69.7 pp | REGRESSED |
| 🟢 | `refusal` | 97.0% | 100.0% | [86.1%, 100.0%] | 100.0% | +0.0 pp | ok |
| 🟢 | `format_violation` | 100.0% | 91.6% | [80.3%, 100.0%] | 91.6% | -0.0 pp | ok |

<details><summary>Example newly-failing cases</summary>

**`citation_error`**
- `q0011` — Can you explain the dwelling coverage limit on my home insurance?
- `q0034` — How much is the comprehensive coverage deductible under my auto policy?
- `q0046` — Could you tell me the beneficiary death claim process in my life insurance plan?

</details>

<sub>Gated on the bias-corrected pass-rate CI lower bound per failure-mode axis (Rogan–Gladen + adjusted-Wald, Bonferroni across axes). 🟢 ok · 🔴 regressed · ⚪️ not gateable.</sub>