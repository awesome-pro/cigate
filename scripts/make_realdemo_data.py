"""Create small, cost-bounded subsets for the REAL cross-provider eval demo.

Deterministically subsamples the synthetic golden + calibration sets so a real run
(GPT generates, Claude judges) stays in the ~$2-5 range. Run: `python scripts/make_realdemo_data.py`.
"""

from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AXES = ["hallucination", "retrieval_miss", "citation_error", "refusal", "format_violation"]


def main() -> None:
    rng = random.Random(11)
    golden = yaml.safe_load((ROOT / "goldensets/synthetic_contract.yaml").read_text())["cases"]
    calib = yaml.safe_load((ROOT / "goldensets/holdout_calibration.yaml").read_text())["cases"]

    # Golden: ~30 in-corpus (prefer cases that exercise hallucination/citation, which the
    # regressed prompt degrades) + ~10 out-of-corpus (refusal).
    in_corpus = [c for c in golden if c.get("in_corpus", True)]
    ooc = [c for c in golden if not c.get("in_corpus", True)]

    def score(c):
        ax = set(c.get("axes", []))
        return ("hallucination" in ax) + ("citation_error" in ax)

    in_sorted = sorted(in_corpus, key=lambda c: (-score(c), c["id"]))
    sel_golden = sorted(in_sorted[:30] + sorted(ooc, key=lambda c: c["id"])[:10],
                        key=lambda c: c["id"])
    (ROOT / "goldensets/realdemo_golden.yaml").write_text(
        yaml.safe_dump({"cases": sel_golden}, sort_keys=False))

    # Calibration: balanced ~12 pass + ~12 fail per judge axis.
    target = 12
    cnt = defaultdict(lambda: {0: 0, 1: 0})
    shuffled = list(calib)
    rng.shuffle(shuffled)
    selected = []
    for c in shuffled:
        hl = c.get("human_labels", {})
        if any(a in hl and cnt[a][int(bool(hl[a]))] < target for a in AXES):
            selected.append(c)
            for a in AXES:
                if a in hl:
                    cnt[a][int(bool(hl[a]))] += 1
        if len(selected) >= 70:
            break
    (ROOT / "goldensets/realdemo_calibration.yaml").write_text(
        yaml.safe_dump({"cases": selected}, sort_keys=False))

    print(f"golden: {len(sel_golden)} ({len(ooc[:10])} out-of-corpus) | calib: {len(selected)}")
    for a in AXES:
        print(f"  {a:16s} pass={cnt[a][1]} fail={cnt[a][0]}")


if __name__ == "__main__":
    main()
