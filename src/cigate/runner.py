"""The eval runner — executes the SUT over a sampled golden set, scores every case on
every axis (code + judge), and produces the raw per-axis arrays the correction layer
needs. It also scores the calibration set so judge TPR/TNR can be measured.

Detector per axis (uniform machinery): code-owned axes use the deterministic check,
judge-owned axes use the LLM judge, and "both" axes require *both* to pass. Each
detector's bias is then measured on the calibration set and corrected the same way.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import corpus as corpus_mod
from . import cost as cost_mod
from .config import Config
from .evaluators import code_based
from .evaluators.judge import make_judge
from .goldenset import load_calibration, load_golden, stratified_sample
from .sut import load_object, load_sut
from .taxonomy import AXIS_BY_KEY
from .types import SUTOutput


@dataclass
class RunResult:
    axes: list[str]
    eval_preds: dict[str, list[int]] = field(default_factory=dict)
    calib_preds: dict[str, list[int]] = field(default_factory=dict)
    calib_truth: dict[str, list[int]] = field(default_factory=dict)
    cases: list[dict] = field(default_factory=list)     # per-case detail for reports
    cost_usd: float = 0.0
    meta: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "axes": self.axes,
            "eval_preds": self.eval_preds,
            "calib_preds": self.calib_preds,
            "calib_truth": self.calib_truth,
            "cases": self.cases,
            "cost_usd": round(self.cost_usd, 6),
            "meta": self.meta,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_json(), indent=2))


def _context(corpus: dict[str, dict[str, str]], retrieved_ids: list[str], k: int = 5) -> str:
    parts = []
    for did in retrieved_ids[:k]:
        doc = corpus.get(did)
        if doc:
            parts.append(f"[{did}] {doc['title']}\n{doc['text']}")
    return "\n\n".join(parts)


def _detector(axis: str, code: dict[str, bool], judge: dict[str, bool]) -> bool:
    kind = AXIS_BY_KEY[axis].evaluator
    if kind == "code":
        return bool(code.get(axis, True))
    if kind == "judge":
        return bool(judge.get(axis, True))
    return bool(code.get(axis, True)) and bool(judge.get(axis, True))   # "both"


def run(cfg: Config, fraction: float | None = None, seed: int | None = None) -> RunResult:
    mock = cfg.mock_mode()
    seed = cfg.sampling.seed if seed is None else seed
    fraction = cfg.sampling.fraction if fraction is None else fraction
    axes = cfg.axes

    corpus = corpus_mod.load_corpus(cfg.corpus)
    valid_ids = set(corpus)
    golden = load_golden(cfg.goldenset)
    sample = stratified_sample(golden, fraction, axes, cfg.sampling.min_per_axis, seed)

    sut = load_sut(cfg.sut)
    judge_prompt = {} if mock else load_object(cfg.judge_prompt)
    judge = make_judge(mock, cfg, judge_prompt, seed)
    budget = cost_mod.Budget(cfg.budget.max_usd_per_run)

    result = RunResult(axes=axes)
    for a in axes:
        result.eval_preds[a] = []

    prompt_version = "?"
    for case in sample:
        output: SUTOutput = sut(case.question, corpus_dir=cfg.corpus, case=case)
        prompt_version = output.prompt_version
        ctx = _context(corpus, output.retrieved_ids)
        code = code_based.code_verdicts(output, case, valid_ids)
        jr = judge.judge(case, output, ctx)

        gen_tokens = output.meta.get("input_tokens", 0), output.meta.get("output_tokens", 0)
        case_cost = jr.cost_usd + cost_mod.price(cfg.generator.model, *gen_tokens)
        result.cost_usd += case_cost
        budget.add(case_cost)

        verdicts = {a: _detector(a, code, jr.verdicts) for a in axes}
        for a in axes:
            result.eval_preds[a].append(int(verdicts[a]))
        result.cases.append({
            "id": case.id, "question": case.question,
            "citations": output.citations, "retrieved_ids": output.retrieved_ids,
            "verdicts": verdicts, "answer": output.text[:300],
        })

    # ---- calibration: measure judge/detector TPR/TNR ---------------------- #
    for a in axes:
        result.calib_preds[a], result.calib_truth[a] = [], []
    for case, output in load_calibration(cfg.calibration_set):
        ctx = _context(corpus, output.retrieved_ids)
        code = code_based.code_verdicts(output, case, valid_ids)
        jr = judge.judge(case, output, ctx)
        result.cost_usd += jr.cost_usd
        budget.add(jr.cost_usd)
        for a in axes:
            if a in case.truth_labels:
                result.calib_preds[a].append(int(_detector(a, code, jr.verdicts)))
                result.calib_truth[a].append(int(bool(case.truth_labels[a])))

    result.meta = {
        "mock": mock, "fraction": fraction, "seed": seed,
        "prompt_version": prompt_version,
        "judge_model": "mock" if mock else cfg.judge.model,
        "generator_model": "mock" if mock else cfg.generator.model,
        "n_eval": len(sample), "n_golden": len(golden),
    }
    return result


def config_fingerprint(cfg: Config) -> str:
    """Stable hash of the eval-relevant config (for cache keys / reproducibility)."""
    blob = json.dumps({
        "sut": cfg.sut, "goldenset": cfg.goldenset, "axes": cfg.axes,
        "judge_model": cfg.judge.model, "generator_model": cfg.generator.model,
    }, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]
