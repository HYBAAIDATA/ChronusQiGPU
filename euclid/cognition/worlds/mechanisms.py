"""Mechanism grammar: the exact semantics behind every task world.

A *mechanism* is a deterministic transformation of a finite discrete state
``x ∈ Z_{m_0} × … × Z_{m_{n-1}}``.  Worlds hide one mechanism behind every
operator name; agents must infer it from interventions.  The same grammar is
used by the environment generator and (independently) by the agent's
hypothesis space, but the two are configured separately so a world can contain
mechanisms *outside* the agent's grammar — the model-breakdown case.

Everything here is exact integer arithmetic.  Description length is the
number of grammar symbols a mechanism needs; it defines the Occam prior and
nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations
from typing import Iterable, Iterator, Mapping, Sequence

State = tuple[int, ...]

SIMPLE_KINDS = ("noop", "add", "set", "copy", "swap")
#: kinds an agent may hypothesise by default (guard inner is add/set only)
DEFAULT_AGENT_KINDS = frozenset({"noop", "add", "set", "copy", "swap", "guard"})
#: kinds only reachable after an explicit grammar expansion
EXPANDED_AGENT_KINDS = DEFAULT_AGENT_KINDS | frozenset({"pair"})


@dataclass(frozen=True)
class Mechanism:
    """One exact, hashable state transformation.

    ``params`` meaning by kind:

    * ``noop``  — ``()``
    * ``add``   — ``(i, c)``: ``x_i ← (x_i + c) mod m_i`` with ``0 < c < m_i``
    * ``set``   — ``(i, v)``: ``x_i ← v``
    * ``copy``  — ``(i, j)``: ``x_j ← x_i mod m_j`` (source ``i``, target ``j``)
    * ``swap``  — ``(i, j)``: exchange ``x_i`` and ``x_j`` (``i < j``, equal domains)
    * ``guard`` — ``(k, v)`` with ``inner``: apply ``inner`` iff ``x_k == v``
    * ``pair``  — ``()`` with ``inner`` and ``second``: two independent writes
    """

    kind: str
    params: tuple[int, ...] = ()
    inner: "Mechanism | None" = field(default=None, compare=True)
    second: "Mechanism | None" = field(default=None, compare=True)

    def __post_init__(self) -> None:
        if self.kind not in SIMPLE_KINDS + ("guard", "pair"):
            raise ValueError(f"unknown mechanism kind {self.kind!r}")
        arity = {"noop": 0, "add": 2, "set": 2, "copy": 2, "swap": 2, "guard": 2, "pair": 0}
        if len(self.params) != arity[self.kind]:
            raise ValueError(f"{self.kind} requires {arity[self.kind]} parameters")
        if self.kind == "guard" and (self.inner is None or self.inner.kind not in SIMPLE_KINDS):
            raise ValueError("guard requires a simple inner mechanism")
        if self.kind == "pair" and (
            self.inner is None
            or self.second is None
            or self.inner.kind not in SIMPLE_KINDS
            or self.second.kind not in SIMPLE_KINDS
        ):
            raise ValueError("pair requires two simple mechanisms")
        if self.kind == "copy" and self.params[0] == self.params[1]:
            raise ValueError("copy source and target must differ")
        if self.kind == "swap" and not self.params[0] < self.params[1]:
            raise ValueError("swap requires i < j")

    # -- semantics ------------------------------------------------------------
    def apply(self, state: State, domains: Sequence[int]) -> State:
        kind = self.kind
        if kind == "noop":
            return state
        if kind == "add":
            i, c = self.params
            values = list(state)
            values[i] = (values[i] + c) % domains[i]
            return tuple(values)
        if kind == "set":
            i, v = self.params
            if state[i] == v:
                return state
            values = list(state)
            values[i] = v
            return tuple(values)
        if kind == "copy":
            i, j = self.params
            target = state[i] % domains[j]
            if state[j] == target:
                return state
            values = list(state)
            values[j] = target
            return tuple(values)
        if kind == "swap":
            i, j = self.params
            if state[i] == state[j]:
                return state
            values = list(state)
            values[i], values[j] = values[j], values[i]
            return tuple(values)
        if kind == "guard":
            k, v = self.params
            return self.inner.apply(state, domains) if state[k] == v else state
        # pair: both writes read the pre-state (simultaneous assignment)
        first = self.inner.apply(state, domains)
        second = self.second.apply(state, domains)
        values = list(state)
        for index in self.inner.writes():
            values[index] = first[index]
        for index in self.second.writes():
            values[index] = second[index]
        return tuple(values)

    def writes(self) -> frozenset[int]:
        kind = self.kind
        if kind in ("add", "set"):
            return frozenset({self.params[0]})
        if kind == "copy":
            return frozenset({self.params[1]})
        if kind == "swap":
            return frozenset(self.params)
        if kind == "guard":
            return self.inner.writes()
        if kind == "pair":
            return self.inner.writes() | self.second.writes()
        return frozenset()

    def reads(self) -> frozenset[int]:
        kind = self.kind
        if kind == "add":
            return frozenset({self.params[0]})
        if kind == "copy":
            return frozenset({self.params[0]})
        if kind == "swap":
            return frozenset(self.params)
        if kind == "guard":
            return frozenset({self.params[0]}) | self.inner.reads()
        if kind == "pair":
            return self.inner.reads() | self.second.reads()
        return frozenset()

    def description_length(self) -> int:
        """Grammar symbols needed to state the mechanism (Occam prior basis)."""
        if self.kind == "noop":
            return 1
        if self.kind in ("guard",):
            return 3 + self.inner.description_length()
        if self.kind == "pair":
            return 1 + self.inner.description_length() + self.second.description_length()
        return 3

    # -- abstraction ------------------------------------------------------------
    def abstract(self, roles: Mapping[int, str]) -> tuple:
        """Vocabulary-free signature with variables replaced by role names."""
        kind = self.kind
        if kind == "noop":
            return ("noop",)
        if kind in ("add", "set"):
            return (kind, roles[self.params[0]], self.params[1])
        if kind in ("copy", "swap"):
            return (kind, roles[self.params[0]], roles[self.params[1]])
        if kind == "guard":
            return ("guard", roles[self.params[0]], self.params[1], self.inner.abstract(roles))
        return ("pair", self.inner.abstract(roles), self.second.abstract(roles))

    def remap(self, mapping: Mapping[int, int]) -> "Mechanism":
        """Rename variables (used to transport mechanisms across analogies)."""
        kind = self.kind
        if kind == "noop":
            return self
        if kind in ("add", "set"):
            return Mechanism(kind, (mapping[self.params[0]], self.params[1]))
        if kind == "copy":
            return Mechanism(kind, (mapping[self.params[0]], mapping[self.params[1]]))
        if kind == "swap":
            a, b = sorted((mapping[self.params[0]], mapping[self.params[1]]))
            return Mechanism(kind, (a, b))
        if kind == "guard":
            return Mechanism(
                kind, (mapping[self.params[0]], self.params[1]), self.inner.remap(mapping)
            )
        return Mechanism(kind, (), self.inner.remap(mapping), self.second.remap(mapping))

    def valid_for(self, domains: Sequence[int]) -> bool:
        """Whether the mechanism is well-formed over the given domains."""
        n = len(domains)
        kind = self.kind
        try:
            if kind == "noop":
                return True
            if kind == "add":
                i, c = self.params
                return 0 <= i < n and 0 < c < domains[i]
            if kind == "set":
                i, v = self.params
                return 0 <= i < n and 0 <= v < domains[i]
            if kind == "copy":
                i, j = self.params
                return 0 <= i < n and 0 <= j < n and i != j
            if kind == "swap":
                i, j = self.params
                return 0 <= i < j < n and domains[i] == domains[j]
            if kind == "guard":
                k, v = self.params
                return (
                    0 <= k < n
                    and 0 <= v < domains[k]
                    and k not in self.inner.writes()
                    and self.inner.valid_for(domains)
                )
            return (
                self.inner.valid_for(domains)
                and self.second.valid_for(domains)
                and not (self.inner.writes() & self.second.writes())
            )
        except (IndexError, TypeError):
            return False

    def describe(self, variables: Sequence[str] | None = None) -> str:
        name = (lambda i: variables[i]) if variables else (lambda i: f"x{i}")
        kind = self.kind
        if kind == "noop":
            return "noop"
        if kind == "add":
            return f"{name(self.params[0])} += {self.params[1]}"
        if kind == "set":
            return f"{name(self.params[0])} := {self.params[1]}"
        if kind == "copy":
            return f"{name(self.params[1])} := {name(self.params[0])}"
        if kind == "swap":
            return f"swap({name(self.params[0])}, {name(self.params[1])})"
        if kind == "guard":
            return (
                f"if {name(self.params[0])} == {self.params[1]}: "
                f"{self.inner.describe(variables)}"
            )
        return f"({self.inner.describe(variables)}) || ({self.second.describe(variables)})"

    def to_json(self) -> list:
        body: list = [self.kind, list(self.params)]
        if self.inner is not None:
            body.append(self.inner.to_json())
        if self.second is not None:
            body.append(self.second.to_json())
        return body

    @classmethod
    def from_json(cls, payload: Sequence) -> "Mechanism":
        kind = str(payload[0])
        params = tuple(int(p) for p in payload[1])
        inner = cls.from_json(payload[2]) if len(payload) > 2 else None
        second = cls.from_json(payload[3]) if len(payload) > 3 else None
        return cls(kind, params, inner, second)


def _simple(domains: Sequence[int], kinds: Iterable[str]) -> Iterator[Mechanism]:
    n = len(domains)
    kinds = set(kinds)
    if "noop" in kinds:
        yield Mechanism("noop")
    if "add" in kinds:
        for i in range(n):
            for c in range(1, domains[i]):
                yield Mechanism("add", (i, c))
    if "set" in kinds:
        for i in range(n):
            for v in range(domains[i]):
                yield Mechanism("set", (i, v))
    if "copy" in kinds:
        for i, j in permutations(range(n), 2):
            yield Mechanism("copy", (i, j))
    if "swap" in kinds:
        for i in range(n):
            for j in range(i + 1, n):
                if domains[i] == domains[j]:
                    yield Mechanism("swap", (i, j))


def hypothesis_space(
    domains: Sequence[int],
    kinds: Iterable[str] = DEFAULT_AGENT_KINDS,
    *,
    guard_inner_kinds: Iterable[str] = ("add", "set"),
) -> list[Mechanism]:
    """Enumerate every mechanism of the given kinds over ``domains``.

    The enumeration is deterministic (stable order) so posterior indices and
    seeded experiments are reproducible.
    """
    kinds = frozenset(kinds)
    simple = list(_simple(domains, kinds & set(SIMPLE_KINDS)))
    space = list(simple)
    if "guard" in kinds:
        inner_pool = list(_simple(domains, guard_inner_kinds))
        for k in range(len(domains)):
            for v in range(domains[k]):
                for inner in inner_pool:
                    if inner.kind == "noop" or k in inner.writes():
                        continue
                    space.append(Mechanism("guard", (k, v), inner))
    if "pair" in kinds:
        pool = [m for m in _simple(domains, ("add",))]
        for a_index, first in enumerate(pool):
            for second in pool[a_index + 1:]:
                if first.writes() & second.writes():
                    continue
                space.append(Mechanism("pair", (), first, second))
    return space


def run_program(
    mechanisms: Mapping[str, Mechanism],
    program: Sequence[str],
    state: State,
    domains: Sequence[int],
) -> list[State]:
    """Exact trajectory (excluding the start state) of a program."""
    trajectory = []
    for op in program:
        state = mechanisms[op].apply(state, domains)
        trajectory.append(state)
    return trajectory


def canonical_roles(variables: Sequence[int]) -> dict[int, str]:
    """Role names in first-occurrence order (``r0``, ``r1``, …)."""
    roles: dict[int, str] = {}
    for index in variables:
        if index not in roles:
            roles[index] = f"r{len(roles)}"
    return roles


def mechanism_variables(mechanism: Mechanism) -> list[int]:
    """Variables touched by a mechanism in a deterministic order."""
    order: list[int] = []
    kind = mechanism.kind
    if kind in ("add", "set"):
        order.append(mechanism.params[0])
    elif kind in ("copy", "swap"):
        order.extend(mechanism.params)
    elif kind == "guard":
        order.append(mechanism.params[0])
        order.extend(mechanism_variables(mechanism.inner))
    elif kind == "pair":
        order.extend(mechanism_variables(mechanism.inner))
        order.extend(mechanism_variables(mechanism.second))
    return order


__all__ = [
    "DEFAULT_AGENT_KINDS",
    "EXPANDED_AGENT_KINDS",
    "Mechanism",
    "SIMPLE_KINDS",
    "State",
    "canonical_roles",
    "hypothesis_space",
    "mechanism_variables",
    "run_program",
]
