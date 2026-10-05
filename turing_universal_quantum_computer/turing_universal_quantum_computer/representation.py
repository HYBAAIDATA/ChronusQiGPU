"""Representation planning for the TURING VQC (canonical workflow WF02).

The representation choice is a *proof-shaped* decision, not a heuristic:
each representation has a stated domain (state class + gate set + resource),
and automatic selection is only permitted where the dominance map shows a
strictly stronger representation available — otherwise the planner returns
the candidate set for a declared choice, never silently downgraded semantics.

Representations (canonical inventory):

* ``dense_algebraic``   — exact statevector over Q(sqrt(2)) + i*Q(sqrt(2));
  any Clifford+T program within the amplitude budget.  The universal
  reference representation.
* ``tableau``           — exact stabilizer tableau; Clifford programs at any
  width; not applicable once a non-Clifford gate appears.
* ``sparse_exact``      — exact sparse support; bounded-support states,
  Clifford+T gates with QuantumRegister bindings; support boundedness is
  enforced at run time, not provable statically.
* ``closed_form``       — symbolic evaluation of named families
  (hypercube/cycle walk, TFIM, Landau-Zener); no state materialised; the
  domain is the family, not the register.
* ``symbolic_density``  — symbolic density-operator semantics; selected only
  when a caller explicitly requires operator-level (not amplitude-level)
  reasoning and accepts symbolic cost.  RESERVED: not bound to a shipped
  backend; requests resolve to UNAVAILABLE rather than a silent substitute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .backends.base import CLIFFORD_GATES, Program

__all__ = [
    "REPRESENTATIONS",
    "DOMINANCE",
    "RepresentationChoice",
    "RepresentationPlanner",
    "plan_representation",
]


@dataclass(frozen=True)
class RepresentationSpec:
    """One representation's domain, expressed as a checkable claim."""

    name: str
    backend: str | None
    gate_set: str
    state_class: str
    resource: str
    exact: bool
    materialises: bool
    notes: str

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


REPRESENTATIONS: dict[str, RepresentationSpec] = {
    spec.name: spec
    for spec in (
        RepresentationSpec(
            name="dense_algebraic",
            backend="exact_algebraic",
            gate_set="clifford+t",
            state_class="universal",
            resource="amplitudes <= max_amplitudes",
            exact=True,
            materialises=True,
            notes="Universal exact reference; amplitudes are the resource.",
        ),
        RepresentationSpec(
            name="tableau",
            backend="stabilizer",
            gate_set="clifford",
            state_class="stabilizer",
            resource="O(n^2) tableau bits",
            exact=True,
            materialises=False,
            notes="Clifford-only; entropic scaling instead of state size.",
        ),
        RepresentationSpec(
            name="sparse_exact",
            backend="sparse",
            gate_set="clifford+t",
            state_class="bounded_support",
            resource="bounded support; enforced at run time",
            exact=True,
            materialises=True,
            notes="Exact amplitudes when support stays bounded; refusal otherwise.",
        ),
        RepresentationSpec(
            name="closed_form",
            backend="closed_form",
            gate_set="closed_form",
            state_class="named_family",
            resource="formula evaluation",
            exact=True,
            materialises=False,
            notes="Symbolic answer for named families; gate programs refused.",
        ),
        RepresentationSpec(
            name="symbolic_density",
            backend=None,
            gate_set="operators",
            state_class="density_operator",
            resource="symbolic algebra",
            exact=True,
            materialises=False,
            notes="RESERVED: declared representation with no bound backend; "
            "selection returns UNAVAILABLE, never a substitute.",
        ),
    )
}

#: DOMINANCE[a] lists representations a *strictly subsumes* for every program
#: in the subsumed representation's domain — same or better exactness, same
#: observable surface, no semantics lost.  Automatic upgrades are only
#: permitted along these edges; anything else must be a declared choice.
DOMINANCE: dict[str, frozenset[str]] = {
    # Dense algebra answers everything the tableau answers (Clifford is a
    # subset of Clifford+T) and everything sparse answers when its budget
    # admits; it does NOT dominate closed_form because closed_form answers
    # families at widths where no state exists.
    "dense_algebraic": frozenset({"tableau", "sparse_exact"}),
    # Tableau dominates nothing: dropping to another representation loses
    # the unbounded-width Clifford domain.
    "tableau": frozenset(),
    "sparse_exact": frozenset(),
    "closed_form": frozenset(),
    "symbolic_density": frozenset(),
}


@dataclass(frozen=True)
class RepresentationChoice:
    """The planner's verdict: what representation, and on what authority."""

    representation: str | None
    backend: str | None
    admitted: bool
    automatic: bool
    candidates: tuple[str, ...]
    rationale: str
    refusals: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "representation": self.representation,
            "backend": self.backend,
            "admitted": self.admitted,
            "automatic": self.automatic,
            "candidates": list(self.candidates),
            "rationale": self.rationale,
            "refusals": list(self.refusals),
        }


