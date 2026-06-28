# Demo PR #1 — a regression the gate catches

**The change:** one line in `src/refbot/prompts/__init__.py`:

```diff
- ACTIVE_PROMPT = "answer_v1"
+ ACTIVE_PROMPT = "answer_v2"
```

`answer_v2` drops the strict-grounding, mandatory-citation, and abstention instructions
("be helpful and complete, citations optional") — a plausible, well-intentioned prompt
edit. In production it silently increases hallucination and missing citations.

**What CIGate does on the PR:**

1. `eval-gate` workflow runs in deterministic mock mode ($0).
2. It evaluates the sampled golden set, statistically corrects the judge scores, and
   compares per axis to `main`'s baseline.
3. `hallucination` and `citation_error` fall well below baseline → the check goes **red**
   and a per-axis comment is posted. The merge is **blocked**.

Expected comment (see `docs/sample_report_regressed.md` for the live version):

> ❌ **CIGate: merge blocked** — 2 axis regression(s)
> `hallucination` 100.0% → 40.7% (−59.3pp), `citation_error` 100.0% → 65.5% (−34.5pp)

Reproduce locally:

```bash
BUILD_FLAVOR=regressed cigate gate --fail-on-regression   # exit 1
```
