"""System-under-test (SUT) adapter loader.

CIGate is product-agnostic: it evaluates *any* callable of the form

    (question: str, *, corpus_dir: str | None = None, **ctx) -> SUTOutput

referenced in ``evalconfig.yaml`` as ``"module.path:callable"`` (e.g.
``"refbot.pipeline:rag_answer"``). Swap that one string to gate a different product.
"""

from __future__ import annotations

import importlib
from typing import Callable

from .types import SUTOutput

SUTCallable = Callable[..., SUTOutput]


def load_sut(ref: str) -> SUTCallable:
    """Resolve a ``"module.path:callable"`` reference to the callable."""
    if ":" not in ref:
        raise ValueError(f"SUT reference must be 'module.path:callable', got: {ref!r}")
    module_path, _, attr = ref.partition(":")
    module = importlib.import_module(module_path)
    fn = getattr(module, attr, None)
    if fn is None or not callable(fn):
        raise ValueError(f"SUT callable {attr!r} not found in module {module_path!r}")
    return fn


def load_object(ref: str):
    """Resolve a ``"module.path:attr"`` reference to any object (e.g. the judge prompt)."""
    module_path, _, attr = ref.partition(":")
    return getattr(importlib.import_module(module_path), attr)
