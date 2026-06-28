"""refbot — the reference RAG answer-bot used as CIGate's system-under-test.

A small contract/insurance support bot: BM25 retrieval over a document corpus plus a
generator that is either real (Claude) or a deterministic mock. The mock has a
``good`` and a ``regressed`` build flavor so the demo can show a real, reproducible
quality regression with no API calls.
"""

from __future__ import annotations

__version__ = "0.1.0"
