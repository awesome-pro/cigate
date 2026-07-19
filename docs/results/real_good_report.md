<!-- cigate-report -->
## ✅ **CIGate: no regression detected**

`prompt=answer_v1` · `judge=claude-sonnet-5` · `sample=40/40` · `cost=$0.32`

| | Axis | Raw judge | Corrected | 95% CI | Baseline | Δ | Verdict |
|---|---|---|---|---|---|---|---|
| 🟢 | `hallucination` | 100.0% | 100.0% | [78.3%, 100.0%] | 100.0% | +0.0 pp | ok |
| 🟢 | `retrieval_miss` | 90.0% | 100.0% | [50.0%, 100.0%] | 100.0% | +0.0 pp | ok |
| 🟢 | `citation_error` | 100.0% | 100.0% | [79.4%, 100.0%] | 93.9% | +6.1 pp | ok |
| 🟢 | `refusal` | 96.7% | 100.0% | [84.4%, 100.0%] | 100.0% | +0.0 pp | ok |
| 🟢 | `format_violation` | 100.0% | 90.9% | [78.7%, 100.0%] | 91.6% | -0.7 pp | ok |

<sub>Gated on the bias-corrected pass-rate CI lower bound per failure-mode axis (Rogan–Gladen + adjusted-Wald, Bonferroni across axes). 🟢 ok · 🔴 regressed · ⚪️ not gateable.</sub>