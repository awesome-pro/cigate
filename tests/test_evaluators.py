"""Tests for the deterministic code-based evaluators."""

from __future__ import annotations

from cigate.evaluators.code_based import code_verdicts, looks_like_abstention
from cigate.types import Case, SUTOutput

VALID = {"d1", "d2", "d3"}


def _case(in_corpus=True, gold=("d1",)):
    return Case(id="x", question="q", gold_doc_ids=list(gold), in_corpus=in_corpus)


def test_good_in_corpus_answer_passes_all():
    out = SUTOutput(text="The deductible is $500 [d1]", citations=["d1"],
                    retrieved_ids=["d1", "d2"])
    v = code_verdicts(out, _case(), VALID)
    assert v["citation_error"] and v["retrieval_miss"] and v["format_violation"]


def test_missing_citation_fails_only_citation():
    out = SUTOutput(text="The deductible is $500", citations=[], retrieved_ids=["d1"])
    v = code_verdicts(out, _case(), VALID)
    assert not v["citation_error"]      # no citation
    assert v["retrieval_miss"]          # gold still retrieved
    assert v["format_violation"]        # well-formed prose, format is fine


def test_wrong_citation_fails():
    out = SUTOutput(text="answer [d3]", citations=["d3"], retrieved_ids=["d1"])
    v = code_verdicts(out, _case(), VALID)
    assert not v["citation_error"]      # cited a non-gold doc


def test_retrieval_miss_when_gold_not_retrieved():
    out = SUTOutput(text="answer [d2]", citations=["d2"], retrieved_ids=["d2", "d3"])
    v = code_verdicts(out, _case(), VALID)
    assert not v["retrieval_miss"]      # gold d1 absent from retrieval


def test_out_of_corpus_abstention_passes():
    out = SUTOutput(text="I could not find this in the available policy documents.",
                    citations=[], retrieved_ids=["d1"])
    v = code_verdicts(out, _case(in_corpus=False, gold=()), VALID)
    assert v["citation_error"] and v["retrieval_miss"] and v["format_violation"]
    assert looks_like_abstention(out.text)


def test_out_of_corpus_fabrication_fails_citation():
    out = SUTOutput(text="Yes, you are fully covered [d1]", citations=["d1"],
                    retrieved_ids=["d1"])
    v = code_verdicts(out, _case(in_corpus=False, gold=()), VALID)
    assert not v["citation_error"]      # should have abstained, cited instead


def test_malformed_brackets_fail_format():
    out = SUTOutput(text="answer [not a valid id!]", citations=[], retrieved_ids=["d1"])
    v = code_verdicts(out, _case(), VALID)
    assert not v["format_violation"]
