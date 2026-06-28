"""Internal retrieval types for the reference bot.

These are *refbot* implementation details. The boundary CIGate sees is
``cigate.types.SUTOutput``, returned by ``refbot.pipeline.rag_answer``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Doc:
    """A document in the corpus the retriever indexes."""

    id: str
    title: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Hit:
    """A retrieved document with its relevance score."""

    doc_id: str
    score: float
    text: str
    title: str = ""
