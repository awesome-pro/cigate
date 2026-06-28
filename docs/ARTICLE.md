# Gate your CI/CD on the confidence interval, not the vibes

*How I built CIGate: a merge gate that blocks LLM-quality regressions per failure mode, with the judge's bias statistically corrected for.*

---

## The $4M tweak nobody reviewed

The case study this project implements opens with a disaster I think every team shipping
AI features will recognize. Someone makes a well-meaning, one-line prompt change — "be
helpful and complete" — and it quietly degrades answer quality on a narrow slice of
traffic: contract questions. No test goes red. No alert fires. The LLM-judge metric on
the dashboard drifts eleven points over a few weeks and nobody is watching that number
closely enough to notice. By the time someone does, a **$4M renewal** is gone.

The thing that makes this failure mode so nasty is that prompt, retrieval, tool, and
model changes have **non-local effects**. Fixing one answer silently breaks ten others.
The industry default — ship it, watch the vibes — has no mechanism to catch that before
it reaches a customer. So I wanted a gate: a required CI check that blocks the merge when
answer quality *statistically* regresses. Hence the pun the whole project hangs on — gate
your **C**ontinuous **I**ntegration on a **C**onfidence **I**nterval.

## Why you can't just gate on the judge

The obvious move is what the popular eval tools — Promptfoo, Braintrust, Langfuse,
DeepEval — already do: run an LLM-as-judge over a golden set, compute a pass rate, and
fail the build if it drops. I tried this first. It does not work, and the reason is
quantitative, not philosophical.

In-domain LLM-judge accuracy is only about **75–88%**. The judge is itself a noisy,
*biased* classifier. So its observed pass rate is a biased estimate of the true pass
rate, and the bias does not cancel out when you compare two builds — sampling noise and
asymmetric error rates push it around run to run. Gate on that raw number and you get the
worst of both worlds:

- **Over-block.** False alarms on builds that were actually fine. Developers learn the
  gate cries wolf and start routing around it — at which point you have eval theater.
- **Under-block.** A real regression sits inside the judge's noise band and ships anyway.
  This is exactly how you lose the $4M renewal *with* an eval suite in place.

A single composite "quality score" makes it worse: a format-compliance gain can
arithmetically mask a hallucination regression in the same average. The thing you most
need to see is the thing the average hides.

## The insight: correct the bias, gate on the lower bound, per axis

The fix has three parts, and all three matter.

**1. Correct the judge's bias.** If I measure the judge's sensitivity (TPR) and
specificity (TNR) on a small human-labeled calibration set, I can recover the true pass
rate from the observed one with the **Rogan–Gladen** estimator — a classic trick from
epidemiology for backing out true prevalence from an imperfect screening test:

```
            p_obs + TNR − 1
θ̂  =  clip( ───────────────── , 0, 1 )
             TPR + TNR − 1
```

