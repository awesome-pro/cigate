"""Generator factory — mock (deterministic, $0) vs real (Claude)."""

from __future__ import annotations

from cigate.types import Case, SUTOutput

from .. import config
from ..interfaces import Hit


def generate(question: str, hits: list[Hit], case: Case | None = None) -> SUTOutput:
    if config.mock_mode():
        if case is None:
            # The mock generator needs the case as its truth oracle. Synthesize a
            # minimal in-corpus case from the top hit so ad-hoc CLI queries still work.
            top = hits[0].doc_id if hits else None
            case = Case(id="adhoc", question=question,
                        gold_doc_ids=[top] if top else [], in_corpus=bool(top))
        from . import mock
        return mock.generate(question, hits, case, config.flavor(), config.seed(),
                             config.regression_rate())
    from . import real
    return real.generate(question, hits, case)
