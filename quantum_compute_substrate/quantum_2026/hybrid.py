"""Hybrid quantum-classical feedback loop."""
from __future__ import annotations
import time
from typing import Any, Callable, Dict, List


class ModernHybrid:
    def __init__(self, num_processors: int = 1) -> None:
        self.num_processors = num_processors

    def loop(self, problem: Dict[str, Any],
             pre: Callable[[Dict[str, Any]], Dict[str, Any]] = lambda x: x,
             q: Callable[[Dict[str, Any]], Dict[str, Any]] = lambda x: x,
             post: Callable[[Dict[str, Any]], Dict[str, Any]] = lambda x: x,
             max_iter: int = 5) -> Dict[str, Any]:
        iters: List[int] = []
        qt: List[float] = []
        ct: List[float] = []
        tt: List[float] = []
        for i in range(max_iter):
            t0 = time.perf_counter()
            pre_res = pre(problem)
            c1 = time.perf_counter() - t0
            t0 = time.perf_counter()
            q_res = q(pre_res)
            qtime = time.perf_counter() - t0
            t0 = time.perf_counter()
            problem = post(q_res)
            c2 = time.perf_counter() - t0
            iters.append(i)
            qt.append(qtime)
            ct.append(c1 + c2)
            tt.append(qtime + c1 + c2)
        return {"iterations": iters, "quantum_times": qt, "classical_times": ct, "total_times": tt}
