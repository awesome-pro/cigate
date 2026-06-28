"""Code-based (deterministic, $0) evaluators.

These own the cheap, objective axes and the deterministic *part* of the "both" axes.
They take the system output plus the case's ground truth (gold docs, answerability) and
return a pass/fail per axis. No LLM, so no statistical correction is needed for the
parts they own — but the uniform pipeline still runs them through the same machinery
(their measured TPR/TNR on the calibration set come out near 1.0).
"""

from __future__ import annotations

import re

from ..types import Case, SUTOutput

ABSTENTION_MARKERS = (
    "could not find",
    "couldn't find",
    "not contained in",
    "no relevant",
    "unable to find",
)
_CITE_TOKEN = re.compile(r"\[([a-z0-9][a-z0-9\-]+)\]")


def looks_like_abstention(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in ABSTENTION_MARKERS)


def _format_ok(output: SUTOutput, case: Case) -> bool:
    text = output.text.strip()
    if not text:
        return False
    if looks_like_abstention(text):
        return True  # abstention is a valid format
    # Structural check only (citation *presence* is citation_error's concern, not format's):
    # any bracketed tokens must be well-formed doc-id references.
    brackets = re.findall(r"\[([^\]]*)\]", text)
    return all(_CITE_TOKEN.fullmatch(f"[{b}]") for b in brackets)


def _citation_ok(output: SUTOutput, case: Case, valid_ids: set[str]) -> bool:
    cites = set(output.citations)
    if not case.in_corpus or not case.gold_doc_ids:
        # Correct behavior is to abstain -> no citations.
        return len(cites) == 0
    if not cites:
        return False
    if not cites.issubset(valid_ids):          # cites a non-existent document
        return False
    return bool(cites & set(case.gold_doc_ids))  # at least one gold source cited


def _retrieval_ok(output: SUTOutput, case: Case) -> bool:
    if not case.in_corpus or not case.gold_doc_ids:
        return True
    return bool(set(case.gold_doc_ids) & set(output.retrieved_ids))


def code_verdicts(output: SUTOutput, case: Case, valid_ids: set[str]) -> dict[str, bool]:
    """Deterministic pass/fail for code-owned and code-part-of-both axes."""
    return {
        "format_violation": _format_ok(output, case),
        "citation_error": _citation_ok(output, case, valid_ids),
        "retrieval_miss": _retrieval_ok(output, case),
    }
