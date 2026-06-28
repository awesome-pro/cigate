# Publishing checklist — shipping CIGate

A concrete, ordered checklist to take CIGate from local repo to public launch: GitHub
repo + required status check, the two demo PRs, a PyPI release, a tagged GitHub release,
the Marketplace listing, and where to embed the demo.

> **Naming:** the PyPI distribution name **and** the import name are both `cigate`
> (`pip install cigate` → `import cigate`). The CLI entry point is `cigate`.

---

## 0. Pre-flight (do this first)

- [ ] Tests green and free: `pytest -q` (26 tests, $0 in mock mode).
- [ ] Lint clean: `ruff check .`
- [ ] Version is correct in `pyproject.toml` (`version = "0.1.0"`).
- [ ] `README.md`, `LICENSE` (MIT), and `data/cuad/ATTRIBUTION.md` (CC BY 4.0) are present.
- [ ] A committed baseline exists: `cigate baseline --promote` then commit `.cigate/baseline.json`.
- [ ] Decide the GitHub owner/repo. Everything below assumes `awesome-pro/cigate` — match
      the URLs already in `README.md`, `pyproject.toml`, and the Action ref.

---

## 1. Create the GitHub repo + push

```bash
gh repo create awesome-pro/cigate --public --source=. --remote=origin \
  --description "Eval-gated CI/CD for AI products: gate merges on the CI lower bound of a bias-corrected LLM-judge score, per failure-mode axis."
git push -u origin main
```

- [ ] Confirm the default branch is `main` (the eval-gate workflow fetches `origin/main`'s
      baseline).
- [ ] Add repo topics: `llm`, `evaluation`, `llm-as-judge`, `ci-cd`, `evals`,
      `regression-testing`, `mlops`.

---

## 2. Enable the eval gate as a required status check

The `eval-gate` workflow already runs on every PR in mock mode for $0.

- [ ] Settings → Branches → add a branch protection rule for `main`.
- [ ] Enable **Require status checks to pass before merging** and select the **`eval`**
      job from the `eval-gate` workflow.
- [ ] (Optional) Enable **Require branches to be up to date before merging**.
- [ ] (Optional, real mode) Add repo secret `ANTHROPIC_API_KEY` so the gate runs with
      Claude. Omit it and the gate stays in $0 mock mode.

> The check only appears in the list after it has run at least once — open a throwaway PR
> (or the demo PRs below) first, then come back and select it.

---

## 3. Open the two demo PRs (red, then green)

```bash
scripts/demo.sh
```

This creates `demo/regression` (flips the prompt to `answer_v2` → gate goes **red**) and
`demo/safe-change` (cosmetic tweak → gate goes **green**). Prereqs: repo pushed, `gh`
authenticated, baseline committed on `main`.

- [ ] Confirm the regression PR shows a red ❌ required check + the sticky CIGate comment.
- [ ] Confirm the safe-change PR shows a green ✅ check.
- [ ] **Leave both PRs open** — they are living proof for visitors. (Do not merge.)

---

## 4. Publish to PyPI as `cigate` (Trusted Publishing — no tokens)

PyPI Trusted Publishing (OIDC) is wired: the `.github/workflows/pypi.yml` workflow
publishes from the `pypi` environment with `id-token: write` — no API token is stored
anywhere. It runs the tests, builds the wheel+sdist, and uploads on every GitHub Release.

- [ ] In GitHub: **Settings → Environments → New environment → `pypi`** (must match the
      pending publisher; optionally add a required reviewer for release protection).
- [ ] On PyPI the pending publisher for `cigate` (repo `awesome-pro/cigate`, workflow
      `pypi.yml`, environment `pypi`) is already configured — the first publish activates it.
- [ ] Publishing is triggered by creating a GitHub Release (step 5); watch the `pypi`
      workflow run go green.
- [ ] Verify in a fresh venv: `pip install cigate` → `python -c "import cigate"` →
      `cigate --help`.
- [ ] Extras for the project page: `cigate[real]` (Claude), `cigate[dashboard]`
      (Streamlit), `cigate[crosscheck]` (judgy), `cigate[dev]`.

> Token fallback (only if you ever bypass CI): `python -m build && twine upload dist/*`
> with a scoped `__token__`. Trusted Publishing is preferred and already set up.

---

## 5. Tag a release

```bash
git tag -a v0.1.0 -m "CIGate 0.1.0 — eval-gated CI/CD, bias-corrected per-axis gating"
git push origin v0.1.0
gh release create v0.1.0 --title "CIGate 0.1.0" --generate-notes
```

- [ ] In the release notes, link the blog post (`docs/ARTICLE.md`), the demo video, and
      the two demo PRs.
- [ ] Attach the built `dist/*` artifacts to the GitHub release (optional but nice).

---

## 6. List the composite Action on the GitHub Marketplace

The composite action lives at `.github/actions/eval-gate` and is consumed as
`awesome-pro/cigate/.github/actions/eval-gate@v0.1`.

- [ ] Ensure `.github/actions/eval-gate/action.yml` has `name`, `description`, and a
      `branding` block (icon + color) — required for Marketplace.
- [ ] Create a tag the Action ref points to: `git tag v0.1 && git push origin v0.1`
      (and re-point it on each release so `@v0.1` stays current).
- [ ] On the release page, check **Publish this Action to the GitHub Marketplace**, accept
      the agreement, pick primary + secondary categories (e.g. *Continuous integration*,
      *Code quality*).
- [ ] Confirm the README usage snippet matches the published ref:
      ```yaml
      - uses: awesome-pro/cigate/.github/actions/eval-gate@v0.1
        with:
          config: evalconfig.yaml
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}   # omit -> $0 mock mode
      ```

---

## 7. Embed the demo + finalize the front page

- [ ] Record the demo from `docs/DEMO_SCRIPT.md`; upload to Loom/YouTube.
- [ ] Add the video (or a GIF of the red→green run) near the top of `README.md`.
- [ ] Add a PyPI badge to `README.md`:
      `[![pypi](https://img.shields.io/pypi/v/cigate)](https://pypi.org/project/cigate/)`
- [ ] Confirm the existing badges (tests, python, license, "$0 offline") render.
- [ ] Add CIGate to your portfolio site with: one-line pitch, the demo video, links to
      the repo, PyPI, and `docs/ARTICLE.md`. Frame it as the reference implementation of
      the "Eval-Gated CI/CD" system-design case study (a hiring signal for agentic-AI / ML
      roles).

---

## 8. Launch

- [ ] Post the X/Twitter thread, LinkedIn post, and Show HN tagline from `docs/social.md`.
- [ ] Pin the launch tweet; link the demo video and the repo.
- [ ] After launch, watch the demo PRs stay red/green and respond to issues.
