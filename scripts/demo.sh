#!/usr/bin/env bash
# Create the two demo PRs that show the gate going red (regression) and green (safe change).
# Prereqs: the repo is pushed to GitHub, `gh` is authenticated, and the eval-gate +
# baseline are committed on main. Run from the repo root.
set -euo pipefail

DEFAULT_BRANCH="$(git symbolic-ref --short HEAD)"
PROMPTS="src/refbot/prompts/__init__.py"

echo "==> Demo PR #1: regression (answer_v1 -> answer_v2)"
git checkout -b demo/regression "$DEFAULT_BRANCH"
# Flip the active prompt to the regressed variant.
python - <<'PY'
import re, pathlib
p = pathlib.Path("src/refbot/prompts/__init__.py")
s = p.read_text().replace('ACTIVE_PROMPT = "answer_v1"', 'ACTIVE_PROMPT = "answer_v2"')
p.write_text(s)
PY
git commit -am "feat(prompt): make the support bot friendlier and more complete

Drops the 'only answer from context / always cite' constraints so answers read
more naturally and we stop telling customers we can't help."
git push -u origin demo/regression
gh pr create --fill --title "Make the support bot friendlier (answer_v2)" \
  --body "Reword the answer prompt to be more helpful and complete. Citations optional."

echo "==> Demo PR #2: safe change (no quality impact)"
git checkout -b demo/safe-change "$DEFAULT_BRANCH"
# A benign wording tweak that keeps answer_v1 active.
python - <<'PY'
import pathlib
p = pathlib.Path("src/refbot/prompts/answer_v1.py")
s = p.read_text().replace("You are a contract & insurance support assistant.",
                          "You are a careful contract & insurance support assistant.")
p.write_text(s)
PY
git commit -am "chore(prompt): minor wording tweak to the grounded answer prompt"
git push -u origin demo/safe-change
gh pr create --fill --title "Minor wording tweak (no behavior change)" \
  --body "Cosmetic wording change; quality should be unchanged."

git checkout "$DEFAULT_BRANCH"
echo "==> Done. Open the two PRs on GitHub to watch CIGate go red then green."
