"""Deterministic BM25 retrieval over a corpus of markdown documents.

Corpus format: a directory of ``<doc_id>.md`` files, each with YAML frontmatter::

    ---
    id: auto-collision-deductible-001
    title: Auto Insurance — Collision Coverage Deductible
    ---
    <body text>

BM25 is lexical, offline, and fully deterministic — ideal for a reproducible demo
(and strong on the keyword-heavy phrasing of contract/policy questions).
"""

from __future__ import annotations

import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from .interfaces import Doc, Hit

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _parse_frontmatter(raw: str, fallback_id: str) -> Doc:
    doc_id, title, body = fallback_id, fallback_id, raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) == 3:
            header, body = parts[1], parts[2]
            for line in header.strip().splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    key, val = key.strip(), val.strip()
                    if key == "id":
                        doc_id = val
                    elif key == "title":
                        title = val
    return Doc(id=doc_id, title=title, text=body.strip())


def load_corpus(corpus_dir: str | Path) -> list[Doc]:
    """Load all ``*.md`` documents from a directory, sorted by id for determinism."""
    d = Path(corpus_dir)
    if not d.exists():
        raise FileNotFoundError(f"corpus dir not found: {d}")
    docs = [_parse_frontmatter(p.read_text(), p.stem) for p in sorted(d.glob("*.md"))]
    if not docs:
        raise ValueError(f"no .md documents found in corpus dir: {d}")
    return docs


class BM25Retriever:
    """BM25 retriever with a stable, score-then-id tie-break for determinism."""

    def __init__(self, docs: list[Doc]):
        self.docs = docs
        self._index = {d.id: d for d in docs}
        self._bm25 = BM25Okapi([_tokenize(f"{d.title} {d.text}") for d in docs])

    @classmethod
    def from_dir(cls, corpus_dir: str | Path) -> "BM25Retriever":
        return cls(load_corpus(corpus_dir))

    def search(self, query: str, k: int = 5) -> list[Hit]:
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(
            zip(self.docs, scores), key=lambda ds: (-ds[1], ds[0].id)
        )
        return [
            Hit(doc_id=d.id, score=float(s), text=d.text, title=d.title)
            for d, s in ranked[:k]
        ]

    def get(self, doc_id: str) -> Doc | None:
        return self._index.get(doc_id)
