"""Typed configuration loaded from ``evalconfig.yaml``.

Resolution order for "are we in mock mode":
1. If ``CIGATE_MOCK=1`` in the environment -> mock.
2. Else if no ``ANTHROPIC_API_KEY`` in the environment -> mock (so forks / no-key runs are $0).
3. Else -> real (Claude).

This keeps the whole system runnable for $0 by default while letting a present API
key flip it to the authentic experience with no config change.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .taxonomy import ALL_AXIS_KEYS


class SamplingConfig(BaseModel):
    fraction: float = 0.20          # default per-PR sample of the golden set
    stratify: bool = True           # ensure every axis is represented
    min_per_axis: int = 1
    seed: int = 7


class GateConfig(BaseModel):
    tolerance: float = 0.02         # allowed drop in corrected lower-bound vs baseline (abs)
    confidence_level: float = 0.95
    multiple_comparison: str = "bonferroni"  # "bonferroni" | "bh" | "none"
    min_calibration_per_class: int = 20      # warn below this; affects CI width


class BudgetConfig(BaseModel):
    max_usd_per_run: float = 40.0
    monthly_ceiling_usd: float = 5000.0


class JudgeConfig(BaseModel):
    model: str = "claude-sonnet-4-6"
    # per-axis mock confusion matrix (sensitivity, specificity); used only in mock mode.
    confusion: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {
            "hallucination": (0.92, 0.88),
            "retrieval_miss": (0.92, 0.88),
            "citation_error": (0.95, 0.93),
            "refusal": (0.91, 0.92),
            "format_violation": (0.99, 0.99),  # code-owned; not used for gating
        }
    )


class GeneratorConfig(BaseModel):
    model: str = "claude-opus-4-8"


class Config(BaseModel):
    sut: str = "refbot.pipeline:rag_answer"
    goldenset: str = "goldensets/synthetic_contract.yaml"
    calibration_set: str = "goldensets/holdout_calibration.yaml"
    corpus: str = "goldensets/corpus"          # dir of documents the retriever indexes
    axes: list[str] = Field(default_factory=lambda: list(ALL_AXIS_KEYS))
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    gate: GateConfig = Field(default_factory=GateConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    generator: GeneratorConfig = Field(default_factory=GeneratorConfig)
    judge_prompt: str = "refbot.prompts:JUDGE_PROMPT"   # module:attr, product-specific
    baseline_path: str = ".cigate/baseline.json"

    # ---- runtime helpers -------------------------------------------------
    def mock_mode(self) -> bool:
        if os.environ.get("CIGATE_MOCK", "") == "1":
            return True
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return True
        return False


def load_config(path: str | Path = "evalconfig.yaml") -> Config:
    p = Path(path)
    if not p.exists():
        return Config()
    data = yaml.safe_load(p.read_text()) or {}
    # YAML stores confusion matrix values as lists; coerce to tuples.
    judge = data.get("judge", {})
    if isinstance(judge.get("confusion"), dict):
        judge["confusion"] = {k: tuple(v) for k, v in judge["confusion"].items()}
    return Config(**data)
