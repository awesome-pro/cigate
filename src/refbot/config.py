"""Runtime configuration for the reference bot.

Single env flip flips the whole bot:
- ``CIGATE_MOCK=1`` or no ``ANTHROPIC_API_KEY`` -> deterministic mock mode ($0, offline).
- otherwise -> real Claude.

The *flavor* (good/regressed) is derived from the active prompt by default, so the demo
regression is a one-line code change (``ACTIVE_PROMPT`` in ``prompts/__init__.py``); an
explicit ``BUILD_FLAVOR`` env var can override it for experiments.
"""

from __future__ import annotations

import os

from .prompts import ACTIVE_PROMPT, get_answer_prompt

GEN_MODEL_DEFAULT = "claude-opus-4-8"
SEED_DEFAULT = 7


def mock_mode() -> bool:
    if os.environ.get("CIGATE_MOCK", "") == "1":
        return True
    return not os.environ.get("ANTHROPIC_API_KEY")


def active_prompt_version() -> str:
    return os.environ.get("REFBOT_PROMPT", ACTIVE_PROMPT)


def flavor() -> str:
    """'good' or 'regressed' — drives the mock generator's behavior."""
    env = os.environ.get("BUILD_FLAVOR")
    if env in ("good", "regressed"):
        return env
    return get_answer_prompt(active_prompt_version()).get("flavor", "good")


def seed() -> int:
    try:
        return int(os.environ.get("REFBOT_SEED", SEED_DEFAULT))
    except ValueError:
        return SEED_DEFAULT


def gen_model() -> str:
    return os.environ.get("REFBOT_GEN_MODEL", GEN_MODEL_DEFAULT)


def regression_rate() -> float:
    """Fraction of regression-eligible cases the regressed flavor actually degrades.

    A partial (not total) regression is more realistic and produces a measurable
    per-axis pass-rate drop rather than an all-or-nothing flip.
    """
    try:
        return float(os.environ.get("REFBOT_REGRESSION_RATE", "0.55"))
    except ValueError:
        return 0.55
