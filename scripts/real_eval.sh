#!/usr/bin/env bash
# Run the REAL cross-provider eval: the product-under-test runs on OpenAI GPT, the judge
# is Claude. Reads keys from a gitignored .env. Results land in docs/results/.
#
#   .env must contain:  ANTHROPIC_API_KEY=...   (the Claude judge)
#                       OPENAI_API_KEY=...      (the GPT product-under-test)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then set -a; . ./.env; set +a; else
  echo "ERROR: create a .env (gitignored) with ANTHROPIC_API_KEY and OPENAI_API_KEY"; exit 1
fi
[ -n "${ANTHROPIC_API_KEY:-}" ] || { echo "ANTHROPIC_API_KEY missing (needed for the Claude judge)"; exit 1; }
[ -n "${OPENAI_API_KEY:-}" ]    || { echo "OPENAI_API_KEY missing (needed for the GPT product)"; exit 1; }

source .venv/bin/activate 2>/dev/null || true
pip install -q -e ".[real]" >/dev/null

export REFBOT_GEN_PROVIDER=openai
export REFBOT_GEN_MODEL="${REFBOT_GEN_MODEL:-gpt-4o-mini}"
mkdir -p docs/results

echo "============================================================"
echo " 1) REAL judge calibration vs CUAD expert labels (Claude judge)"
echo "============================================================"
cigate calibrate --config evalconfig_cuad.yaml --out docs/results/cuad_calibration_real.json

echo "============================================================"
echo " 2) REAL baseline — good prompt (answer_v1), GPT product"
echo "============================================================"
REFBOT_PROMPT=answer_v1 cigate baseline --promote --config evalconfig_realdemo.yaml

echo "============================================================"
echo " 3) REAL gate — REGRESSED prompt (answer_v2)  [expect BLOCK]"
echo "============================================================"
REFBOT_PROMPT=answer_v2 cigate gate --config evalconfig_realdemo.yaml \
  --out-report docs/results/real_regressed_report.md \
  --out-summary docs/results/real_regressed_summary.json || true

echo "============================================================"
echo " 4) REAL gate — good prompt (answer_v1)  [expect PASS]"
echo "============================================================"
REFBOT_PROMPT=answer_v1 cigate gate --config evalconfig_realdemo.yaml \
  --out-report docs/results/real_good_report.md \
  --out-summary docs/results/real_good_summary.json

echo ""
echo "Done. Real results in docs/results/ (model: $REFBOT_GEN_MODEL product, claude-sonnet-5 judge)."
