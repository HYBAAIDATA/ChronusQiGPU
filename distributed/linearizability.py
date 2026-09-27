"""Q3 — sequential specification + interleaving checker for the seam queue."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations
from typing import List, Optional, Tuple


@dataclass
class SpecQueue:
    pending: List[str] = field(default_factory=list)
    in_flight: List[str] = field(default_factory=list)
    seen: dict = field(default_factory=dict)
    threshold: int = 2

    def enqueue(self, key: str, item_id: str) -> str:
        if key in self.seen:
            return self.seen[key]
        if len(self.in_flight) >= self.threshold:
            raise RuntimeError("rate_limited")
        self.pending.append(item_id)
        self.seen[key] = item_id
        return item_id

    def dequeue(self) -> Optional[str]:
        if not self.pending:
            return None
        item = self.pending.pop(0)
        self.in_flight.append(item)
        return item


Op = Tuple[str, tuple]


def apply_ops(ops: List[Op]) -> Optional[List[str]]:
    q = SpecQueue()
    log: List[str] = []
    try:
        for name, args in ops:
            if name == "enq":
                log.append("enq:" + q.enqueue(args[0], args[1]))
            else:
                got = q.dequeue()
                log.append("deq:" + (got or "none"))
    except RuntimeError:
        return None
    return log


def linearizable(history: List[Op]) -> bool:
    if len(history) > 8:
        raise ValueError("bound histories to 8 ops")
    for perm in permutations(history):
        if apply_ops(list(perm)) is not None:
            return True
    return False


def check_q3() -> bool:
    h1: List[Op] = [("enq", ("k1", "a")), ("enq", ("k1", "a")), ("deq", ())]
    h2: List[Op] = [("enq", ("k1", "a")), ("enq", ("k2", "b")), ("deq", ()), ("deq", ())]
    h3: List[Op] = [("deq", ()), ("enq", ("k1", "a"))]
    assert linearizable(h1)
    assert linearizable(h2)
    assert linearizable(h3)
    spec = SpecQueue()
    first = spec.enqueue("k", "id1")
    second = spec.enqueue("k", "id2")
    assert first == second == "id1"
    spec2 = SpecQueue(threshold=1)
    spec2.in_flight.append("busy")
    raised = False
    try:
        spec2.enqueue("n", "x")
    except RuntimeError:
        raised = True
    assert raised
    return True
