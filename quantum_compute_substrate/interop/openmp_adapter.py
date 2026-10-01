"""OpenMP-style parallelism adapter.

Uses `joblib.Parallel` if available, otherwise a ThreadPoolExecutor. Does NOT
require compiling C extensions; relies on Python-level threads plus BLAS.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, List, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class OpenMPAdapter:
    def __init__(self, n_threads: int | None = None) -> None:
        self.n_threads = n_threads or int(os.environ.get("OMP_NUM_THREADS", "4"))
        try:
            import joblib  # noqa: F401

            self.backend = "joblib"
        except ImportError:
            self.backend = "threadpool"

    def parallel_map(self, fn: Callable[[T], R], items: Iterable[T]) -> List[R]:
        items_list = list(items)
        if self.backend == "joblib":
            import joblib

            return list(
                joblib.Parallel(n_jobs=self.n_threads)(joblib.delayed(fn)(x) for x in items_list)
            )
        with ThreadPoolExecutor(max_workers=self.n_threads) as ex:
            return list(ex.map(fn, items_list))

    def status(self) -> dict:
        return {"n_threads": self.n_threads, "backend": self.backend}
