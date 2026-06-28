# CIGate — full demo video script (~10–12 min)

A chaptered script for a proper walkthrough + demo. Records the *story* (why this matters),
the *idea* (the statistics), and *proof* (live mock demo + a REAL cross-provider run with
real numbers). Trim chapters for a shorter cut; the ⭐ chapters are the must-keep core.

> Setup before recording: `source .venv/bin/activate`; have the repo, the two GitHub PRs,
> and `pypi.org/project/cigate` open in tabs. For Chapter 6 you'll need `.env` with both keys
> (and ideally pre-run `scripts/real_eval.sh` so `docs/results/` is populated).

---

## 0 · Cold open (20s) ⭐
**On screen:** the blocked PR comment (`docs/samples/pr_comment_regressed.md` or PR #1).
**Say:** "A one-line prompt change shipped. Six months later a customer noticed answer
quality had quietly dropped on contract questions — and a $4M renewal was gone. Nobody
caught it, because nothing in CI was *measuring* quality. This is the tool that catches it.
It's called CIGate."

## 1 · The problem (60s) ⭐
**On screen:** README "The problem" section.
**Say:** "Everyone shipping LLM features changes prompts, retrieval, and models constantly.
Those changes have non-local effects: you fix one answer and silently break ten. The default
is *vibes-based* shipping, and it produces silent quality regressions that reach production.
We have unit tests for code. We have nothing equivalent for answer quality."

## 2 · Why the obvious fix doesn't work (75s) ⭐
**On screen:** README "The gap nobody fills."
**Say:** "The obvious fix is 'use an LLM as a judge in CI and gate on its score.' The
problem: in-domain LLM-judge accuracy is only 75–88%. The judge is a biased measuring
instrument. Gate on its raw score and you either over-block — false alarms, so devs ignore
the gate — or under-block, and real regressions still ship. Promptfoo, Braintrust, Langfuse:
they all gate on the raw, biased number."

## 3 · The insight (90s) ⭐
**On screen:** `docs/METHODOLOGY.md` — the Rogan–Gladen formula.
**Say:** "CIGate gates on the *corrected* number. We measure the judge's true-positive and
true-negative rate on a human-labeled calibration set, then invert the bias with the
Rogan–Gladen estimator to recover the *true* pass rate — with a confidence interval. Then
the clever part: we don't compare a single CI to the baseline (that false-blocks on small
samples). We run a two-sample *drop test* — block only when we're statistically confident
the drop exceeds tolerance — per failure-mode axis, so a gain on formatting can never mask a
regression on hallucination. That's the thesis: gate your CI/CD on a *confidence interval*,
not the vibes."

## 4 · Architecture (75s)
**On screen:** README mermaid diagram; scroll `src/cigate/stats.py` and `src/cigate/gate.py`.
**Say:** "Two packages: `cigate`, the reusable gate, and `refbot`, a demo RAG support bot as
the system-under-test. Each case is scored two ways — cheap deterministic code checks for
citations and schema, and the LLM judge for subjective axes like hallucination. Code axes are
unbiased, so they use an exact binomial interval; only the judge axes get bias-corrected."

## 5 · Live demo — mock mode, $0 (120s) ⭐
**On screen:** terminal.
```bash
pytest -q                                   # 28 passed
cigate baseline --promote                   # establish a good baseline
BUILD_FLAVOR=regressed cigate gate          # → BLOCKED (hallucination + citation red)
BUILD_FLAVOR=good      cigate gate          # → PASSES
```
**Say:** "Everything runs offline, deterministically, for zero dollars — that's what powers
the test suite and CI. A regressed prompt is blocked, and the report isolates the exact two
axes that got worse. A clean change passes."
**Then on screen:** GitHub PR #1 (red + comment) and PR #2 (green).
**Say:** "These are two live PRs on the repo. The gate runs on every PR in mock mode for
free — red on the regression, green on the safe change. The red check blocks the merge."

## 6 · Real models, real data — cross-provider (150s) ⭐⭐ (the money chapter)
**On screen:** terminal output from `scripts/real_eval.sh` + files in `docs/results/`.
**Say:** "Mock mode proves the mechanics. Now the real thing. The product-under-test runs on
OpenAI GPT; the judge is Claude — so no model grades its own output."
1. **Real judge calibration vs CUAD expert labels** — open `docs/results/cuad_calibration_real.json`.
   "We ran the actual Claude judge over 166 real contract questions from CUAD, a dataset with
   expert legal annotations, and measured its real bias: [read the TPR/TNR/κ]. Not simulated
   — the judge's measured accuracy against human experts."
2. **Real regression caught** — open `docs/results/real_regressed_report.md`.
   "GPT answers 40 real contract questions with the good prompt, then the degraded prompt. The
   degraded answers really are worse — and the gate, using the bias-corrected score, blocks
   it. Total cost: [read the real $] — a few dollars."
3. **Raw-vs-corrected contrast** — point at an axis where raw ≠ corrected.
   "The raw judge score here would have slipped past a naive threshold — the corrected lower
   bound is what caught it."

## 7 · Depth (60s)
```bash
cigate calibrate --perturb-judge            # drift flags fire
cigate report --auditor | head -40          # auditor pack
```
**Say:** "There's an operational layer: judge-drift detection with Cohen's kappa — catch the
judge silently degrading after a model upgrade — cost budgets with caching, and an
auto-generated auditor pack for regulated buyers."

## 8 · Adopt it (45s)
**On screen:** PyPI page; the Action snippet.
```bash
pip install cigate
```
```yaml
- uses: awesome-pro/cigate@v0.1
  with: { config: evalconfig.yaml, anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }} }
```
**Say:** "It's on PyPI and the GitHub Marketplace. Point it at your own bot with one line of
config, drop the Action into your pipeline, and you have an eval gate on every PR."

## 9 · Close (20s) ⭐
**Say:** "Silent quality regressions are the unsolved CI problem for AI products. CIGate
solves it the statistically honest way — correct the judge's bias, gate on the confidence
interval, per failure mode. Links to the repo, PyPI, and the writeup are below."

---

### ⭐ If you only post a 60-second clip
Chapter 0 (hook) → the mock blocked PR (Ch 5) → the real regression caught + cost (Ch 6.2)
→ one line of Chapter 3 ("gate on a confidence interval, not the vibes").

### B-roll / screenshots to capture
- The blocked PR comment (per-axis table).
- `stats.py` Rogan–Gladen function.
- `docs/results/cuad_calibration_real.json` (real κ).
- `docs/results/real_regressed_report.md` (real regression + cost).
- Green CI badge + the PyPI page.