**2. Gate on a confidence-interval lower bound, not a point.** A corrected point estimate
is still an estimate. I put a confidence interval around it using the **adjusted-Wald
delta method** from Lee, Zeng et al. ([arXiv:2511.21140](https://arxiv.org/abs/2511.21140)),
which combines all three sources of uncertainty — the evaluated sample, the measured
sensitivity, and the measured specificity — with correct ~95% coverage even on small
calibration sets. If the judge is no better than chance (`TPR + TNR ≤ 1`) or the interval
is too wide to carry signal, CIGate **refuses to gate that axis** rather than guess.

**3. Do it per failure-mode axis.** Never one composite. `hallucination`,
`retrieval_miss`, `citation_error`, `refusal`, and `format_violation` each gate
independently, so a win on one axis can never paper over a regression on another.

That's the whole thesis. It's also precisely the part the case study makes its centerpiece
and the mainstream tools skip.

## What it looks like on a PR

Here's the demo regression. A one-line change ships `answer_v2` ("be helpful and complete,
citations optional"), dropping the strict-grounding and mandatory-citation instructions.
CIGate runs on the PR and posts this, then **blocks the merge**:

> ### ❌ CIGate: merge blocked — 2 axis regression(s)
> `prompt=answer_v2` · `judge=mock` · `sample=60/300` · `cost=$0.00`
>
> | | Axis | Raw judge | Corrected | 95% CI | Baseline | Δ | Verdict |
> |---|---|---|---|---|---|---|---|
> | 🔴 | `hallucination` | 45.0% | 37.0% | [11.1%, 59.0%] | 98.9% | −61.9 pp | REGRESSED |
> | 🟢 | `retrieval_miss` | 85.0% | 91.1% | [69.8%, 100%] | 100% | −8.9 pp | ok |
> | 🔴 | `citation_error` | 61.7% | 65.5% | [47.6%, 82.3%] | 100% | −34.5 pp | REGRESSED |
> | 🟢 | `refusal` | 71.7% | 76.5% | [55.9%, 91.9%] | 93.2% | −16.7 pp | ok |
> | 🟢 | `format_violation` | 100% | 95.0% | [88.2%, 100%] | 98.9% | −3.9 pp | ok |

The regression is **isolated to the two axes the change actually hurt**. A composite score
would have averaged it away. A clean change goes green and merges — the gate's job is to
catch regressions, not to block every PR.

## How CIGate implements it

The pipeline is deliberately small. On each PR it:

1. **Samples** the golden set, stratified so every axis is represented (per-PR runs touch
   a fraction for cost control; nightly runs the full set).
2. **Scores** each case two ways — cheap deterministic **code checks** (schema, citations,
   retrieval) and an **LLM-as-judge** for the subjective axes.
3. **Corrects** the judge's bias with Rogan–Gladen + the adjusted-Wald CI. Deterministic
   axes are unbiased, so they skip correction and use an exact binomial interval instead.
4. **Gates** with a one-sided **two-sample drop test** against the committed `main`
   baseline, Bonferroni-corrected across axes.

That last step is the one I got wrong first, so it's worth showing. The naive version —
"block if the current CI lower bound is below baseline" — false-blocks almost every
per-PR sample, because a small sample's interval is wider than the tolerance even when
nothing changed. The right test compares the *drop* and only blocks when we're confident
the drop itself exceeds tolerance:

```python
delta = est.corrected - base                 # signed; negative = regression
drop = base - est.corrected
drop_se = math.sqrt(est.se**2 + base_se**2)  # both runs carry uncertainty
drop_lower = drop - z * drop_se              # conservative lower bound of the drop
regressed = bool(drop_lower > tol)
```

Identical builds give a drop of ~0, so they never false-block — *regardless of how wide
the CI is*. That property is what makes the gate safe to mark as required.

## What was hard, and what I learned

Three things surprised me.

**The statistics are the product.** The eval harness is the easy 80%. The 20% that
matters — and that nobody else ships — is correctly propagating three sources of
uncertainty through a ratio estimator. I cross-check my analytic CI against the
[`judgy`](https://github.com/ai-evals-course/judgy) library's bootstrap and reproduce the
paper's worked example exactly in the test suite, because "trust me, the math is right" is
not a thing you can say about a gate that blocks people's merges.

**Calibration has to be measured, not assumed.** It's tempting to hard-code "the judge is
90% accurate." CIGate's `cuad_real` dataset is built from [CUAD](https://www.atticusprojectai.org/cuad)
— real commercial contracts with expert clause annotations — specifically so the judge's
confusion matrix is *measured from real expert labels*. Synthetic confidence is no
confidence.

**Cost discipline is a feature.** The whole thing runs in a deterministic **mock mode**
for **$0** — no API key — which is what powers the test suite and the demo CI going red
then green for free. Flip on `ANTHROPIC_API_KEY` and the *same* pipeline uses Claude as
generator and judge. Being able to develop and demo the entire gate offline changed how
fast I could iterate.

## Try it in 60 seconds ($0, offline)

```bash
git clone https://github.com/awesome-pro/cigate && cd cigate
pip install -e ".[dev]"

cigate baseline --promote              # establish a 'good' baseline (full run)
BUILD_FLAVOR=regressed cigate gate     # → blocks: hallucination + citation_error red
BUILD_FLAVOR=good      cigate gate     # → passes: all axes within tolerance
pytest -q                              # 26 tests, all green, $0
```

To gate your own product, point `evalconfig.yaml` at any `(question) -> SUTOutput`
callable, bring your own golden set, and drop the composite Action into your pipeline.

## Links

- **Repo:** https://github.com/awesome-pro/cigate
- **The statistical core:** [`src/cigate/stats.py`](../src/cigate/stats.py) ·
  **the drop test:** [`src/cigate/gate.py`](../src/cigate/gate.py)
- **Methodology:** [`docs/METHODOLOGY.md`](METHODOLOGY.md) ·
  **Architecture:** [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) ·
  **Auditor pack:** [`docs/samples/auditor_pack.md`](samples/auditor_pack.md)
- **Method paper:** Lee, Zeng et al., *How to Correctly Report LLM-as-a-Judge
  Evaluations* — [arXiv:2511.21140](https://arxiv.org/abs/2511.21140)

Built from the "Eval-Gated CI/CD" system-design case study, and grounded in the evals
work of Hamel Husain, Shreya Shankar, and Eugene Yan.
