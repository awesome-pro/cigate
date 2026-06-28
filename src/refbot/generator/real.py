"""Real generator — Claude via the Anthropic Messages API.

Used when ``ANTHROPIC_API_KEY`` is set and ``CIGATE_MOCK`` is not. Unlike the mock, it
never sees ground-truth labels: it answers from retrieved context using the *active*
answer prompt (v1 good / v2 regressed), and citations are parsed back out of the text.
Requires the ``[real]`` extra (``pip install 'cigate[real]'``).
"""

from __future__ import annotations

import re

from cigate.types import Case, SUTOutput

from .. import config
from ..interfaces import Hit
from ..prompts import get_answer_prompt

_CITE = re.compile(r"\[([a-z0-9][a-z0-9\-]+)\]")


def _context(hits: list[Hit]) -> str:
    return "\n\n".join(f"[{h.doc_id}] {h.title}\n{h.text}" for h in hits)


def generate(question: str, hits: list[Hit], case: Case | None = None) -> SUTOutput:
    import anthropic  # lazy import; only needed in real mode

    prompt = get_answer_prompt(config.active_prompt_version())
    client = anthropic.Anthropic()
    retrieved_ids = [h.doc_id for h in hits]
    user = (
        f"Customer question:\n{question}\n\n"
        f"Policy excerpts:\n{_context(hits)}\n\n"
        "Answer the question."
    )
    resp = client.messages.create(
        model=config.gen_model(),
        max_tokens=600,
        system=prompt["system"],
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text").strip()
    citations = list(dict.fromkeys(_CITE.findall(text)))  # de-dup, keep order
    usage = getattr(resp, "usage", None)
    meta = {
        "flavor": prompt.get("flavor", "good"),
        "provider": "anthropic",
        "model": config.gen_model(),
        "input_tokens": getattr(usage, "input_tokens", 0),
        "output_tokens": getattr(usage, "output_tokens", 0),
    }
    return SUTOutput(text=text, citations=citations, retrieved_ids=retrieved_ids,
                     prompt_version=prompt["version"], meta=meta)
