"""Exact MPS backend: Clifford+T at any width when entanglement stays bounded.

The stabilizer tableau covers the Clifford group at any width; the dense
algebraic backend covers universal Clifford+T while 2^n amplitudes fit. This
backend covers the class between them: Clifford+T programs of any width whose
Schmidt rank stays bounded at every cut. The state is a Kellogg exact MPS over
Q(zeta_8) whose bonds are the exact Schmidt ranks; nothing is truncated.

Admission is decided before execution from a static bound. A two-qubit gate
across a cut multiplies the Schmidt rank there by at most its operator
Schmidt rank (2 for CX/CZ, 4 for SWAP); while a long-range gate is routed by
SWAPs, cuts it passes see one relocated qubit (a further factor of at most 2).
Every bound is also capped by 2^min(left, right). If the bound exceeds
``chi_max`` at any cut the program is refused, so execution can never exceed
it.
"""

from __future__ import annotations

import random
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base import Admission, Capability, ExecutionClass, ExecutionResult, Program, TruthClass

__all__ = ["MPSExactBackend", "schmidt_bound"]

_ONE_QUBIT = {
    "i": "I",
    "x": "X",
    "y": "Y",
    "z": "Z",
    "h": "H",
    "s": "S",
    "sdg": "Sdg",
    "t": "T",
    "tdg": "Tdg",
}
_TWO_QUBIT = {"cx": ("CNOT", 1), "cnot": ("CNOT", 1), "cz": ("CZ", 1), "swap": ("SWAP", 2)}
SUPPORTED = frozenset(_ONE_QUBIT) | frozenset(_TWO_QUBIT)


def schmidt_bound(program: Program) -> List[int]:
    """log2 upper bound on the Schmidt rank at each internal cut, over the whole run.

    Cut c separates qubits 0..c from c+1..n-1. The returned list has n-1
    entries; entry c is the largest log2 rank any intermediate state of the
    routed execution can reach at cut c.
    """
    n = program.n_qubits
    if n < 2:
        return []
    cap = [min(c + 1, n - c - 1) for c in range(n - 1)]
    state = [0] * (n - 1)
    peak = [0] * (n - 1)
    for op in program.operations:
        if op.gate not in _TWO_QUBIT:
            continue
        lo, hi = sorted(op.qubits)
        bits = _TWO_QUBIT[op.gate][1]
        for c in range(lo, hi):
            state[c] = min(cap[c], state[c] + bits)
        for c in range(lo + 1, hi):
            peak[c] = max(peak[c], min(cap[c], state[c] + 1))
        for c in range(lo, hi):
            peak[c] = max(peak[c], state[c])
    return peak


def _q8_text(value: Any) -> str:
    """Exact text for a real Q(sqrt 2) value: 'p/q' or 'p/q + r/s*sqrt(2)'."""
    a = Fraction(value.a, value.den)
    b = Fraction(value.b, value.den)
    if b == 0:
        return str(a)
    if a == 0:
        return f"{b}*sqrt(2)"
    return f"{a} - {-b}*sqrt(2)" if b < 0 else f"{a} + {b}*sqrt(2)"


