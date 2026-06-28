"""End-to-end gate behavior in deterministic mock mode.

Proves the headline guarantees: the gate is reproducible, it BLOCKS a regressed build
(isolating the degraded axes), and it PASSES a clean build.
"""

from __future__ import annotations

import pytest

from cigate.config import load_config
from cigate.gate import baseline_from_run, evaluate_gate
from cigate.runner import run


@pytest.fixture(autouse=True)
def _mock(monkeypatch):
    monkeypatch.setenv("CIGATE_MOCK", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def cfg():
    return load_config("evalconfig.yaml")


def test_mock_run_is_deterministic(monkeypatch, cfg):
    monkeypatch.setenv("BUILD_FLAVOR", "good")
    r1 = run(cfg, fraction=0.3, seed=7)
    r2 = run(cfg, fraction=0.3, seed=7)
    assert r1.eval_preds == r2.eval_preds
    assert r1.cost_usd == 0.0  # mock mode is free


def test_gate_blocks_regression_and_isolates_axes(monkeypatch, cfg):
    monkeypatch.setenv("BUILD_FLAVOR", "good")
    baseline = baseline_from_run(run(cfg, fraction=1.0, seed=7), cfg)

    monkeypatch.setenv("BUILD_FLAVOR", "regressed")
    report = evaluate_gate(run(cfg, fraction=0.5, seed=11), cfg, baseline)

    assert report.regressed
    regressed = {r.axis for r in report.results if r.regressed}
    assert {"hallucination", "citation_error"} <= regressed
    # The regression must NOT bleed into unrelated axes.
    assert "retrieval_miss" not in regressed
    assert "refusal" not in regressed
    assert "format_violation" not in regressed


def test_gate_passes_clean_build(monkeypatch, cfg):
    monkeypatch.setenv("BUILD_FLAVOR", "good")
    baseline = baseline_from_run(run(cfg, fraction=1.0, seed=7), cfg)
    report = evaluate_gate(run(cfg, fraction=0.5, seed=11), cfg, baseline)
    assert not report.regressed


def test_corrected_beats_raw_on_regressed_judge_axis(monkeypatch, cfg):
    """On judge axes the corrected estimate should differ from the raw judge rate
    (bias correction is actually doing something)."""
    monkeypatch.setenv("BUILD_FLAVOR", "good")
    baseline = baseline_from_run(run(cfg, fraction=1.0, seed=7), cfg)
    monkeypatch.setenv("BUILD_FLAVOR", "regressed")
    report = evaluate_gate(run(cfg, fraction=1.0, seed=7), cfg, baseline)
    hallu = next(r for r in report.results if r.axis == "hallucination")
    assert hallu.estimate.observed_pass_rate != hallu.estimate.corrected
