"""The reference bot's RAG pipeline — this is CIGate's system-under-test.

``rag_answer`` is the callable referenced in ``evalconfig.yaml`` as
``refbot.pipeline:rag_answer``. Signature is the SUT contract: it takes the question
plus optional context and returns a ``cigate.types.SUTOutput``.
"""

from __future__ import annotations

from functools import lru_cache

from cigate.types import Case, SUTOutput

from . import generator
from .retriever import BM25Retriever

DEFAULT_CORPUS = "goldensets/corpus"
TOP_K = 5


@lru_cache(maxsize=8)
def _retriever(corpus_dir: str) -> BM25Retriever:
    return BM25Retriever.from_dir(corpus_dir)


def rag_answer(
    question: str,
    *,
    corpus_dir: str = DEFAULT_CORPUS,
    case: Case | None = None,
    k: int = TOP_K,
    **_ctx,
) -> SUTOutput:
    hits = _retriever(corpus_dir).search(question, k=k)
    return generator.generate(question, hits, case)
