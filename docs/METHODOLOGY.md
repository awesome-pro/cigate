# Methodology: correcting a biased judge and gating on it

This is the core of CIGate. It explains why raw LLM-judge scores can't be gated on
directly, how we correct them, and how the gate decides to block.

## 1. The problem: the judge is a biased measurement instrument

An LLM-as-judge is a noisy classifier. On subjective, in-domain axes its accuracy is
typically **75–88%**. So its *observed* pass rate `p_obs` is a biased estimate of the
true pass rate `θ`. Concretely, with sensitivity `TPR = P(judge=pass | truly pass)` and
specificity `TNR = P(judge=fail | truly fail)`:

```
p_obs = θ · TPR + (1 − θ) · (1 − TNR)
```

Gating on `p_obs` directly conflates a real quality change with the judge's fixed bias.

## 2. The correction: Rogan–Gladen

Solving the equation above for `θ` gives the Rogan–Gladen estimator:

```
            p_obs + TNR − 1
θ̂  =  clip( ───────────────── , 0, 1 )
             TPR + TNR − 1
```

`TPR` and `TNR` are **measured**, not assumed — from a human-labeled **calibration set**
(`holdout_calibration.yaml`) that is kept separate from the golden set the bot is graded
on. In the demo's mock mode the judge's confusion matrix is configured directly so the
correction has known bias to recover; in real mode you measure it by running the judge
over the calibration set and comparing to the human labels (`cigate calibrate`).

**Guard rails.** If `TPR + TNR ≤ 1` the judge is no better than chance and the estimator
is undefined — CIGate raises and **refuses to gate** that axis rather than emit garbage.

## 3. The confidence interval: adjusted-Wald delta method

A point estimate isn't enough to gate responsibly; we need its uncertainty. CIGate uses
the analytic adjusted-Wald delta-method interval from Lee, Zeng et al.,
[*How to Correctly Report LLM-as-a-Judge Evaluations*](https://arxiv.org/abs/2511.21140)
(2025). Its variance combines **all three** sources of uncertainty:

```
            p(1−p)/n   +   (1−θ)²·q0(1−q0)/m0   +   θ²·q1(1−q1)/m1
Var(θ̂) =  ────────────────────────────────────────────────────────
                              (q0 + q1 − 1)²
```

where `n` is the evaluated-sample size, `m0`/`m1` the calibration negative/positive
counts, and `q0`/`q1` the specificity/sensitivity. A naive bootstrap that holds `p_obs`
fixed (as the `judgy` library does) **omits the `p(1−p)/n` term**; CIGate includes it,
adds a pseudo-count small-sample correction, and a ratio-bias term — giving correct ~95%
coverage even with small calibration sets.

**Validation.** `tests/test_stats.py` asserts the point estimates exactly, reproduces the
paper's worked example (`[0.7338, 0.8720]`), confirms the interval widens with confidence
level and narrows with calibration size, and **cross-checks against the `judgy`
library**. A bootstrap that resamples *both* sets is provided as an independent check.

## 4. Deterministic axes don't need correction

Code-based checks (citations, schema, retrieval) are unbiased detectors (`TPR=TNR=1`).
Running them through bias correction would be meaningless, so those axes use an exact
**Agresti–Coull** binomial proportion interval instead. Only the genuinely subjective
(judge) axes get Rogan–Gladen. *Correction is applied exactly where — and only where —
there is bias to correct.*

## 5. The gate: a two-sample drop test, not a threshold

The naive rule "block if `CI_lower < baseline − tolerance`" **false-blocks any run whose
CI is wider than the tolerance** — i.e. almost every per-PR sample, since correction
inflates variance. (The case study's literal phrasing only works at its 1,200-case
floor, where CIs are ±2pp.)

Instead CIGate runs a **one-sided, two-sample test on the difference**. The drop
`d = θ_baseline − θ_current` has standard error `√(SE_current² + SE_baseline²)`. We block
iff the lower bound of the drop's confidence interval still exceeds the tolerance:

```
block  ⇔  (θ_baseline − θ_current) − z · √(SE_cur² + SE_base²)  >  tolerance
```

- **Identical builds** give `d ≈ 0`, so the lower bound is negative → **never blocks**,
  regardless of CI width. This is what makes the gate usable on small per-PR samples.
- **Real regressions** produce a large, significant drop → **blocks**.
- `z` is **Bonferroni-corrected** across axes so running many axes doesn't inflate the
  false-block rate.

Each axis is tested **independently** — a gain on one axis can never mask a regression on
another, which a single composite score would allow.

## 6. Drift detection

`cigate calibrate` measures per-axis TPR, TNR, accuracy, and **Cohen's κ** against the
calibration set and flags drift when accuracy < 80% or κ < 0.70 — the SLI that catches a
judge silently degrading after a model upgrade. (`--perturb-judge` demonstrates it.)

## References

- M. Rogan & B. Gladen (1978). *Estimating prevalence from the results of a screening test.*
- Lee, Zeng, et al. (2025). *How to Correctly Report LLM-as-a-Judge Evaluations.* arXiv:2511.21140.
- `judgy` — github.com/ai-evals-course/judgy.
- Hamel Husain; Shreya Shankar; Eugene Yan — applied LLM evaluation.
