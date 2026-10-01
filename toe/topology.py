"""Operational topological/geometric intelligence — §32.

The question the brief asks: what can topology/geometry ANSWER
operationally? On a declared state-transition graph the answers are
concrete and checkable: connected components, reachability, boundary
states, articulation/bottleneck states, path existence — questions a
feature-distance baseline cannot answer (two states can be
metric-close and topologically disconnected, e.g. separated by a wall).

``StateTopology`` is domain-general: feed any transition relation.
``reachability_task`` is the ground-truth test harness comparing it to
the honest non-topological baseline (greedy Euclidean descent), which
fails exactly when geometry is not topology.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

TOPOLOGY_VERSION = "toe.topology/v1"


class StateTopology:
    """Discrete topology over a declared transition relation.

    ``states``: hashable state identifiers. ``transitions``: iterable of
    (from, to) directed edges — the system's neighbourhood structure.
    """

    def __init__(
        self,
        states: List[Any],
        transitions: List[Tuple[Any, Any]],
    ) -> None:
        self.states = list(states)
        self.adj: Dict[Any, Set[Any]] = {s: set() for s in states}
        self.rev: Dict[Any, Set[Any]] = {s: set() for s in states}
        for a, b in transitions:
            self.adj.setdefault(a, set()).add(b)
            self.rev.setdefault(b, set()).add(a)
            self.adj.setdefault(b, set())
            self.rev.setdefault(a, set())

    def components(self) -> List[Set[Any]]:
        """Weakly-connected components of the state space."""
        seen: Set[Any] = set()
        comps: List[Set[Any]] = []
        for s in self.states:
            if s in seen:
                continue
            comp: Set[Any] = set()
            q = deque([s])
            while q:
                u = q.popleft()
                if u in comp:
                    continue
                comp.add(u)
                q.extend(self.adj.get(u, ()) | self.rev.get(u, ()) - comp)
            comps.append(comp)
            seen |= comp
        return comps

    def reachable(self, source: Any) -> Set[Any]:
        """Directed reachability — states enterable from ``source``."""
        seen: Set[Any] = set()
        q = deque([source])
        while q:
            u = q.popleft()
            if u in seen:
                continue
            seen.add(u)
            q.extend(self.adj.get(u, ()) - seen)
        return seen

    def path_exists(self, source: Any, target: Any) -> bool:
        return target in self.reachable(source)

    def shortest_path(self, source: Any, target: Any) -> Optional[List[Any]]:
        q = deque([(source, [source])])
        seen = {source}
        while q:
            u, path = q.popleft()
            if u == target:
                return path
            for v in self.adj.get(u, ()) - seen:
                seen.add(v)
                q.append((v, path + [v]))
        return None

    def boundary_states(self) -> List[Any]:
        """Frontier states: have an outgoing edge but no incoming one
        (entry-only boundaries), or vice-versa (exit-only)."""
        return [
            s
            for s in self.states
            if bool(self.adj.get(s)) != bool(self.rev.get(s))
        ]

    def articulation_points(self) -> List[Any]:
        """States whose removal increases the component count — the
        bottlenecks any plan crossing components must pass through."""
        base = len(self.components())
        out = []
        for s in self.states:
            rest = [x for x in self.states if x != s]
            sub = StateTopology(
                rest,
                [(a, b) for a, outs in self.adj.items()
                 for b in outs if a != s and b != s],
            )
            if len(sub.components()) > base:
                out.append(s)
        return out


def reachability_task(
    states: List[Any],
    transitions: List[Tuple[Any, Any]],
    source: Any,
    target: Any,
    *,
    coords: Optional[Mapping[Any, Tuple[float, float]]] = None,
) -> Dict[str, Any]:
    """Ground-truth task: is ``target`` reachable from ``source``?

    The topological answer is exact (directed reachability). The
    non-topological baseline is greedy Euclidean descent on ``coords``:
    it declares reachability iff greedy descent reaches the target —
    and fails on wall-separated points where geometry misleads.
    """
    topo = StateTopology(states, transitions)
    truth = topo.path_exists(source, target)
    path = topo.shortest_path(source, target)

    baseline_answer: Optional[bool] = None
    baseline_path: Optional[List[Any]] = None
    if coords is not None:
        cur, seen_b, walk = source, {source}, [source]
        while cur != target:
            nxt = min(
                (n for n in topo.adj.get(cur, set()) if n not in seen_b),
                key=lambda n: (coords[n][0] - coords[target][0]) ** 2
                + (coords[n][1] - coords[target][1]) ** 2,
                default=None,
            )
            if nxt is None:
                break
            seen_b.add(nxt)
            walk.append(nxt)
            cur = nxt
        baseline_answer = cur == target
        baseline_path = walk
    return {
        "version": TOPOLOGY_VERSION,
        "reachable": truth,
        "topological_path": path,
        "baseline_answer": baseline_answer,
        "baseline_path": baseline_path,
        "baseline_correct": (
            baseline_answer == truth if baseline_answer is not None else None
        ),
        "components": [sorted(c, key=str) for c in topo.components()],
        "articulation_points": topo.articulation_points(),
    }


__all__ = [
    "TOPOLOGY_VERSION",
    "StateTopology",
    "reachability_task",
]
