#!/usr/bin/env bash
# Zero-cost local walkthrough of CIGate. Proves the whole thesis in ~5 seconds:
# a REGRESSED build is BLOCKED, a GOOD build PASSES. Runs fully offline in mock mode
# ($0, no API keys) so anyone can replay it. This is the best first thing to run.
set -uo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true

export CIGATE_MOCK=1          # force free, deterministic mock mode (ignores any API keys)

echo "=================================================================="
echo " CIGate — local walkthrough (mock mode, \$0, fully offline)"
echo "=================================================================="
echo
echo "==> 1/3  Promote a GOOD baseline (this is what 'healthy' looks like)"
BUILD_FLAVOR=good cigate baseline --promote
echo
echo "==> 2/3  Gate a REGRESSED build   (expect: BLOCKED)"
if BUILD_FLAVOR=regressed cigate gate --fail-on-regression; then
  echo "   [!] unexpected: the regressed build PASSED"
else
  echo "   [OK] as expected: the regressed build was BLOCKED (see the per-axis table above)"
fi
echo
echo "==> 3/3  Gate a GOOD build        (expect: PASSES)"
if BUILD_FLAVOR=good cigate gate --fail-on-regression; then
  echo "   [OK] as expected: the good build PASSED"
else
  echo "   [!] unexpected: the good build was blocked"
fi
echo
echo "Done. That is the whole idea: a bad change is blocked, a safe change ships —"
echo "and the report names the exact failure-mode axes that regressed."
