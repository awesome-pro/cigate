"""Versioned prompt registry.

``ACTIVE_PROMPT`` is the single source of truth for which answer prompt the bot ships.
The demo's regression PR is a one-line change here: ``answer_v1`` -> ``answer_v2``.
"""

from __future__ import annotations

from . import answer_v1, answer_v2, judge_v1

ANSWER_PROMPTS = {
    answer_v1.PROMPT["version"]: answer_v1.PROMPT,
    answer_v2.PROMPT["version"]: answer_v2.PROMPT,
}

JUDGE_PROMPT = judge_v1.PROMPT

# >>> The line the demo regression PR flips. <<<
ACTIVE_PROMPT = "answer_v2"


def get_answer_prompt(version: str | None = None) -> dict:
    return ANSWER_PROMPTS[version or ACTIVE_PROMPT]
