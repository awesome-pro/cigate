# Demo PR #2 — a safe change the gate lets through

The gate's job is to catch regressions, **not** to block every change ("gatekeeping
theater"). This PR makes a benign change (e.g., reword the grounded answer prompt or
refactor `refbot` internals) that keeps `ACTIVE_PROMPT = "answer_v1"` — quality is
unchanged.

**What CIGate does on the PR:**

1. `eval-gate` runs in mock mode ($0).
2. Every axis stays within tolerance of `main`'s baseline (the two-sample drop test sees
   no significant drop).
3. The check goes **green** — the PR merges.

Reproduce locally:

```bash
BUILD_FLAVOR=good cigate gate --fail-on-regression       # exit 0
```

In **real** mode (with `ANTHROPIC_API_KEY`), a genuine prompt *improvement* would raise
the corrected pass rates above baseline — also green, and visibly better.
