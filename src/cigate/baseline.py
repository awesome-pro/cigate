"""Baseline persistence.

The baseline is a committed JSON file on ``main`` (durable, diffable, versioned quality
history). PR runs read it; nightly / promote runs rewrite it.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_baseline(path: str | Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    text = p.read_text().strip()
    if not text or text == "{}":
        return None
    return json.loads(text)


def save_baseline(path: str | Path, doc: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n")
