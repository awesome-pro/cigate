"""OpenAI generator — the product-under-test runs on GPT (cross-provider demo).

Pairs with the Claude judge so a model never grades its own output. Requires the
`[real]` extra (`pip install 'cigate[real]'`) and `OPENAI_API_KEY`.
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
    from openai import OpenAI  # lazy import; only needed in real OpenAI mode

    prompt = get_answer_prompt(config.active_prompt_version())
    client = OpenAI()
    model = config.gen_model()
    retrieved_ids = [h.doc_id for h in hits]
    user = (
        f"Customer question:\n{question}\n\n"
        f"Policy excerpts:\n{_context(hits)}\n\n"
        "Answer the question."
    )
    resp = client.chat.completions.create(
        model=model,
        max_tokens=600,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": user},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    citations = list(dict.fromkeys(_CITE.findall(text)))
    usage = getattr(resp, "usage", None)
    meta = {
        "flavor": prompt.get("flavor", "good"),
        "provider": "openai",
        "model": model,
        "input_tokens": getattr(usage, "prompt_tokens", 0),
        "output_tokens": getattr(usage, "completion_tokens", 0),
    }
    return SUTOutput(text=text, citations=citations, retrieved_ids=retrieved_ids,
                     prompt_version=prompt["version"], meta=meta)
