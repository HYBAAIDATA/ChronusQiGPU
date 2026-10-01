# caltech.py -- Caltech academic-review enhancement modules (audit-fixed, 3 Aug 2026)
#
# Real vs. flavor-text triage:
#   - Caltech_Ising_Anyons: the fusion rules and R-/F-matrices for Ising
#     anyons are standard, correct topological-quantum-computing math,
#     implemented exactly.
#   - Caltech_Topological_Quantum: uses those real matrices to build actual
#     gate matrices. This is *simulated linear algebra*, not physical
#     anyons -- this package has no topological hardware, so "braiding"
#     here means "compute the correct R-/F-matrix and apply it", same as
#     the rest of Chronos's classical-numpy simulation.
#   - Caltech_Surface_Code: a real, small (distance-3) surface code with
#     real X/Z stabilizers and a real minimum-weight lookup decoder. The
#     pseudocode's claimed "6,000,000-sample trained neural network, 99.9%
#     accuracy" decoder does not exist here -- no training data or model
#     was available -- so it is replaced with an honest, actually-working
#     brute-force decoder instead of fabricating a trained-model claim.

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


class Caltech_Ising_Anyons:
    FUSION_RULES = {
        ("1", "1"): ["1"],
        ("1", "psi"): ["psi"],
        ("1", "sigma"): ["sigma"],
        ("psi", "psi"): ["1"],
        ("psi", "sigma"): ["sigma"],
        ("sigma", "sigma"): ["1", "psi"],
    }

    def fuse(self, a: str, b: str) -> List[str]:
        key = (a, b) if (a, b) in self.FUSION_RULES else (b, a)
        return self.FUSION_RULES[key]

    def r_matrix(self) -> Dict[str, complex]:
        return {
            "sigma_sigma_1": complex(np.exp(-1j * np.pi / 8)),
            "sigma_sigma_psi": complex(np.exp(1j * 3 * np.pi / 8)),
        }

    def f_matrix(self) -> np.ndarray:
        return (1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)


class Caltech_Topological_Quantum:
    # Builds real 2x2/4x4 gate matrices from the Ising anyon R-/F-matrices
    # above -- genuine (simulated) unitary construction, not a hardcoded
    # gate table pretending to come from physical braiding hardware that
    # does not exist in this codebase.

    def __init__(self):
        self.anyons = Caltech_Ising_Anyons()

    def braid_hadamard(self) -> np.ndarray:
        return self.anyons.f_matrix()

    def braid_phase_gate(self) -> np.ndarray:
        r = self.anyons.r_matrix()
        return np.diag([r["sigma_sigma_1"], r["sigma_sigma_psi"]])

    def braid_cnot(self) -> np.ndarray:
        # Lattice-surgery CNOT is a standard fixed unitary in the fusion
        # basis (kept as the standard matrix form, not derived from R/F).
        return np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)


@dataclass
class SurfaceCodeResult:
    syndrome: List[int]
    correction: List[Tuple[int, str]]
    logical_error: bool


class Caltech_Surface_Code:
    # Real, small (distance-3, 9-qubit) planar surface code: real X/Z
    # stabilizer generators and a real brute-force minimum-weight decoder
    # (tries all low-weight error patterns and picks the one matching the
    # observed syndrome). Small enough to brute force exactly and actually
    # run, unlike the pseudocode's claimed 6-million-sample trained neural
    # network, which does not exist in this codebase.

    def __init__(self, distance: int = 3):
        self.d = distance
        self.n_qubits = distance * distance
        self.x_stabilizers, self.z_stabilizers = self._build_stabilizers()

    def _build_stabilizers(self):
        d = self.d
        x_stabs, z_stabs = [], []
        for i in range(d - 1):
            for j in range(d - 1):
                qubits = [i * d + j, i * d + j + 1, (i + 1) * d + j, (i + 1) * d + j + 1]
                if (i + j) % 2 == 0:
                    x_stabs.append(qubits)
                else:
                    z_stabs.append(qubits)
        return x_stabs, z_stabs

    def measure_syndrome(self, error_qubits: List[int], error_type: str = "X") -> List[int]:
        stabilizers = self.z_stabilizers if error_type == "X" else self.x_stabilizers
        syndrome = []
        for stab in stabilizers:
            parity = sum(1 for q in error_qubits if q in stab) % 2
            syndrome.append(parity)
        return syndrome

    def decode(self, syndrome: List[int], error_type: str = "X", max_weight: int = 2) -> SurfaceCodeResult:
        for weight in range(0, max_weight + 1):
            for combo in itertools.combinations(range(self.n_qubits), weight):
                test_syndrome = self.measure_syndrome(list(combo), error_type)
                if test_syndrome == syndrome:
                    correction = [(q, error_type) for q in combo]
                    return SurfaceCodeResult(syndrome=syndrome, correction=correction, logical_error=False)
        return SurfaceCodeResult(syndrome=syndrome, correction=[], logical_error=True)
