<!-- cigate-report -->
## ✅ **CIGate: no regression detected**

`prompt=answer_v1` · `judge=mock` · `sample=60/300` · `cost=$0.00`

| | Axis | Raw judge | Corrected | 95% CI | Baseline | Δ | Verdict |
|---|---|---|---|---|---|---|---|
| 🟢 | `hallucination` | 90.0% | 95.9% | [75.3%, 100.0%] | 98.9% | -3.0 pp | ok |
| 🟢 | `retrieval_miss` | 85.0% | 91.1% | [69.8%, 100.0%] | 100.0% | -8.9 pp | ok |
| 🟢 | `citation_error` | 95.0% | 100.0% | [85.8%, 100.0%] | 100.0% | +0.0 pp | ok |
| 🟢 | `refusal` | 83.3% | 89.8% | [70.6%, 100.0%] | 93.2% | -3.4 pp | ok |
| 🟢 | `format_violation` | 100.0% | 95.0% | [88.2%, 100.0%] | 98.9% | -3.9 pp | ok |

<sub>Gated on the bias-corrected pass-rate CI lower bound per failure-mode axis (Rogan–Gladen + adjusted-Wald, Bonferroni across axes). 🟢 ok · 🔴 regressed · ⚪️ not gateable.</sub>