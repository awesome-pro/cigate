"""Judge calibration & drift detection.

Measures, per axis, the judge's sensitivity (TPR), specificity (TNR), accuracy, and
Cohen's kappa against the human-labeled calibration set. These TPR/TNR feed the
statistical correction; the accuracy/kappa are the SLIs that catch judge-prompt drift
(re-tune when accuracy < 80% or kappa < 0.7).

The headline use in real mode: calibrate the Claude judge against CUAD's expert
annotations, so the correction's confusion matrix is *measured from real bias*, not
assumed.
"""

from __future__ import annotations

import json

from . import corpus as corpus_mod
from .config import load_config
from .evaluators import code_based
from .evaluators.judge import make_judge
from .goldenset import load_calibration
from .parallel import map_progress
from .runner import _context, _detector
from .sut import load_object
from .taxonomy import AXIS_BY_KEY


def _kappa(preds: list[int], truth: list[int]) -> float:
    n = len(preds)
    if n == 0:
        return float("nan")
    po = sum(int(p == t) for p, t in zip(preds, truth)) / n
    p_pred1 = sum(preds) / n
    p_true1 = sum(truth) / n
    pe = p_pred1 * p_true1 + (1 - p_pred1) * (1 - p_true1)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def calibrate(cfg, perturb_judge: bool = False) -> dict:
    mock = cfg.mock_mode()
    corpus = corpus_mod.load_corpus(cfg.corpus)
    valid_ids = set(corpus)

    if mock and perturb_judge:
        # Simulate judge drift: degrade sensitivity/specificity on subjective axes.
        drifted = dict(cfg.judge.confusion)
        for axis in ("hallucination", "refusal"):
            s, t = drifted.get(axis, (0.9, 0.9))
            drifted[axis] = (max(0.5, s - 0.15), max(0.5, t - 0.15))
        cfg.judge.confusion = drifted

    judge_prompt = {} if mock else load_object(cfg.judge_prompt)
    judge = make_judge(mock, cfg, judge_prompt, cfg.sampling.seed)

    # Calibration (TPR/TNR/kappa) is only meaningful for judge-involved axes; code-only
    # axes are deterministic (no bias to measure).
    judge_axes = [a for a in cfg.axes if AXIS_BY_KEY[a].evaluator != "code"]
    code_axes = [a for a in cfg.axes if AXIS_BY_KEY[a].evaluator == "code"]

    preds = {a: [] for a in judge_axes}
    truth = {a: [] for a in judge_axes}

    def _score(item):
        case, output = item
        ctx = _context(corpus, output.retrieved_ids)
        code = code_based.code_verdicts(output, case, valid_ids)
        jr = judge.judge(case, output, ctx)
        return case, code, jr

    items = list(load_calibration(cfg.calibration_set))
    desc = "mock calibration" if mock else "judge vs expert labels"
    for res in map_progress(_score, items, desc=desc):
        if res is None:
            continue
        case, code, jr = res
        for a in judge_axes:
            if a in case.truth_labels:
                preds[a].append(int(_detector(a, code, jr.verdicts)))
                truth[a].append(int(bool(case.truth_labels[a])))

    axes_out = {a: {"deterministic": True, "note": "code axis; no calibration needed"}
                for a in code_axes}
    for a in judge_axes:
        p, t = preds[a], truth[a]
        pos = [pi for pi, ti in zip(p, t) if ti == 1]
        neg = [pi for pi, ti in zip(p, t) if ti == 0]
        tpr = sum(pos) / len(pos) if pos else float("nan")
        tnr = (1 - sum(neg) / len(neg)) if neg else float("nan")
        acc = sum(int(pi == ti) for pi, ti in zip(p, t)) / len(p) if p else float("nan")
        axes_out[a] = {
            "n": len(p), "m_pos": len(pos), "m_neg": len(neg),
            "tpr": round(tpr, 4), "tnr": round(tnr, 4),
            "accuracy": round(acc, 4), "kappa": round(_kappa(p, t), 4),
            "drift_flag": (acc < 0.80) or (_kappa(p, t) < 0.70),
        }
    return {"mock": mock, "perturbed": perturb_judge, "axes": axes_out}


def run_calibration(args) -> int:
    cfg = load_config(args.config)
    result = calibrate(cfg, perturb_judge=getattr(args, "perturb_judge", False))
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[cigate calibrate] mode={'mock' if result['mock'] else 'real'}"
          f"{' (perturbed)' if result['perturbed'] else ''}")
    for a, d in result["axes"].items():
        if d.get("deterministic"):
            print(f"  {a:16s} deterministic (code axis; no calibration)")
            continue
        flag = "  ⚠️ DRIFT" if d["drift_flag"] else ""
        print(f"  {a:16s} TPR={d['tpr']} TNR={d['tnr']} "
              f"acc={d['accuracy']} kappa={d['kappa']} (n={d['n']}){flag}")
    print(f"  -> {args.out}")
    return 0
