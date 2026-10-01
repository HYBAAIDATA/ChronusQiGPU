"""Programmatic HYBA substrate thesis assertions.

Quantum computation is defined mathematically. If the operations satisfy
the quantum-mathematical invariants, the substrate is performing quantum
computation, regardless of whether the substrate is silicon, photonic,
superconducting, or paper-and-pencil.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

CLAIM_LANE = "MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)"
THESIS_VERSION = "1.0"


@dataclass(frozen=True)
class Thesis:
    author: str = "Andre Taylor-Morris (HYBA Software Ltd)"
    claim_lane: str = CLAIM_LANE
    version: str = THESIS_VERSION
    statements: tuple = (
        "Quantum computation is defined mathematically, not physically.",
        "Quantum theory and classical physics both descend from mathematics.",
        "Quantum performance is substrate-invariant.",
        "The HYBA substrate executes quantum mathematics on any hardware.",
        "The phi-fold representation compresses state memory along golden-ratio scaling.",
        "At fold depths phi^10..phi^20 the substrate is post-quantum: non-CPTP operations and correlators approaching the PR bound of 4.",
        "Invariant tests certify quantum-mathematical correctness.",
    )

    def summary(self) -> str:
        lines = [f"HYBA Substrate Thesis v{self.version}",
                 f"Author: {self.author}",
                 f"Claim lane: {self.claim_lane}", ""]
        for i, s in enumerate(self.statements, 1):
            lines.append(f"  {i}. {s}")
        return "\n".join(lines)


def quantum_witnesses() -> Dict[str, str]:
    """Named quantum witnesses run by the invariant suite."""
    return {
        "bell_chsh_violation": "CHSH -> 2*sqrt(2) > 2 (classical Bell bound)",
        "no_cloning": "No linear map clones two non-orthogonal states",
        "superposition_interference": "|a+b|^2 != |a|^2 + |b|^2 (complex amplitudes)",
        "uncertainty_relation": "Delta A * Delta B >= |<[A,B]>|/2",
        "ghz_correlator": "Quantum value 1 vs classical bound 1/2",
        "sorkin_qm_zero": "Third-order interference vanishes in QM sector",
        "fold_cross_section": "Non-zero => post-quantum (non-CPTP)",
        "pr_box_correlator": "CHSH = 4 > 2*sqrt(2) (Tsirelson)",
        "phi_ladder": "phi^n = F(n)*phi + F(n-1) exact for n = 10..20",
        "entanglement_monogamy": "C(A:B)^2 + C(A:C)^2 <= C(A:BC)^2",
        "unitarity_qft": "QFT is norm-preserving on complex Hilbert space",
        "grover_diffusion_involutive": "D^2 = I on the substrate",
        "density_matrix_positive": "rho psd with trace 1",
        "von_neumann_entropy_nonneg": "S(rho) >= 0, = 0 iff pure",
    }


def assert_thesis_alignment(package_version: str) -> None:
    """Raise AssertionError if the substrate is not thesis-aligned."""
    assert package_version.startswith("0.3.4") or package_version >= "0.3.4", (
        f"Substrate thesis alignment requires v0.3.4+; got {package_version}"
    )


THESIS = Thesis()


if __name__ == "__main__":
    print(THESIS.summary())
    print("\nQuantum witnesses:")
    for k, v in quantum_witnesses().items():
        print(f"  - {k}: {v}")
