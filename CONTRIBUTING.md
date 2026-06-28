# Contributing to CIGate

Thanks for your interest! CIGate is the reference implementation of an "Eval-Gated CI/CD"
system. Everything runs in deterministic **mock mode** ($0, no API key), so you can
develop, test, and run the gate end to end for free.

## Dev setup

```bash
git clone https://github.com/awesome-pro/cigate && cd cigate
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Optional extras: `.[real]` (Claude generator + judge), `.[dashboard]` (Streamlit),
`.[crosscheck]` (the `judgy` library, for the CI cross-check test).

## Run the tests

```bash
pytest -q          # all green, $0 (mock mode)
```

The suite includes a cross-check of our analytic confidence interval against `judgy`'s
bootstrap and reproduces the method paper's worked example — please keep both passing if
you touch `src/cigate/stats.py`.

## Run the gate locally

```bash
cigate baseline --promote              # promote a full run to the committed baseline
BUILD_FLAVOR=regressed cigate gate     # → blocks: hallucination + citation_error red
BUILD_FLAVOR=good      cigate gate     # → passes: all axes within tolerance
```

`cigate gate` writes `report.md` (the PR comment) and `summary.json`. Add
`--fail-on-regression` to make it exit 1 when an axis regresses (this is what CI uses).

## Code style

We use [ruff](https://docs.astral.sh/ruff/) (config in `pyproject.toml`, line length 100):

```bash
ruff check .
ruff format .
```

Keep public functions typed and docstringed, especially in the statistical core
(`stats.py`) and the gate (`gate.py`) — those are the load-bearing parts and the place
reviewers will look hardest. Add or update a test with any behavior change.

## Adding a new failure-mode axis

The taxonomy is the single source of truth. To add an axis:

1. Add an `Axis(...)` entry to `AXES` in `src/cigate/taxonomy.py`, choosing
   `evaluator="code" | "judge" | "both"`:
   - `code` — deterministic, unbiased, no LLM (uses an exact binomial interval, no correction).
   - `judge` — subjective; scored by the LLM judge and **bias-corrected** (Rogan–Gladen + CI).
   - `both` — a deterministic *and* a judge signal, combined with AND.
2. List the axis under `axes:` in `evalconfig.yaml` (and any other `evalconfig_*.yaml`).
3. Make sure golden-set cases tag the new axis so it's exercised and stratified into the
   per-PR sample (`goldensets/synthetic_contract.yaml`, with calibration items in
   `goldensets/holdout_calibration.yaml`).
4. For a `judge`/`both` axis, add a per-axis mock confusion matrix entry under
   `judge.confusion` in `evalconfig.yaml` so mock mode has known, real bias to correct.
5. Run `cigate calibrate` to confirm the judge's measured TPR/TNR and Cohen's κ, then
   `cigate baseline --promote` to refresh the baseline.

## Adding or changing an evaluator

Evaluators live in `src/cigate/evaluators/`:

- **Deterministic checks** (schema, citations, retrieval) → `code_based.py`.
- **LLM-judge logic** → `judge.py`.

The per-axis detector in `src/cigate/runner.py` dispatches on the axis's `evaluator` kind,
so once your check returns a per-axis pass/fail it plugs into the existing correction and
gate machinery unchanged. Add a focused test in `tests/test_evaluators.py`.

## Pull requests

- Keep PRs small and focused; include a one-line "why".
- `pytest -q` and `ruff check .` must pass.
- If you change gating or correction behavior, update the relevant doc
  (`docs/METHODOLOGY.md`) and any affected sample report.

By contributing you agree your contributions are licensed under the project's MIT license.
