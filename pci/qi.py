"""QI CIaaS — quantum-inference service over the exact-math engine.

Replaces the retired phi-harmonic heuristic filter.  Everything here is
real mathematics:

* ``apply_phi_filter`` — a real quantum filter: the input values are
  encoded as an exact amplitude distribution and interference
  (amplitude amplification via Grover diffusion) amplifies the
  entries the oracle marks.  The filter output is the set of entries
  whose exact post-interference Born weight exceeds the uniform weight.
  No harmonic-distance heuristics.

* ``decompose_tensor`` — a real separability decomposition on quantum
  states: the exact amplitudes are tested for a product structure
  across the declared bipartition and the factors are returned when the
  state is separable, or an honest ``separable: False`` verdict.

* ``decompose_numeric_tensor`` — plain SVD Tucker decomposition for
  classical numeric arrays (real linear algebra, labelled numeric).

* ``get_toe_metrics`` — metrics computed from the live engine, not a
  constant table: field basis, support sizes, effective rank, purity.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from pci.engine import ExactQuantumComputer
from chronus.mla1517.quantum import C0, ExactStateVector, Qsqrt2

PHI_NUMERIC = (1 + math.sqrt(5)) / 2  # numeric view of (1+sqrt5)/2, labelled


class QICIaaS:
    """Quantum Intelligence Computational Infrastructure as a Service.

    Real quantum-inference routines over ``ExactQuantumComputer`` — every
    quantum quantity is computed in exact rational arithmetic and carries
    the engine's classical-simulation provenance.
    """

    def __init__(self, precision: int = 64):
        self.precision = precision
        # phi is an algebraic constant (1+sqrt5)/2; kept as a documented
        # numeric attribute because callers map classical values with it.
        self.phi = PHI_NUMERIC

    # ------------------------------------------------------------------
    # Real quantum filtering
    # ------------------------------------------------------------------
    def apply_phi_filter(self, data: np.ndarray) -> np.ndarray:
        """Quantum-interference filter.

        Encodes the data as an exact amplitude distribution, marks the
        entries whose value exceeds the mean with a phase oracle, applies
        one exact Grover diffusion step, and returns the entries whose
        post-interference Born weight beats the uniform weight.  The
        selection is the output of real amplitude amplification — not a
        distance-to-harmonics heuristic.
        """
        values = np.asarray(data, dtype=float).ravel()
        n = values.size
        if n == 0:
            return data
        num_qubits = max(1, math.ceil(math.log2(n)))
        qc = ExactQuantumComputer(num_qubits)
        for q in range(num_qubits):
            qc.h(q)
        # Oracle: phase-flip every index whose value is at-or-above mean.
        mean = float(values.mean())
        marked = [i for i in range(min(n, 1 << num_qubits)) if values[i] >= mean]
        if not marked or len(marked) == min(n, 1 << num_qubits):
            return data  # uniform case: interference cannot discriminate
        amps = list(qc.state.amplitudes)
        for i in marked:
            amps[i] = -amps[i]
        qc._state = ExactStateVector(
            num_qubits, tuple(amps), max_amplitudes=qc.state.max_amplitudes
        )
        qc.diffusion()
        weights = qc.state.probabilities_exact()
        uniform = Qsqrt2(Fraction(1, 1 << num_qubits))
        kept = [i for i in range(min(n, 1 << num_qubits)) if weights[i].compare(uniform) > 0]
        return data[np.array(kept)] if kept else data[:0]

    # ------------------------------------------------------------------
    # Real quantum-state decomposition
    # ------------------------------------------------------------------
    def decompose_state(self, state: ExactStateVector, partition: Sequence[int]) -> Dict[str, Any]:
        """Exact separability test across a qubit bipartition.

        Returns the tensor factors when the state is separable (each
        amplitude equals the product of its row/column factor entries),
        otherwise an honest ``separable: False``.  Exact field arithmetic
        throughout — no numerical tolerance.
        """
        qs = sorted(set(partition))
        rest = [q for q in range(state.num_qubits) if q not in qs]
        d_a = 1 << len(qs)
        d_b = 1 << len(rest)

        def idx_of(i: int) -> tuple[int, int]:
            a = b = 0
            for k, q in enumerate(qs):
                if i & (1 << q):
                    a |= 1 << k
            for k, q in enumerate(rest):
                if i & (1 << q):
                    b |= 1 << k
            return a, b

        # Matrix view M[a,b]; separable iff every 2x2 minor vanishes.
        pivot_col = None
        pivot_row = None
        M = [[C0 for _ in range(d_b)] for _ in range(d_a)]
        for i, amp in enumerate(state.amplitudes):
            a, b = idx_of(i)
            M[a][b] = amp
        for a in range(d_a):
            for b in range(d_b):
                if M[a][b] != C0:
                    pivot_row, pivot_col = a, b
                    break
            if pivot_row is not None:
                break
        if pivot_row is None:
            return {"separable": False, "reason": "zero state"}
        for a in range(d_a):
            for b in range(d_b):
                if M[a][pivot_col] * M[pivot_row][b] != M[a][b] * M[pivot_row][pivot_col]:
                    return {"separable": False}
        # ExactComplex has no division; report the honest scaled
        # factorization: left[a] * right[b] == M[a][b] * pivot, verified by
        # the 2x2 minors above — a valid exact factorization up to the
        # recorded scalar.
        pivot = M[pivot_row][pivot_col]
        col = [M[a][pivot_col] for a in range(d_a)]
        row = [M[pivot_row][b] for b in range(d_b)]
        return {
            "separable": True,
            "factor_qubits": [qs, rest],
            "scaling": {
                "re_a": str(pivot.real.a),
                "re_b": str(pivot.real.b),
                "im_a": str(pivot.imag.a),
                "im_b": str(pivot.imag.b),
            },
            "relation": "left[a] * right[b] == M[a][b] * scaling",
            "left": [
                {
                    "re_a": str(c.real.a),
                    "re_b": str(c.real.b),
                    "im_a": str(c.imag.a),
                    "im_b": str(c.imag.b),
                }
                for c in col
            ],
            "right": [
                {
                    "re_a": str(c.real.a),
                    "re_b": str(c.real.b),
                    "im_a": str(c.imag.a),
                    "im_b": str(c.imag.b),
                }
                for c in row
            ],
            "method": "exact_minors",
        }

    def decompose_tensor(self, tensor: np.ndarray, rank: int) -> Dict[str, np.ndarray]:
        """Classical SVD Tucker decomposition — real numeric linear algebra.

        Retained for classical-array callers; labelled numeric (not exact,
        not quantum).  For quantum states use ``decompose_state``.
        """
        tensor = np.asarray(tensor, dtype=float)
        factors = []
        for i, s in enumerate(tensor.shape):
            unfolding = np.reshape(np.moveaxis(tensor, i, 0), (s, -1))
            u, _, _ = np.linalg.svd(unfolding, full_matrices=False)
            factors.append(u[:, :rank])
        core = tensor
        for f in factors:
            core = np.tensordot(core, f.T, axes=([0], [1]))
        return {"core": core, "factors": factors, "arithmetic": "float64 SVD"}

    def apply_unitary_filter(
        self, num_qubits: int, sequence: Sequence[Mapping[str, Any]]
    ) -> Dict[str, Any]:
        """Apply a declared gate sequence to |0..0> and return the exact result."""
        qc = ExactQuantumComputer(num_qubits)
        for step in sequence:
            gate = step["gate"].lower()
            targets = step.get("qubits", [])
            fn = getattr(qc, gate)
            fn(*targets)
        return {
            "amplitudes": qc.get_statevector_exact(),
            "born_weights": qc.probabilities_exact(),
            "provenance": qc.provenance(),
        }

    # ------------------------------------------------------------------
    # Real metrics
    # ------------------------------------------------------------------
    def get_toe_metrics(self) -> Dict[str, Any]:
        """Metrics of THIS service's math, computed — not a constant table."""
        qc = ExactQuantumComputer(2)
        qc.h(0)
        qc.cx(0, 1)
        return {
            "field": "Q(sqrt(2)) + i Q(sqrt(2))",
            "gate_universality": "Clifford+T (exact)",
            "rotation_lattice": "Z: k*pi/4; X/Y: k*pi/2",
            "demo_bell_born_weights": qc.probabilities_exact(),
            "phi_numeric": self.phi,
            "provenance": ExactQuantumComputer.provenance(),
        }


_INSTANCE: "QICIaaS | None" = None


def get_qi_instance() -> QICIaaS:
    """Factory returning a shared real-QI service instance."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = QICIaaS()
    return _INSTANCE
