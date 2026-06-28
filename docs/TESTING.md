# Testing CIGate — functional verification

A step-by-step way to prove the whole project works as claimed. Everything except the
last two sections runs **offline, deterministically, for $0** (mock mode).

## 0. Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,crosscheck]"
```

---

## 1. Automated test suite ($0)

```bash
pytest -q          # expect: 28 passed
```

What it proves:
| File | Proves |
|---|---|
| `test_stats.py` | The correction math: exact Rogan–Gladen point estimates, the paper's worked CI `[0.7338, 0.8720]`, recovery of a true rate from a biased judge, and **agreement with the `judgy` library**. |
| `test_evaluators.py` | Deterministic code checks (citations, retrieval, format) pass/fail correctly. |
| `test_end_to_end.py` | The gate **blocks a regression**, **passes a clean build**, **isolates** the regressed axes, and is **deterministic**. |
| `test_cli.py` | `cigate gate --config …` parses (the contract the Action relies on). |

---

## 2. The core gate behavior (the headline)

```bash
cigate baseline --promote                              # establish a 'good' baseline (full run)

BUILD_FLAVOR=regressed cigate gate --fail-on-regression; echo "exit=$?"
#  expect: hallucination + citation_error => REGRESSED, exit=1

BUILD_FLAVOR=good      cigate gate --fail-on-regression; echo "exit=$?"
#  expect: all axes ok, exit=0
```

Then read the generated report (the same thing posted on a PR):

```bash
BUILD_FLAVOR=regressed cigate gate --out-report report.md >/dev/null
cat report.md     # per-axis table: raw judge | corrected | 95% CI | baseline | Δ | verdict
```

---

## 3. Prove the statistical claim (raw ≠ corrected)

The whole point is that we gate on the *corrected* number, not the raw judge score.

```bash
BUILD_FLAVOR=regressed cigate gate --out-summary summary.json >/dev/null
python -c "import json; d=json.load(open('summary.json'))['axes']['hallucination']; \
print('raw judge:', d['observed'], '| corrected:', d['corrected'], '| 95% CI:', (d['ci_low'], d['ci_high']))"
#  raw and corrected differ -> the bias correction is doing real work.
```

---

## 4. Determinism (reproducible CI)

```bash
BUILD_FLAVOR=regressed cigate run --out a.json >/dev/null
BUILD_FLAVOR=regressed cigate run --out b.json >/dev/null
python -c "import json;print('identical:', json.load(open('a.json'))['eval_preds']==json.load(open('b.json'))['eval_preds'])"
#  expect: identical: True
```

---

## 5. Judge calibration + drift detection

```bash
cigate calibrate                  # healthy: every judge axis kappa > 0.70, no DRIFT
cigate calibrate --perturb-judge  # simulates a degraded judge: DRIFT flags fire
```

---

## 6. Auditor pack

```bash
cigate report --auditor --out auditor_pack.md && head -40 auditor_pack.md
#  self-contained methodology + taxonomy + golden-set + calibration + SLOs
```

---

## 7. Real public data — CUAD track

Same gate, run over real commercial contracts with judge calibration derived from CUAD
expert annotations:

```bash
cigate baseline --promote --config evalconfig_cuad.yaml
cigate gate --config evalconfig_cuad.yaml
cigate calibrate --config evalconfig_cuad.yaml   # TPR/TNR/kappa over the real-label set
```

---

## 8. Real Claude mode (optional — costs API $)

The *same* pipeline, now with Claude as generator and judge:

```bash
pip install -e ".[real]"
export ANTHROPIC_API_KEY=sk-...
cigate gate --fraction 0.05            # tiny sample to keep cost trivial
#  watch the per-PR cost in the output stay well under the budget
```

---

## 9. Dashboard (optional)

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py         # per-axis quality, calibration, live gate button
```

---

## 10. Package install sanity

```bash
python -m build
python -m venv /tmp/clean && /tmp/clean/bin/pip install dist/*.whl
/tmp/clean/bin/cigate --help           # console script works from a clean install
```

---

## 11. The live demo on GitHub (the proof for visitors)

- **PR #1 (regression):** the `eval` check is **🔴 red (merge blocked)** with a per-axis
  CIGate comment. The two `test` jobs are green.
- **PR #2 (safe-change):** the `eval` check is **🟢 green**.
- Pushes to `main` run the `ci` workflow (28 tests) — green badge in the README.

> Cleanup of local scratch files: `rm -f report.md summary.json a.json b.json auditor_pack.md results.json`
