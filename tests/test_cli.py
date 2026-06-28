"""CLI smoke tests — guards the arg-parsing contract the GitHub Action relies on
(`--config` must be accepted *after* the subcommand, e.g. `cigate gate --config ...`).
"""

from __future__ import annotations

import pytest

from cigate.cli import main


@pytest.fixture(autouse=True)
def _mock(monkeypatch):
    monkeypatch.setenv("CIGATE_MOCK", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_gate_accepts_config_after_subcommand(monkeypatch, tmp_path):
    monkeypatch.setenv("BUILD_FLAVOR", "good")
    rc = main([
        "gate", "--config", "evalconfig.yaml", "--fraction", "0.1",
        "--out-report", str(tmp_path / "r.md"),
        "--out-summary", str(tmp_path / "s.json"),
    ])
    assert rc == 0
    assert (tmp_path / "r.md").exists()


def test_run_accepts_config_after_subcommand(tmp_path):
    rc = main([
        "run", "--config", "evalconfig.yaml", "--fraction", "0.1",
        "--out", str(tmp_path / "results.json"),
    ])
    assert rc == 0
    assert (tmp_path / "results.json").exists()
