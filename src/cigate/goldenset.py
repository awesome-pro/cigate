"""Golden-set + calibration-set loading and cost-bounded stratified sampling.

Per-PR runs evaluate only a sample of the golden set (cost control), but the sample is
*stratified by failure mode* so every axis is represented — a corner of the eval space
is never silently skipped. Full runs (nightly / `full-eval` label) use fraction=1.0.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

import yaml

from .types import Case, SUTOutput

_CITE = re.compile(r"\[([a-z0-9][a-z0-9\-]+)\]")
_CASE_FIELDS = {
    "id", "question", "axes", "gold_doc_ids", "reference_answer",
    "in_corpus", "truth_labels", "metadata",
}


def load_golden(path: str | Path) -> list[Case]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    cases = []
    for raw in data.get("cases", []):
        cases.append(Case(**{k: v for k, v in raw.items() if k in _CASE_FIELDS}))
    return cases


def load_calibration(path: str | Path) -> list[tuple[Case, SUTOutput]]:
    """Calibration items pair a fixed candidate answer with expert per-axis labels.

    Returns ``[(case, output)]`` where ``case.truth_labels`` holds the human labels
    (so the mock judge corrupts the *truth*, and we can measure judge TPR/TNR) and
    ``output`` reconstructs the fixed answer for the evaluators.
    """
    data = yaml.safe_load(Path(path).read_text()) or {}
    out = []
    for raw in data.get("cases", []):
        answer = raw.get("answer", "")
        gold = raw.get("gold_doc_ids", []) or []
        in_corpus = raw.get("in_corpus", True)
        citations = raw.get("citations") or list(dict.fromkeys(_CITE.findall(answer)))
        retrieved = raw.get("retrieved_ids")
        if retrieved is None:
            retrieved = list(gold) if in_corpus else []
        case = Case(
            id=raw["id"], question=raw.get("question", ""),
            axes=list(raw.get("human_labels", {}).keys()),
            gold_doc_ids=gold, in_corpus=in_corpus,
            truth_labels=raw.get("human_labels", {}),
            metadata=raw.get("metadata", {}),
        )
        output = SUTOutput(text=answer, citations=citations, retrieved_ids=retrieved,
                           prompt_version="calibration", meta={})
        out.append((case, output))
    return out


def stratified_sample(
    cases: list[Case], fraction: float, axes: list[str],
    min_per_axis: int = 1, seed: int = 7,
) -> list[Case]:
    """Sample ~fraction of cases while guaranteeing >= min_per_axis cases per axis."""
    if fraction >= 1.0 or len(cases) == 0:
        return list(cases)
    rng = random.Random(seed)
    target = max(1, math.ceil(fraction * len(cases)))

    by_id = {c.id: c for c in cases}
    chosen: set[str] = set()

    # 1) Guarantee axis coverage.
    for axis in axes:
        pool = [c for c in cases if axis in (c.axes or [])]
        rng.shuffle(pool)
        for c in pool[:min_per_axis]:
            chosen.add(c.id)

    # 2) Fill the rest at random (deterministically).
    rest = [c.id for c in cases if c.id not in chosen]
    rng.shuffle(rest)
    for cid in rest:
        if len(chosen) >= target:
            break
        chosen.add(cid)

    return [by_id[cid] for cid in sorted(chosen)]