class RepresentationPlanner:
    """Plans the state representation for a program — fail-closed.

    Rules (WF02):

    * Explicit requests are honoured only if the representation's static
      domain covers the program; otherwise refused with the reason.
    * ``"auto"`` selects the cheapest representation whose domain provably
      covers the program: tableau for unbounded Clifford, dense algebra
      inside budget, sparse only as a declared candidate (its bound is a
      run-time property).  Anything else is a refused plan, not a guess.
    * RESERVED representations (no bound backend) resolve UNAVAILABLE.
    """

    AUTO_ORDER: tuple[str, ...] = (
        "tableau",
        "dense_algebraic",
        "sparse_exact",
        "closed_form",
        "symbolic_density",
    )

    def __init__(self, *, max_amplitudes: int = 1 << 20) -> None:
        self.max_amplitudes = max_amplitudes

    # -- static domain checks -------------------------------------------------

    def _static_domain_ok(self, name: str, program: Program) -> tuple[bool, str]:
        if name not in REPRESENTATIONS:
            return False, f"unknown representation {name!r}"
        spec = REPRESENTATIONS[name]
        gates = program.gates()
        if name == "tableau":
            bad = sorted(g for g in gates if g not in CLIFFORD_GATES)
            if bad:
                return False, f"non-Clifford gate(s) {bad} outside tableau domain"
            return True, "Clifford program; tableau domain covers any width"
        if name == "dense_algebraic":
            unknown = sorted(g for g in gates if g not in _DENSE_GATES)
            if unknown:
                return False, f"gate(s) {unknown} have no exact algebraic form"
            if (1 << program.n_qubits) > self.max_amplitudes:
                return (
                    False,
                    f"2^{program.n_qubits} amplitudes exceed budget "
                    f"{self.max_amplitudes}",
                )
            return True, "universal exact domain within amplitude budget"
        if name == "sparse_exact":
            unknown = sorted(g for g in gates if g not in _DENSE_GATES)
            if unknown:
                return False, f"gate(s) {unknown} have no sparse binding"
            return (
                True,
                "static domain covered; support bound is enforced at run time",
            )
        if name == "closed_form":
            return (
                False,
                "closed_form answers named families, not gate programs; "
                "use evaluate_family()",
            )
        if name == "symbolic_density":
            return False, "UNAVAILABLE: representation reserved; no bound backend"
        return False, "no static domain rule"

    def plan(
        self,
        program: Program,
        *,
        representation: str = "auto",
        declared_support_bound: int | None = None,
    ) -> RepresentationChoice:
        """Choose a representation for ``program``; never invents one."""
        if representation != "auto":
            ok, reason = self._static_domain_ok(representation, program)
            spec = REPRESENTATIONS.get(representation)
            if ok and spec is not None and spec.backend is None:
                return RepresentationChoice(
                    representation=representation,
                    backend=None,
                    admitted=False,
                    automatic=False,
                    candidates=(representation,),
                    rationale=f"{representation} is reserved with no bound backend",
                    refusals=("UNAVAILABLE: no backend bound to this representation",),
                )
            if ok:
                return RepresentationChoice(
                    representation=representation,
                    backend=spec.backend if spec else None,
                    admitted=True,
                    automatic=False,
                    candidates=(representation,),
                    rationale=reason,
                )
            return RepresentationChoice(
                representation=None,
                backend=None,
                admitted=False,
                automatic=False,
                candidates=(representation,),
                rationale=f"requested representation refused: {reason}",
                refusals=(reason,),
            )

        # automatic path — walk AUTO_ORDER, first static-domain coverage wins
        candidates: list[str] = []
        refusals: list[str] = []
        for name in self.AUTO_ORDER:
            ok, reason = self._static_domain_ok(name, program)
            if ok:
                spec = REPRESENTATIONS[name]
                if spec.backend is None:
                    refusals.append(f"{name}: reserved, no bound backend")
                    continue
                if name == "sparse_exact" and declared_support_bound is None:
                    # sparse is a candidate, not an automatic pick: its bound
                    # is only checkable at run time, so record and move on.
                    candidates.append(name)
                    refusals.append(
                        "sparse_exact: declared candidate only — support "
                        "boundedness not provable statically"
                    )
                    continue
                return RepresentationChoice(
                    representation=name,
                    backend=spec.backend,
                    admitted=True,
                    automatic=True,
                    candidates=tuple([name, *candidates]),
                    rationale=f"{reason}; selected automatically over candidates "
                    f"{candidates or '[]'}",
                    refusals=tuple(refusals),
                )
            refusals.append(f"{name}: {reason}")
        return RepresentationChoice(
            representation=None,
            backend=None,
            admitted=False,
            automatic=True,
            candidates=tuple(candidates),
            rationale="no representation's static domain covers this program",
            refusals=tuple(refusals),
        )

    def dominates(self, stronger: str, weaker: str) -> bool:
        """True iff ``stronger`` provably subsumes ``weaker``'s domain."""
        return weaker in DOMINANCE.get(stronger, frozenset())


# Gates with an exact algebraic form over Q(sqrt(2)) + i*Q(sqrt(2)) — the
# Clifford+T set plus phases the exact field can express exactly.
_DENSE_GATES = frozenset(CLIFFORD_GATES | {"t", "tdg"})


def plan_representation(
    program: Program,
    *,
    representation: str = "auto",
    max_amplitudes: int = 1 << 20,
    declared_support_bound: int | None = None,
) -> RepresentationChoice:
    """Convenience wrapper for the default planner."""
    return RepresentationPlanner(max_amplitudes=max_amplitudes).plan(
        program,
        representation=representation,
        declared_support_bound=declared_support_bound,
    )
