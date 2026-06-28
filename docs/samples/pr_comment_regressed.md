<!-- cigate-report -->
## ❌ **CIGate: merge blocked** — 2 axis regression(s)

`prompt=answer_v2` · `judge=mock` · `sample=60/300` · `cost=$0.00`

| | Axis | Raw judge | Corrected | 95% CI | Baseline | Δ | Verdict |
|---|---|---|---|---|---|---|---|
| 🔴 | `hallucination` | 45.0% | 37.0% | [11.1%, 59.0%] | 98.9% | -61.9 pp | REGRESSED |
| 🟢 | `retrieval_miss` | 85.0% | 91.1% | [69.8%, 100.0%] | 100.0% | -8.9 pp | ok |
| 🔴 | `citation_error` | 61.7% | 65.5% | [47.6%, 82.3%] | 100.0% | -34.5 pp | REGRESSED |
| 🟢 | `refusal` | 71.7% | 76.5% | [55.9%, 91.9%] | 93.2% | -16.7 pp | ok |
| 🟢 | `format_violation` | 100.0% | 95.0% | [88.2%, 100.0%] | 98.9% | -3.9 pp | ok |

<details><summary>Example newly-failing cases</summary>

**`hallucination`**
- `q0006` — Can you explain the collision coverage deductible on my auto insurance?
- `q0011` — Can you explain the dwelling coverage limit on my home insurance?
- `q0021` — What is the home-based business inventory coverage for my renters insurance policy?
**`citation_error`**
- `q0006` — Can you explain the collision coverage deductible on my auto insurance?
- `q0048` — Can you explain the accidental death benefit rider on my life insurance?
- `q0059` — How much is the annual out-of-pocket maximum under my health policy?

</details>

<sub>Gated on the bias-corrected pass-rate CI lower bound per failure-mode axis (Rogan–Gladen + adjusted-Wald, Bonferroni across axes). 🟢 ok · 🔴 regressed · ⚪️ not gateable.</sub>