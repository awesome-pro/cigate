"""Concurrent map with a lightweight progress counter.

Real-mode wall time is dominated by per-case LLM calls (the generator and the
judge), which are network-bound and independent across cases. Running them
sequentially makes a 166-item calibration take 10-15 minutes with no output, so it
looks hung. This maps the work over a small thread pool and prints a single-line
progress counter, cutting wall time ~5-8x while showing the run is alive.

Concurrency is capped via ``CIGATE_CONCURRENCY`` (default 8). Results preserve input
order, so aggregation and mock determinism are unaffected.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def _workers(default: int = 8) -> int:
    try:
        return max(1, int(os.environ.get("CIGATE_CONCURRENCY", str(default))))
    except ValueError:
        return default


def map_progress(
    fn: Callable[[T], R],
    items: Iterable[T],
    desc: str = "working",
    workers: int | None = None,
    show: bool | None = None,
) -> list[R | None]:
    """Apply ``fn`` to each item concurrently, preserving input order.

    Prints ``[desc] done/total`` to stderr as results complete (suppressed when not a
    TTY unless ``show`` forces it). An item whose ``fn`` raises is recorded as ``None``
    and its error printed, so one flaky API call can't abort a long run.
    """
    items = list(items)
    total = len(items)
    if total == 0:
        return []
    workers = workers or _workers()
    show = sys.stderr.isatty() if show is None else show
    results: list[R | None] = [None] * total
    done = 0

    def _tick() -> None:
        if show:
            sys.stderr.write(f"\r  [{desc}] {done}/{total}")
            sys.stderr.flush()

    with ThreadPoolExecutor(max_workers=min(workers, total)) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                results[i] = fut.result()
            except Exception as e:  # noqa: BLE001 — keep the run alive; report and skip
                if show:
                    sys.stderr.write(f"\r  [{desc}] item {i} failed: {type(e).__name__}: {e}\n")
            done += 1
            _tick()
    if show:
        sys.stderr.write("\n")
    return results
