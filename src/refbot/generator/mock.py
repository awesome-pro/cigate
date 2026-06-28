"""Deterministic mock generator — the offline, $0 system-under-test.

It is a pure function of ``(case, hits, flavor, seed)``, so the demo's red/green CI
flip is perfectly reproducible with no API calls. In mock mode the runner passes the
golden ``case`` so the generator can act as an oracle and record the *true* per-axis
outcome of its own output in ``SUTOutput.meta["truth"]`` — that ground truth is what
the mock judge later corrupts through a configured confusion matrix, giving the
statistical-correction layer real, known bias to recover.

The ``good`` flavor grounds in the gold document, cites it, and abstains correctly.
The ``regressed`` flavor degrades a tunable fraction of cases (drops citations, grounds
in the wrong document, fabricates instead of abstaining) — the kind of silent quality
regression an eval gate must catch.
"""

from __future__ import annotations

import hashlib

from cigate.taxonomy import ALL_AXIS_KEYS
from cigate.types import Case, SUTOutput

from ..interfaces import Hit

ABSTENTION = "I could not find this in the available policy documents."


def _unit(*parts: object) -> float:
    """Deterministic float in [0, 1) from the given parts."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _lead_sentence(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    for end in (". ", "; ", ": "):
        i = text.find(end)
        if 40 <= i <= limit:
            return text[: i + 1].strip()
    return text[:limit].strip()


def _all_true() -> dict[str, bool]:
    return {a: True for a in ALL_AXIS_KEYS}


def generate(question: str, hits: list[Hit], case: Case, flavor: str, seed: int,
             regression_rate: float) -> SUTOutput:
    retrieved_ids = [h.doc_id for h in hits]
    truth = _all_true()
    pv = "answer_v1" if flavor == "good" else "answer_v2"

    gold = case.gold_doc_ids[0] if case.gold_doc_ids else None
    gold_hit = next((h for h in hits if gold and h.doc_id == gold), None)

    # ---- out-of-corpus: the correct behavior is to abstain --------------- #
    if not case.in_corpus or not gold:
        if flavor == "regressed" and _unit(seed, "abstain", case.id) < regression_rate:
            # Fabricate instead of abstaining -> wrong refusal + hallucination.
            wrong = hits[0] if hits else None
            text = (
                f"Yes — {_lead_sentence(wrong.text)}" if wrong
                else "Yes, your policy generally covers this in most standard cases."
            )
            truth["refusal"] = False
            truth["hallucination"] = False
            return SUTOutput(text=text, citations=[], retrieved_ids=retrieved_ids,
                             prompt_version=pv, meta={"truth": truth, "flavor": flavor})
        return SUTOutput(text=ABSTENTION, citations=[], retrieved_ids=retrieved_ids,
                         prompt_version=pv, meta={"truth": truth, "flavor": flavor})

    # ---- in-corpus -------------------------------------------------------- #
    grounding = gold_hit or (hits[0] if hits else None)
    if grounding is None:
        # Retrieval found nothing for an answerable question.
        truth["retrieval_miss"] = False
        return SUTOutput(text=ABSTENTION, citations=[], retrieved_ids=retrieved_ids,
                         prompt_version=pv, meta={"truth": truth, "flavor": flavor})

    degrade = flavor == "regressed" and _unit(seed, "degrade", case.id) < regression_rate
    if not degrade:
        text = f"{_lead_sentence(grounding.text)} [{gold}]"
        truth["retrieval_miss"] = gold in retrieved_ids
        return SUTOutput(text=text, citations=[gold], retrieved_ids=retrieved_ids,
                         prompt_version=pv, meta={"truth": truth, "flavor": flavor})

    # Regressed: ground in a WRONG document and drop the citation.
    wrong_hit = next((h for h in hits if h.doc_id != gold), grounding)
    text = _lead_sentence(wrong_hit.text)  # no citation, ungrounded vs gold
    truth["hallucination"] = False
    truth["citation_error"] = False
    return SUTOutput(text=text, citations=[], retrieved_ids=retrieved_ids,
                     prompt_version=pv, meta={"truth": truth, "flavor": flavor})
