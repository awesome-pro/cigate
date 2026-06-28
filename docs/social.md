# CIGate — launch copy

Three standalone, copy-pasteable variants: an X/Twitter thread, a LinkedIn post, and a
one-line "Show HN" tagline. All consistent with the README's claims and terminology.

---

## (a) X / Twitter thread

**1/**
Your LLM eval suite is lying to you.

It gates merges on the judge's raw pass rate. But in-domain judge accuracy is only 75–88% — so that number is *biased*. You over-block (devs route around the gate) or under-block (regressions ship).

I built CIGate to fix it. 🧵

**2/**
The canonical disaster: a one-line prompt tweak quietly degrades quality on one slice of traffic. No test goes red. The judge metric drifts 11 points unnoticed. A $4M renewal is gone before anyone looks.

Prompt changes have non-local effects. Vibes don't catch them.

**3/**
Promptfoo, Braintrust, Langfuse, DeepEval all gate on the RAW judge score.

CIGate gates on the BIAS-CORRECTED pass rate's confidence-interval LOWER BOUND — per failure-mode axis.

The pun is the whole thesis: gate your Continuous Integration on a Confidence Interval. 🚦

**4/**
Three parts, all load-bearing:

1. Correct the judge's bias (Rogan–Gladen, from its measured sensitivity/specificity)
2. Gate on a CI lower bound, not a point (adjusted-Wald, arXiv:2511.21140)
3. Per axis — never a composite that hides a regression in an average

**5/**
Here's a blocked PR. One line ships "be helpful, citations optional." CIGate isolates the damage to the two axes it actually hurt:

🔴 hallucination  98.9% → 37.0%  (−61.9pp)
🔴 citation_error  100% → 65.5%  (−34.5pp)
🟢 everything else within tolerance → merge blocked.

**6/**
The trick that makes it safe to mark "required": it's a two-sample DROP test vs the committed `main` baseline (Bonferroni-corrected).

Identical builds give a drop of ~0, so they never false-block — no matter how wide the CI is. No eval theater.

**7/**
It runs in deterministic mock mode for $0 — no API key. That's what powers the test suite and the demo CI going red→green for free.

Flip on ANTHROPIC_API_KEY and the same pipeline uses Claude as generator + judge. Calibrated against real expert labels (CUAD contracts).

**8/**
60 seconds, $0, offline:

git clone …/cigate && cd cigate
pip install -e ".[dev]"
cigate baseline --promote
BUILD_FLAVOR=regressed cigate gate   # blocks
BUILD_FLAVOR=good cigate gate        # passes

MIT. Code + demo + methodology:
github.com/awesome-pro/cigate

---

## (b) LinkedIn post

Most teams shipping AI features gate their CI on an LLM-judge's pass rate. There's a
quiet problem with that: in-domain LLM-judge accuracy is only ~75–88%, so that pass rate
is a *biased* estimate. Gate on it and you either over-block (developers learn to route
around the check) or under-block (real regressions ship anyway). That's how a one-line
prompt tweak can drift a quality metric 11 points and cost a renewal before anyone
notices.

I built CIGate, an open-source reference implementation of an "Eval-Gated CI/CD" system,
to close that gap. Instead of the raw judge score, it gates on the **bias-corrected pass
rate's confidence-interval lower bound, per failure-mode axis** — Rogan–Gladen correction
plus an adjusted-Wald delta-method CI (arXiv:2511.21140), cross-checked against the
`judgy` library. The gate is a one-sided two-sample drop test against a committed
baseline, so identical builds never false-block.

The engineering lesson I keep coming back to: the eval harness is the easy part. Correctly
propagating uncertainty through the judge's bias — so a blocking decision is defensible —
is the part that's actually hard, and the part most tools skip.

Runs in mock mode for $0. MIT-licensed. Feedback welcome.

👉 github.com/awesome-pro/cigate

#MachineLearning #LLM #MLOps #AIEngineering #Evals

---

## (c) Show HN tagline

**Show HN: CIGate – block a merge when LLM answer quality regresses, with the judge's bias corrected (gate on a confidence interval, not the vibes; runs $0 offline)**
