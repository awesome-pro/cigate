"""LLM-as-judge — the subjective evaluator whose bias we statistically correct.

Two implementations behind one interface:

- :class:`MockJudge` — deterministic. It reads the ground-truth per-axis outcome
  (from ``output.meta["truth"]`` for live cases, or ``case.truth_labels`` for
  calibration cases) and corrupts it through a configured per-axis confusion matrix
  ``(sensitivity, specificity)``, seeded per (case, axis). Over many cases its empirical
  TPR/TNR match the configured matrix, so the correction layer has real, known bias to
  recover. Runs offline for $0 and powers the tests/CI.
- :class:`ClaudeJudge` — real Claude via forced tool-use for a structured per-axis verdict.

Both return a :class:`JudgeResult`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .. import cost
from ..types import Case, SUTOutput

# Axes the judge owns (judge-only + the judge part of "both").
JUDGE_AXES = ("hallucination", "retrieval_miss", "citation_error", "refusal")


@dataclass
class JudgeResult:
    verdicts: dict[str, bool] = field(default_factory=dict)
    rationale: str = ""
    cost_usd: float = 0.0


def _unit(*parts: object) -> float:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _truth_for(case: Case, output: SUTOutput) -> dict[str, bool]:
    meta_truth = output.meta.get("truth") if output.meta else None
    if meta_truth:
        return meta_truth
    return case.truth_labels or {}


class MockJudge:
    def __init__(self, confusion: dict[str, tuple[float, float]], seed: int = 0,
                 axes: tuple[str, ...] = JUDGE_AXES):
        self.confusion = confusion
        self.seed = seed
        self.axes = axes

    def judge(self, case: Case, output: SUTOutput, context: str = "") -> JudgeResult:
        truth = _truth_for(case, output)
        verdicts: dict[str, bool] = {}
        for axis in self.axes:
            sens, spec = self.confusion.get(axis, (0.9, 0.9))
            u = _unit(self.seed, case.id, axis)
            truly_pass = bool(truth.get(axis, True))
            # P(judge=pass | truly pass) = sens ; P(judge=pass | truly fail) = 1 - spec
            verdicts[axis] = (u < sens) if truly_pass else (u >= spec)
        return JudgeResult(verdicts=verdicts, rationale="mock(confusion-matrix)", cost_usd=0.0)


class ClaudeJudge:
    def __init__(self, model: str, judge_prompt: dict, axes: tuple[str, ...] = JUDGE_AXES):
        self.model = model
        self.prompt = judge_prompt
        self.axes = axes

    def _tool_schema(self) -> dict:
        props = {a: {"type": "boolean"} for a in self.axes}
        props["rationale"] = {"type": "string"}
        return {
            "name": "report_verdict",
            "description": "Report the per-axis pass/fail verdict.",
            "input_schema": {
                "type": "object",
                "properties": props,
                "required": list(self.axes) + ["rationale"],
            },
        }

    def judge(self, case: Case, output: SUTOutput, context: str = "") -> JudgeResult:
        import anthropic

        client = anthropic.Anthropic()
        rubric = "\n".join(
            f"- {a}: {self.prompt['axis_rubric'][a]}" for a in self.axes
        )
        user = self.prompt["user_template"].format(
            question=case.question, context=context or "(none provided)",
            answer=output.text, axes=", ".join(self.axes),
        )
        resp = client.messages.create(
            model=self.model,
            max_tokens=700,
            system=self.prompt["system"] + "\n\nAxis rubric:\n" + rubric,
            tools=[self._tool_schema()],
            tool_choice={"type": "tool", "name": "report_verdict"},
            messages=[{"role": "user", "content": user}],
        )
        data = next((b.input for b in resp.content if b.type == "tool_use"), {})
        verdicts = {a: bool(data.get(a, False)) for a in self.axes}
        usage = getattr(resp, "usage", None)
        c = cost.price(self.model, getattr(usage, "input_tokens", 0),
                       getattr(usage, "output_tokens", 0))
        return JudgeResult(verdicts=verdicts, rationale=str(data.get("rationale", "")),
                           cost_usd=c)


def make_judge(mock: bool, cfg, judge_prompt: dict, seed: int) -> "MockJudge | ClaudeJudge":
    if mock:
        return MockJudge(cfg.judge.confusion, seed=seed)
    return ClaudeJudge(cfg.judge.model, judge_prompt)
