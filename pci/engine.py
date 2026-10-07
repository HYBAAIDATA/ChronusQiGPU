"""PCI — Predictive Causal Intelligence, exact-arithmetic engine.

This module replaces the retired numpy state-vector simulator and the
constant-prior "causal" heuristics with real, first-principles mathematics:

* ``VirtualQuantumComputer`` — an exact state-vector computer over the
  field Q(sqrt(2)) + i Q(sqrt(2)) (built on ``chronus.mla1517.quantum``).
  Clifford+T is universal and exactly representable in this field, so H,
  S, T, X, Y, Z, CNOT, CY, CZ, SWAP, Toffoli and the Grover diffusion
  operator are all exact.  Z-axis rotations are exact at every multiple of
  pi/4 (the eighth roots of unity live in the field); X/Y rotations are
  exact at multiples of pi/2.  Anything outside that lattice fails closed
  with ``GateNotExactlyRepresentable`` — no angle truncation, ever.

* ``PredictiveCausalIntelligence`` — real probabilistic causal inference.
  Observations are counted into an exact joint distribution (Fraction
  arithmetic).  Interventions implement Pearl's do-operator with parent
  adjustment:  P(y | do(x)) = sum_z P(y | x, z) * P(z),  evaluated in
  exact rationals over the declared DAG.  Confidence values are exact
  posteriors plus their sample counts — never a constant prior.

Provenance: every result here is exact classical simulation.  It is never
quantum hardware and never a cloud quantum service.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from chronus.mla1517.quantum import (
    C0,
    C1,
    CI,
    CLASSICAL_SIMULATION,
    ExactComplex,
    ExactStateVector,
    H,
    I,
    Qsqrt2,
    S,
    S_DG,
    SQRT2_INV,
    T,
    X,
    Y,
    Z,
    classical_simulation_provenance,
)

__all__ = [
    "CausalMode",
    "CausalPrediction",
    "CausalRelationship",
    "ExactQuantumComputer",
    "GateNotExactlyRepresentable",
    "InsufficientEvidence",
    "PredictiveCausalIntelligence",
    "VirtualQuantumComputer",
    "create_predictive_causal_intelligence",
]


class GateNotExactlyRepresentable(ValueError):
    """Requested gate/rotation is not exactly representable in Q(sqrt2)+iQ(sqrt2)."""


class InsufficientEvidence(RuntimeError):
    """A causal query was issued against an unobserved region of the joint."""


# The eighth roots of unity, all exact in Q(sqrt(2)) + i Q(sqrt(2)).
_R2 = ExactComplex(SQRT2_INV, SQRT2_INV)  # exp(i pi/4)  = (1+i)/sqrt2
_EIGHTH_ROOTS: Tuple[ExactComplex, ...] = (
    C1,  # k=0
    _R2,  # k=1
    CI,  # k=2
    ExactComplex(-SQRT2_INV, SQRT2_INV),  # k=3
    -C1,  # k=4
    ExactComplex(-SQRT2_INV, -SQRT2_INV),  # k=5
    -CI,  # k=6
    ExactComplex(SQRT2_INV, -SQRT2_INV),  # k=7
)

_TDG: Any = ((C1, C0), (C0, _EIGHTH_ROOTS[7]))


def _exact_scalar_phase(
    state: ExactStateVector, qubit: int, phase: ExactComplex
) -> ExactStateVector:
    """Apply diag(1, phase) on one qubit — exact amplitudes only."""
    if not 0 <= qubit < state.num_qubits:
        raise ValueError("qubit out of range")
    bit = 1 << qubit
    out = tuple(amp * phase if (i & bit) else amp for i, amp in enumerate(state.amplitudes))
    return ExactStateVector(state.num_qubits, out, max_amplitudes=state.max_amplitudes)


class ExactQuantumComputer:
    """Exact state-vector quantum computer over Q(sqrt(2)) + i Q(sqrt(2)).

    Every gate application, Born weight and expectation value is computed
    in exact rational arithmetic — no floats enter the state.  The machine
    fails closed (``GateNotExactlyRepresentable``) for rotations that are
    not exactly representable instead of silently truncating them.
    """

    def __init__(self, num_qubits: int, *, max_amplitudes: int | None = None):
        if num_qubits < 1:
            raise ValueError("num_qubits must be >= 1")
        self.num_qubits = num_qubits
        self._state = ExactStateVector.basis(num_qubits, 0, max_amplitudes=max_amplitudes)
        self._history: List[Dict[str, Any]] = []

    # -- provenance ----------------------------------------------------
    @staticmethod
    def provenance() -> Dict[str, Any]:
        return classical_simulation_provenance(
            "pci.engine.ExactQuantumComputer",
            arithmetic="exact Q(sqrt2) + iQ(sqrt2)",
            sampling="deterministic (exact Born weights); seeded histogram only when explicitly requested",
        )

    # -- state access --------------------------------------------------
    @property
    def state(self) -> ExactStateVector:
        return self._state

    def reset(self) -> None:
        self._state = ExactStateVector.basis(
            self.num_qubits, 0, max_amplitudes=self._state.max_amplitudes
        )
        self._history.append({"op": "reset"})

    def get_statevector_exact(self) -> Tuple[Dict[str, str], ...]:
        """Amplitudes as exact rational records — the authoritative form."""
        out = []
        for amp in self._state.amplitudes:
            out.append(
                {
                    "re_a": str(amp.real.a),
                    "re_b": str(amp.real.b),
                    "im_a": str(amp.imag.a),
                    "im_b": str(amp.imag.b),
                }
            )
        return tuple(out)

    def get_statevector(self) -> List[complex]:
        """Float view for display/diagnostics only; never authoritative."""
        s2 = math.sqrt(2.0)
        return [
            complex(float(a.real.a) + s2 * float(a.real.b), float(a.imag.a) + s2 * float(a.imag.b))
            for a in self._state.amplitudes
        ]

    def _record(self, op: str, **detail: Any) -> None:
        self._history.append({"op": op, **detail})

    # -- gates ---------------------------------------------------------
    def op(self, gate: Any, target_qubit: int) -> None:
        """Apply an exact 2x2 gate; the kernel validates exact unitarity."""
        self._state = self._state.apply_single(target_qubit, gate)
        self._record("op", qubit=target_qubit)

    def h(self, qubit: int) -> None:
        self._state = self._state.apply_single(qubit, H)
        self._record("H", qubit=qubit)

    def x(self, qubit: int) -> None:
        self._state = self._state.apply_single(qubit, X)
        self._record("X", qubit=qubit)

    def y(self, qubit: int) -> None:
        self._state = self._state.apply_single(qubit, Y)
        self._record("Y", qubit=qubit)

    def z(self, qubit: int) -> None:
        self._state = self._state.apply_single(qubit, Z)
        self._record("Z", qubit=qubit)

    def s(self, qubit: int) -> None:
        self._state = self._state.apply_single(qubit, S)
        self._record("S", qubit=qubit)

    def sdg(self, qubit: int) -> None:
        self._state = self._state.apply_single(qubit, S_DG)
        self._record("Sdg", qubit=qubit)

    def t(self, qubit: int) -> None:
        self._state = self._state.apply_single(qubit, T)
        self._record("T", qubit=qubit)

    def tdg(self, qubit: int) -> None:
        self._state = self._state.apply_single(qubit, _TDG)
        self._record("Tdg", qubit=qubit)

    # -- rotations: exact only ----------------------------------------
    def rz(self, qubit: int, eighth_turns: int) -> None:
        """Z rotation by ``eighth_turns * pi/4`` — exact for every integer."""
        if not isinstance(eighth_turns, int):
            raise GateNotExactlyRepresentable("rz accepts integer eighth-turns (pi/4 units) only")
        k = eighth_turns % 8
        if k % 2 == 0:
            quarter = k // 2
            if quarter:
                self._state = self._state.evolve_pauli_z(quarter)
        else:
            self._state = _exact_scalar_phase(self._state, qubit, _EIGHTH_ROOTS[k])
            # note: _exact_scalar_phase applies diag(1, w) — the full Rz is
            # diag(1, w) up to the global phase e^{-i theta/2}; the kernel's
            # convention (and this class's) is the unnormalized diag(1, w),
            # identical to all state-vector observables.
        self._record("Rz", qubit=qubit, eighth_turns=eighth_turns)

    def rx(self, qubit: int, quarter_turns: int) -> None:
        """X rotation by ``quarter_turns * pi/2`` — exact Clifford angles only."""
        if not isinstance(quarter_turns, int):
            raise GateNotExactlyRepresentable("rx accepts integer quarter-turns (pi/2 units) only")
        k = quarter_turns % 4
        if k:
            # Rx(k pi/2) = H Rz(k pi/2) H
            self._state = self._state.apply_single(qubit, H)
            self._state = _exact_scalar_phase(self._state, qubit, _EIGHTH_ROOTS[2 * k])
            self._state = self._state.apply_single(qubit, H)
        self._record("Rx", qubit=qubit, quarter_turns=quarter_turns)

    def ry(self, qubit: int, quarter_turns: int) -> None:
        """Y rotation by ``quarter_turns * pi/2`` — exact Clifford angles only."""
        if not isinstance(quarter_turns, int):
            raise GateNotExactlyRepresentable("ry accepts integer quarter-turns (pi/2 units) only")
        k = quarter_turns % 4
        if k:
            # Ry(k pi/2) = (S H) Rz(k pi/2) (H Sdg)
            self._state = self._state.apply_single(qubit, S_DG)
            self._state = self._state.apply_single(qubit, H)
            self._state = _exact_scalar_phase(self._state, qubit, _EIGHTH_ROOTS[2 * k])
            self._state = self._state.apply_single(qubit, H)
            self._state = self._state.apply_single(qubit, S)
        self._record("Ry", qubit=qubit, quarter_turns=quarter_turns)

    def u1(self, qubit: int, eighth_turns: int) -> None:
        """U1(lambda): exact iff lambda is a multiple of pi/4."""
        self.rz(qubit, eighth_turns)
        self._record("U1", qubit=qubit)

    def u2(self, qubit: int, phi_eighths: int, lambda_eighths: int) -> None:
        """U2(phi, lambda) = Rz(phi) Ry(pi/2) Rz(lambda) — exact on the lattice."""
        self.rz(qubit, lambda_eighths)
        self.ry(qubit, 1)
        self.rz(qubit, phi_eighths)
        self._record("U2", qubit=qubit)

    def u3(self, qubit: int, theta_quarters: int, phi_eighths: int, lambda_eighths: int) -> None:
        """U3(theta, phi, lambda) = Rz(phi) Ry(theta) Rz(lambda).

        Exact iff theta is a quarter-turn multiple and phi/lambda are
        pi/4 multiples; anything else fails closed.
        """
        self.rz(qubit, lambda_eighths)
        self.ry(qubit, theta_quarters)
        self.rz(qubit, phi_eighths)
        self._record("U3", qubit=qubit)

    # -- two/three-qubit gates -----------------------------------------
    def cnot(self, control: int, target: int) -> None:
        self._state = self._state.apply_cnot(control, target)
        self._record("CNOT", control=control, target=target)

    cx = cnot

    def cz(self, control: int, target: int) -> None:
        self._state = (
            self._state.apply_single(target, H).apply_cnot(control, target).apply_single(target, H)
        )
        self._record("CZ", control=control, target=target)

    def cy(self, control: int, target: int) -> None:
        # CY = (I tensor S) CNOT (I tensor Sdg)
        self._state = (
            self._state.apply_single(target, S_DG)
            .apply_cnot(control, target)
            .apply_single(target, S)
        )
        self._record("CY", control=control, target=target)

    def swap(self, qubit1: int, qubit2: int) -> None:
        self.cnot(qubit1, qubit2)
        self.cnot(qubit2, qubit1)
        self.cnot(qubit1, qubit2)
        self._record("SWAP", a=qubit1, b=qubit2)

    def ccx(self, control1: int, control2: int, target: int) -> None:
        """Toffoli — canonical exact Clifford+T decomposition (6 CNOTs)."""
        a, b, c = control1, control2, target
        self._state = self._state.apply_single(c, H)
        self.cnot(b, c)
        self.tdg(c)
        self.cnot(a, c)
        self.t(c)
        self.cnot(b, c)
        self.tdg(c)
        self.cnot(a, c)
        self.t(b)
        self.t(c)
        self._state = self._state.apply_single(c, H)
        self.cnot(a, b)
        self.t(a)
        self.tdg(b)
        self.cnot(a, b)
        self._record("CCX", a=a, b=b, c=c)

    def diffusion(self, qubits: Optional[Sequence[int]] = None) -> None:
        """Grover diffusion D = 2|s><s| - I over the given qubits (default: all).

        Exact: conjugate by H on each diffused qubit and flip the sign of
        every amplitude whose subset-index is nonzero — the algebraic
        identity H R0 H a == (2*mean - a_i) within each spectator sector.
        """
        targets = list(qubits) if qubits is not None else list(range(self.num_qubits))
        for q in targets:
            self._state = self._state.apply_single(q, H)
        mask = 0
        for q in targets:
            mask |= 1 << q
        out = tuple(
            amp if (i & mask) == 0 else -amp for i, amp in enumerate(self._state.amplitudes)
        )
        self._state = ExactStateVector(
            self.num_qubits, out, max_amplitudes=self._state.max_amplitudes
        )
        for q in targets:
            self._state = self._state.apply_single(q, H)
        self._record("DIFFUSION", qubits=list(targets))

    # -- Hamiltonian evolution (Pauli quarter-turns, exact) ------------
    def evolve_hamiltonian(self, hamiltonian: str, quarter_turns: int) -> None:
        self._state = self._state.evolve_hamiltonian(hamiltonian, quarter_turns)
        self._record("EVOLVE", hamiltonian=hamiltonian, quarter_turns=quarter_turns)

    # -- measurement ---------------------------------------------------
    def probabilities_exact(self) -> Tuple[Dict[str, str], ...]:
        """Exact Born weights as Q(sqrt2) records {a, b} (a + b*sqrt2)."""
        return tuple({"a": str(w.a), "b": str(w.b)} for w in self._state.probabilities_exact())

    def probabilities(self) -> List[float]:
        """Float view of the exact Born weights — display only."""
        s2 = math.sqrt(2.0)
        return [float(w.a) + s2 * float(w.b) for w in self._state.probabilities_exact()]

    def measure(self, shots: int = 1, collapse: bool = False) -> List[str]:
        """Deterministic measurement: the maximum-Born-weight basis state.

        This is exact, not sampled.  The result repeats for each shot —
        shots>1 is accepted for API compatibility and returns the same
        deterministic outcome each time.
        """
        index = self._state.measure_deterministic()
        if collapse:
            self._state = self._state.collapse(index)
        self._record("MEASURE", index=index, shots=shots, deterministic=True)
        return [format(index, f"0{self.num_qubits}b") for _ in range(max(1, shots))]

    def sample(self, shots: int, seed: int) -> Dict[str, int]:
        """Seeded histogram over the exact Born weights.

        Selection boundaries are compared in exact rationals; only the
        uniform draw is a float.  Labelled honestly as seeded sampling.
        """
        if shots < 1 or not isinstance(seed, int):
            raise ValueError("shots must be >= 1 and seed an int")
        rng = random.Random(seed)
        weights = self._state.probabilities_exact()
        counts: Dict[str, int] = {}
        for _ in range(shots):
            # u is an exact rational embedding of the float draw; every
            # comparison against the exact cumulative weights is exact.
            u = Qsqrt2(Fraction(rng.random()))
            acc = Qsqrt2()
            chosen = len(weights) - 1
            for i, w in enumerate(weights):
                acc = acc + w
                if (acc - u).sign() > 0:
                    chosen = i
                    break
            key = format(chosen, f"0{self.num_qubits}b")
            counts[key] = counts.get(key, 0) + 1
        self._record("SAMPLE", shots=shots, seed=seed, sampling="seeded_over_exact_weights")
        return counts

    def measure_qubit(self, qubit: int, shots: int = 1, collapse: bool = False) -> List[str]:
        """Deterministic marginal outcome for one qubit."""
        if not 0 <= qubit < self.num_qubits:
            raise ValueError("qubit out of range")
        weights = self._state.probabilities_exact()
        w0 = sum((w for i, w in enumerate(weights) if not (i & (1 << qubit))), Qsqrt2())
        w1 = sum((w for i, w in enumerate(weights) if i & (1 << qubit)), Qsqrt2())
        outcome = 0 if w0.compare(w1) >= 0 else 1
        return [str(outcome) for _ in range(max(1, shots))]

    def expectation_z_exact(self, qubit: int = 0) -> Dict[str, str]:
        """Exact Z expectation (a + b*sqrt2) on the given qubit."""
        weights = self._state.probabilities_exact()
        acc = Qsqrt2()
        bit = 1 << qubit
        for i, w in enumerate(weights):
            acc = acc + w if not (i & bit) else acc - w
        return {"a": str(acc.a), "b": str(acc.b)}

    def fidelity_to_basis_exact(self, index: int) -> Dict[str, str]:
        """Exact |<index|psi>|^2 Born weight."""
        w = self._state.probabilities_exact()[index]
        return {"a": str(w.a), "b": str(w.b)}

    def suggest_optimal_gate(self, target_qubit: int, goal_index: int) -> Dict[str, Any]:
        """REAL gate selection: try each exact gate, keep the argmax Born
        weight at ``goal_index``.  No heuristic — the winner is computed."""
        candidates = {
            "I": I,
            "H": H,
            "X": X,
            "Y": Y,
            "Z": Z,
            "S": S,
            "Sdg": S_DG,
            "T": T,
            "Tdg": _TDG,
        }
        best_name, best_weight = "I", None
        scores: Dict[str, Dict[str, str]] = {}
        for name, gate in candidates.items():
            trial = self._state.apply_single(target_qubit, gate)
            w = trial.probabilities_exact()[goal_index]
            scores[name] = {"a": str(w.a), "b": str(w.b)}
            if best_weight is None or w.compare(best_weight) > 0:
                best_name, best_weight = name, w
        return {
            "gate": best_name,
            "exact_weight_at_goal": scores[best_name],
            "all_weights": scores,
            "goal_index": goal_index,
            "method": "exhaustive_exact_evaluation",
        }

    # -- introspection ---------------------------------------------------
    def introspect_quantum_state(self) -> Dict[str, Any]:
        """Real, computed state inspection — no fabricated metrics."""
        amps = self._state.amplitudes
        support = sum(1 for a in amps if a != C0)
        weights = self._state.probabilities_exact()
        max_w = weights[0]
        for w in weights[1:]:
            if w.compare(max_w) > 0:
                max_w = w
        return {
            "num_qubits": self.num_qubits,
            "dimension": len(amps),
            "nonzero_amplitudes": support,
            "is_superposition": support > 1,
            "normalized_exact": self._state.normalized_exact(),
            "max_born_weight": {"a": str(max_w.a), "b": str(max_w.b)},
            "purity": "1 (state vector is pure by construction)",
            "provenance": self.provenance(),
        }

    # -- persistence (exact round-trip) --------------------------------
    def save_state(self, path: str | Path) -> None:
        payload = {
            "schema": "pci.exact-state/v1",
            "num_qubits": self.num_qubits,
            "amplitudes": list(self.get_statevector_exact()),
            "provenance": self.provenance(),
        }
        Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load_state(cls, path: str | Path) -> "ExactQuantumComputer":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != "pci.exact-state/v1":
            raise ValueError("not a pci exact-state artifact")
        obj = cls(int(data["num_qubits"]))
        amps = tuple(
            ExactComplex(
                Qsqrt2(Fraction(a["re_a"]), Fraction(a["re_b"])),
                Qsqrt2(Fraction(a["im_a"]), Fraction(a["im_b"])),
            )
            for a in data["amplitudes"]
        )
        obj._state = ExactStateVector(obj.num_qubits, amps)
        if not obj._state.normalized_exact():
            raise ValueError("loaded state is not exactly normalized")
        return obj

    def print_state(self, file=None) -> None:
        lines = [
            f"|{format(i, f'0{self.num_qubits}b')}>: {a}"
            for i, a in enumerate(self.get_statevector_exact())
        ]
        text = "\n".join(lines)
        if file is not None:
            print(text, file=file)
        else:
            print(text)


# Backwards-compatible alias: the retired class was named
# VirtualQuantumComputer.  The new implementation is exact — the name is
# kept so existing callers resolve, and its contract is now honest.
VirtualQuantumComputer = ExactQuantumComputer


# ----------------------------------------------------------------------
# Predictive Causal Intelligence — exact Pearl-style inference
# ----------------------------------------------------------------------


class CausalMode(Enum):
    OBSERVATIONAL = "observational"  # P(y | x) — association only
    INTERVENTIONAL = "interventional"  # P(y | do(x)) — parent adjustment
    CAUSAL_PREDICTION = "causal_prediction"  # declared DAG required


@dataclass(frozen=True)
class CausalRelationship:
    cause: str
    effect: str
    strength: Fraction  # P(e|c) - P(e|~c), exact
    conditional_given: Fraction
    conditional_without: Fraction
    evidence_samples: int
    mode: str
    direction: str  # "declared" (DAG) or "associational"


@dataclass(frozen=True)
class CausalPrediction:
    target: str
    probabilities: Dict[str, Fraction]  # value -> exact posterior
    evidence_samples: int
    mechanism: str
    provenance: Dict[str, Any]


class PredictiveCausalIntelligence:
    """Exact causal inference over an observed joint distribution.

    All probabilities are exact Fractions of observed counts.  The
    do-operator uses parent adjustment against a declared DAG — the DAG is
    declared, never invented; queries beyond the declared structure fail
    closed with ``InsufficientEvidence``.
    """

    def __init__(self, mode: CausalMode = CausalMode.CAUSAL_PREDICTION):
        self.mode = mode
        self._variables: List[str] = []
        self._values: Dict[str, List[int]] = {}
        self._counts: Dict[Tuple[int, ...], int] = {}
        self._parents: Dict[str, Tuple[str, ...]] = {}

    # -- declaration -----------------------------------------------------
    def declare_variable(self, name: str, values: Sequence[int] = (0, 1)) -> None:
        if name not in self._variables:
            self._variables.append(name)
            self._values[name] = list(values)
            self._counts = {k: v for k, v in self._counts.items()}  # keep raw; new slots zero

    def declare_parents(self, variable: str, parents: Sequence[str]) -> None:
        for p in parents:
            if p not in self._variables:
                raise ValueError(f"undeclared parent variable {p!r}")
        if variable not in self._variables:
            raise ValueError(f"undeclared variable {variable!r}")
        if variable in parents:
            raise ValueError("a variable cannot be its own parent")
        self._parents[variable] = tuple(parents)

    # -- observation ------------------------------------------------------
    def observe(self, assignment: Mapping[str, int]) -> None:
        for v in assignment:
            if v not in self._variables:
                if self._counts:
                    raise InsufficientEvidence(
                        f"new variable {v!r} appeared after observations exist — "
                        "extending the joint would fabricate unmeasured data"
                    )
                self.declare_variable(v)
        key = tuple(int(assignment.get(v, 0)) for v in self._variables)
        self._counts[key] = self._counts.get(key, 0) + 1

    def observe_many(self, assignments: Iterable[Mapping[str, int]]) -> None:
        for a in assignments:
            self.observe(a)

    def total_observations(self) -> int:
        return sum(self._counts.values())

    # -- exact probability machinery --------------------------------------
    def _match(self, key: Tuple[int, ...], evidence: Mapping[str, int]) -> bool:
        return all(key[self._variables.index(v)] == int(val) for v, val in evidence.items())

    def _prob(
        self, target: Mapping[str, int], evidence: Mapping[str, int] | None = None
    ) -> Fraction:
        """Exact P(target | evidence) from counts; fails closed on no data."""
        evidence = evidence or {}
        num = den = 0
        for key, c in self._counts.items():
            if self._match(key, evidence):
                den += c
                if self._match(key, target):
                    num += c
        if den == 0:
            raise InsufficientEvidence(
                f"no observations cover evidence {dict(evidence)} — refusing to fabricate"
            )
        return Fraction(num, den)

    def _do_prob(self, target: Mapping[str, int], do: Mapping[str, int]) -> Fraction:
        """Exact P(target | do(X)) via parent adjustment on the declared DAG."""
        do_vars = set(do)
        if not do_vars.issubset(set(self._variables)):
            raise InsufficientEvidence("do() references undeclared variables")
        # Adjustment set = union of declared parents of intervened vars
        adjust: List[str] = sorted({p for v in do_vars for p in self._parents.get(v, ())})
        for v in do_vars:
            if v in adjust:
                raise ValueError("intervened variable cannot adjust for itself")
        total = Fraction(0)
        any_covered = False
        # Sum over the observed joint of the adjustment set.
        if not adjust:
            return self._prob(target, dict(do))
        domains = [self._values.get(p, [0, 1]) for p in adjust]
        for combo in _cartesian(domains):
            z = dict(zip(adjust, combo))
            ev = {**do, **z}
            try:
                p_y_given_xz = self._prob(target, ev)
                p_z = self._prob(z, {})
            except InsufficientEvidence:
                continue
            any_covered = True
            total += p_y_given_xz * p_z
        if not any_covered:
            raise InsufficientEvidence("adjustment set has no observed support")
        return total

    # -- public inference --------------------------------------------------
    def conditional_probability(
        self,
        target: Mapping[str, int],
        evidence: Mapping[str, int] | None = None,
        do: Mapping[str, int] | None = None,
    ) -> Fraction:
        if do:
            return self._do_prob(target, do)
        return self._prob(target, evidence)

    def analyze_relationship(
        self, cause: str, effect: str, *, cause_value: int = 1, effect_value: int = 1
    ) -> CausalRelationship:
        """Exact effect strength: P(e|c) - P(e|~c) — observational by default,
        interventional (parent-adjusted) when mode requires it."""
        if cause not in self._variables or effect not in self._variables:
            raise InsufficientEvidence("relationship references undeclared variables")
        with_c = self._prob({effect: effect_value}, {cause: cause_value})
        without_c = self._prob({effect: effect_value}, {cause: 1 - cause_value})
        if self.mode in (
            CausalMode.INTERVENTIONAL,
            CausalMode.CAUSAL_PREDICTION,
        ) and self._parents.get(cause):
            with_c = self._do_prob({effect: effect_value}, {cause: cause_value})
            without_c = self._do_prob({effect: effect_value}, {cause: 1 - cause_value})
            direction = "declared"
        else:
            direction = "declared" if cause in self._parents.get(effect, ()) else "associational"
        n = sum(
            c
            for k, c in self._counts.items()
            if k[self._variables.index(cause)] in (cause_value, 1 - cause_value)
        )
        return CausalRelationship(
            cause=cause,
            effect=effect,
            strength=with_c - without_c,
            conditional_given=with_c,
            conditional_without=without_c,
            evidence_samples=n,
            mode=self.mode.value,
            direction=direction,
        )

    def predict(
        self,
        target: str,
        evidence: Mapping[str, int] | None = None,
        do: Mapping[str, int] | None = None,
    ) -> CausalPrediction:
        """Exact posterior distribution over the target's declared values."""
        if target not in self._variables:
            raise InsufficientEvidence("target variable is undeclared")
        probs: Dict[str, Fraction] = {}
        for val in self._values.get(target, [0, 1]):
            t = {target: val}
            probs[str(val)] = self._do_prob(t, do) if do else self._prob(t, evidence or {})
        n = self.total_observations()
        return CausalPrediction(
            target=target,
            probabilities=probs,
            evidence_samples=n,
            mechanism="exact_parent_adjustment" if do else "exact_conditioning",
            provenance={
                "execution": CLASSICAL_SIMULATION,
                "arithmetic": "exact rational (Fraction) inference",
                "sampling": "none — full joint enumeration",
            },
        )


def _cartesian(domains: Sequence[Sequence[int]]) -> Iterable[Tuple[int, ...]]:
    if not domains:
        yield ()
        return
    first, rest = domains[0], domains[1:]
    for v in first:
        for tail in _cartesian(rest):
            yield (v, *tail)


def create_predictive_causal_intelligence(
    mode: CausalMode = CausalMode.CAUSAL_PREDICTION,
) -> PredictiveCausalIntelligence:
    return PredictiveCausalIntelligence(mode=mode)
