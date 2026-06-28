"""Minimal corpus loader for judge context.

The judge needs the text of the retrieved documents to assess grounding/citations.
Corpus is a directory of ``<id>.md`` files with ``id``/``title`` frontmatter (the same
format the reference bot indexes). Optional: products without a document corpus simply
leave ``corpus`` unset and the judge falls back to the answer + reference answer.
"""

from __future__ import annotations

from pathlib import Path


def _parse(raw: str, fallback_id: str) -> tuple[str, str, str]:
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
    return doc_id, title, body.strip()


def load_corpus(corpus_dir: str | Path) -> dict[str, dict[str, str]]:
    """Return ``{doc_id: {"title": ..., "text": ...}}`` (empty if dir missing)."""
    d = Path(corpus_dir)
    if not d.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    for p in sorted(d.glob("*.md")):
        doc_id, title, body = _parse(p.read_text(), p.stem)
        out[doc_id] = {"title": title, "text": body}
    return out