class MPSExactBackend:
    """Kellogg exact MPS behind the TURING backend contract."""

    name = "mps_exact"
    READOUT_LIMIT = 64
    MARGINAL_ENUMERATION_CAP = 4096

    def __init__(self, chi_max: int = 64, custody: Any = None) -> None:
        if chi_max < 1:
            raise ValueError("chi_max must be positive")
        self.chi_max = int(chi_max)
        self.custody = custody

    def capability(self) -> Capability:
        return Capability(
            name=self.name,
            execution_class=ExecutionClass.BOUNDED_EXACT,
            materialises_state=False,
            gate_set="clifford+t",
            state_classes=("bounded-schmidt-rank", "ghz", "product", "shallow-circuit"),
            max_qubits=None,
            requires=("kellogg",),
            notes=(
                f"Exact Clifford+T at any width while the static Schmidt bound stays <= "
                f"{self.chi_max} at every cut; Kellogg exact MPS over Q(zeta_8), bonds are exact "
                "Schmidt ranks, cores held in custody. Programs whose bound exceeds chi_max are "
                "refused, never truncated."
            ),
        )

    def _engine(self) -> Tuple[bool, str, Any]:
        try:
            from kellogg import exact_network
        except ImportError as exc:
            return False, f"kellogg is not importable ({exc})", None
        return True, "", exact_network

    def available(self) -> Tuple[bool, str]:
        ok, reason, _ = self._engine()
        return ok, reason

    def admit(self, program: Program) -> Admission:
        ok, reason, _ = self._engine()
        if not ok:
            return Admission(False, self.name, reason, ExecutionClass.BOUNDED_EXACT)
        outside = sorted(program.gates() - SUPPORTED)
        if outside:
            return Admission(
                False,
                self.name,
                f"gate(s) {outside} lie outside Clifford+T over Q(zeta_8); refused, not approximated",
                ExecutionClass.BOUNDED_EXACT,
            )
        bound = schmidt_bound(program)
        worst = max(bound, default=0)
        if (1 << worst) > self.chi_max:
            cut = bound.index(worst)
            return Admission(
                False,
                self.name,
                f"static Schmidt bound 2^{worst} at cut {cut} exceeds chi_max={self.chi_max}; "
                "refused rather than truncated",
                ExecutionClass.BOUNDED_EXACT,
            )
        return Admission(
            True,
            self.name,
            f"Clifford+T program with static Schmidt bound 2^{worst} <= chi_max={self.chi_max}",
            ExecutionClass.BOUNDED_EXACT,
        )

    def build(self, program: Program) -> Any:
        _, _, net = self._engine()
        psi = net.ExactMPS.zeros(program.n_qubits, custody=self.custody)
        for op in program.operations:
            if op.gate in _ONE_QUBIT:
                if op.gate != "i":
                    psi.apply_1q(op.qubits[0], _ONE_QUBIT[op.gate])
                continue
            name = _TWO_QUBIT[op.gate][0]
            a, b = op.qubits
            if b == a + 1:
                psi.apply_2q(a, name)
            elif name in ("CZ", "SWAP") and a == b + 1:
                psi.apply_2q(b, name)
            else:
                psi.apply_gate_pair(a, b, name)
        return psi

    # -- exact readout -----------------------------------------------------

    def marginal(self, psi: Any, qubits: Sequence[int]) -> Dict[str, Any]:
        from kellogg.exact_network import ExactNetworkError

        try:
            exact = psi.marginal(qubits, max_outcomes=self.MARGINAL_ENUMERATION_CAP)
        except ExactNetworkError as exc:
            raise ValueError(str(exc)) from exc
        return {
            "qubits": sorted(set(int(q) for q in qubits)),
            "probabilities": {k: _q8_text(v) for k, v in exact.items()},
            "field": "Q(sqrt2)",
            "_exact": exact,
        }

    def sample(self, distribution: Dict[str, Any], shots: int, seed: Optional[int]) -> Dict[str, int]:
        from kellogg.cyclotomic import Q8

        rng = random.Random(seed)
        keys = sorted(distribution)
        counts: Dict[str, int] = {}
        for _ in range(int(shots)):
            u = Q8.from_fractions(Fraction(rng.getrandbits(64), 1 << 64))
            acc = None
            pick = keys[-1]
            for k in keys:
                acc = distribution[k] if acc is None else acc + distribution[k]
                if (u - acc).sign() < 0:
                    pick = k
                    break
            counts[pick] = counts.get(pick, 0) + 1
        return counts

    def execute(self, program: Program, **options: Any) -> ExecutionResult:
        admission = self.admit(program)
        if not admission.admitted:
            raise ValueError(f"program refused by {self.name}: {admission.reason}")
        psi = self.build(program)
        bonds = psi.bonds()
        payload: Dict[str, Any] = {
            "representation": "mps_exact",
            "field": "Q(zeta8)",
            "max_bond": max(bonds),
            "static_schmidt_bound_log2": max(schmidt_bound(program), default=0),
            "chi_max": self.chi_max,
            "state_root": psi.root,
            "kellogg_certificates": psi.ledger.count,
            "kellogg_chain_digest": psi.ledger.chain_digest,
            "custody": psi.custody.accounting(),
            "norm_squared": _q8_text(psi.norm2()),
        }
        n = program.n_qubits
        shots = options.get("shots")
        if shots:
            readout = options.get("readout")
            if readout is None:
                if n > self.READOUT_LIMIT:
                    raise ValueError(
                        f"reading out all {n} qubits is refused above {self.READOUT_LIMIT}; "
                        "pass readout=[...]"
                    )
                readout = list(range(n))
            qubits = sorted({int(q) for q in readout})
            if len(qubits) > self.READOUT_LIMIT:
                raise ValueError(f"readout of {len(qubits)} qubits exceeds {self.READOUT_LIMIT}")
            dist = self.marginal(psi, qubits)
            payload["readout_qubits"] = qubits
            payload["counts"] = self.sample(dist["_exact"], int(shots), options.get("seed"))
        subset = options.get("marginal_of")
        if subset:
            m = self.marginal(psi, subset)
            m.pop("_exact")
            payload["marginal"] = m
        probe = options.get("measure_qubit")
        if probe is not None:
            q = int(probe)
            payload["measurement"] = {
                "qubit": q,
                "p0": _q8_text(psi.probability(q, 0)),
                "p1": _q8_text(psi.probability(q, 1)),
                "expectation_z": _q8_text(psi.expectation(q, "Z")),
            }
        bloch = options.get("bloch_of")
        if bloch is not None:
            q = int(bloch)
            payload["expectation_values"] = {
                axis: _q8_text(psi.expectation(q, axis)) for axis in ("X", "Y", "Z")
            }
        cut = options.get("entropy_of")
        if cut is not None:
            subset_cut = sorted({int(q) for q in cut})
            if subset_cut != list(range(len(subset_cut))) or not 0 < len(subset_cut) < n:
                raise ValueError("entropy_of must name a prefix {0..c} of the chain on this backend")
            bond = len(subset_cut) - 1
            rank = psi.schmidt_rank(bond)
            purity = psi.cut_purity(bond)
            from kellogg.cyclotomic import Q8

            flat = purity == Q8.from_fractions(Fraction(1, rank))
            payload["schmidt_rank"] = rank
            payload["purity"] = _q8_text(purity)
            payload["entanglement_entropy_bits"] = (rank.bit_length() - 1) if flat and rank & (rank - 1) == 0 else None
            payload["entropy_note"] = (
                "flat Schmidt spectrum: entropy = log2(rank), exact"
                if payload["entanglement_entropy_bits"] is not None
                else "non-flat spectrum: entropy is not exact in Q(zeta_8); rank and purity are exact"
            )
        return ExecutionResult(
            backend=self.name,
            execution_class=ExecutionClass.BOUNDED_EXACT,
            truth_class=TruthClass.EXACT,
            n_qubits=n,
            program_digest=program.digest(),
            materialised=False,
            payload=payload,
        )
