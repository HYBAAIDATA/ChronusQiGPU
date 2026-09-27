"""
Unified Clay checklist. Status is pulled dynamically from the modules
that implement each item. No item may be labelled ESTABLISHED unless a
continuum proof exists in this codebase. Since none does, 0 items are
ESTABLISHED.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any

# Ensure workspace root is in sys.path
_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@dataclass
class ChecklistItem:
    id: str
    description: str
    status: str  # present | open | partial
    scope: str  # LATTICE_THEOREM | LATTICE_VERIFIED | EXACT_ARITHMETIC
    # | EXTRAPOLATED_NOT_ESTABLISHED | FINITE_VOLUME_CHECK
    # | FINITE_VOLUME_CONSTRUCTED | CONTINUUM_OPEN
    module: str
    test: str
    honesty_note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "scope": self.scope,
            "module": self.module,
            "test": self.test,
            "honesty_note": self.honesty_note,
        }


# =============================================================================
# CLOSED ITEMS (lattice-level, already in main branch)
# =============================================================================

CLOSED_ITEMS = {
    "C1_lattice_regularized_yang_mills": ChecklistItem(
        id="C1",
        description="Lattice-regularized pure Yang-Mills action and measure",
        status="present",
        scope="LATTICE_THEOREM",
        module="yang_mills_lattice_extensions.py",
        test="test_yang_mills_lattice.py",
        honesty_note="Wilson action on 4D lattice. Continuum limit not constructed.",
    ),
    "C2_reflection_positivity": ChecklistItem(
        id="C2",
        description="Osterwalder-Seiler reflection positivity",
        status="present",
        scope="LATTICE_THEOREM",
        module="yang_mills_continuum_bridge.py::ReflectionPositivityVerifier",
        test="test_yang_mills_continuum_bridge.py",
        honesty_note="Proved on the lattice (Osterwalder-Seiler 1978). Continuum reconstruction open.",
    ),
    "C3_transfer_matrix_positive": ChecklistItem(
        id="C3",
        description="Positive transfer matrix on the lattice",
        status="present",
        scope="LATTICE_THEOREM",
        module="yang_mills_continuum_bridge.py::TransferMatrix",
        test="test_yang_mills_continuum_bridge.py",
        honesty_note="Finite-volume transfer matrix is positive by construction.",
    ),
    "C4_gap_on_finite_lattice": ChecklistItem(
        id="C4",
        description="Spectral gap on the finite lattice",
        status="present",
        scope="LATTICE_VERIFIED",
        module="ricci_yang_mills_flow.py::spectral_gap",
        test="test_ricci_yang_mills_flow.py",
        honesty_note="Δ computed exactly on ℂ³². Continuum value not established.",
    ),
    "C5_soliton_condition": ChecklistItem(
        id="C5",
        description="Spectral soliton [H, Φ] = 0",
        status="present",
        scope="LATTICE_VERIFIED",
        module="ricci_yang_mills_flow.py::spectral_soliton_residual",
        test="test_ricci_yang_mills_flow.py",
        honesty_note="Commutator condition verified on ℂ³². Continuum soliton not established.",
    ),
    "C6_holographic_entropy": ChecklistItem(
        id="C6",
        description="Ryu-Takayanagi entropy via graph min-cut",
        status="present",
        scope="LATTICE_VERIFIED",
        module="ricci_yang_mills_flow.py::holographic_entropy",
        test="test_ricci_yang_mills_flow.py",
        honesty_note="Exact min-cut on M32. Continuum holography not established.",
    ),
    "C7_golden_algebra": ChecklistItem(
        id="C7",
        description="Golden algebra (Binet, Cassini, Pisot, Zeckendorf)",
        status="present",
        scope="EXACT_ARITHMETIC",
        module="golden_algebra_basis.py",
        test="test_golden_transform_exactness_hardening.py",
        honesty_note="Exact integer arithmetic. Theorems verified for n in [1,100].",
    ),
    "C8_landau_gauge_fixing": ChecklistItem(
        id="C8",
        description="Landau gauge fixing on the lattice",
        status="present",
        scope="LATTICE_THEOREM",
        module="yang_mills_lattice_extensions.py::landau_gauge_fix",
        test="test_yang_mills_lattice.py",
        honesty_note="Gauge fixing verified on the lattice. Gribov copies unresolved.",
    ),
    "C9_thermalization": ChecklistItem(
        id="C9",
        description="Metropolis thermalization on SU(3) lattices",
        status="present",
        scope="LATTICE_VERIFIED",
        module="yang_mills_lattice_extensions.py::thermalize",
        test="test_yang_mills_thermalization.py",
        honesty_note="Ensemble thermalized at fixed a. Continuum limit not constructed.",
    ),
    "C10_written_proof_object": ChecklistItem(
        id="C10",
        description="Written proof object (ContinuumBridgeReport + API_REFERENCE)",
        status="partial",
        scope="CONTINUUM_OPEN",
        module="yang_mills_continuum_bridge.py::ContinuumBridgeReport",
        test="test_yang_mills_continuum_bridge.py",
        honesty_note=(
            "The report is written. The proof object contains finite-volume "
            "evidence and extrapolations. It does NOT constitute a Clay proof."
        ),
    ),
}


# =============================================================================
# OPEN GAPS (continuum obligations, dynamically linked to modules)
# =============================================================================

OPEN_GAPS = {
    "G1_continuum_limit": ChecklistItem(
        id="G1",
        description="Continuum limit a→0",
        status="partial",
        scope="EXTRAPOLATED_NOT_ESTABLISHED",
        module="yang_mills_continuum_limit.py::ContinuumLimit",
        test="test_yang_mills_continuum_limits.py::TestContinuumExtrapolations",
        honesty_note=(
            "Extrapolation framework built. Finite-a sequence extrapolated. "
            "Proof that the limit exists is not provided."
        ),
    ),
    "G2_infinite_volume_limit": ChecklistItem(
        id="G2",
        description="Infinite-volume limit L→∞",
        status="partial",
        scope="EXTRAPOLATED_NOT_ESTABLISHED",
        module="yang_mills_continuum_limit.py::InfiniteVolumeLimit",
        test="test_yang_mills_continuum_limits.py::TestContinuumExtrapolations",
        honesty_note=(
            "Extrapolation framework built. Finite-L sequence extrapolated. "
            "Proof that the mass gap persists as L→∞ is not provided."
        ),
    ),
    "G3_os_reconstruction": ChecklistItem(
        id="G3",
        description="Osterwalder-Schrader reconstruction theorem",
        status="partial",
        scope="FINITE_VOLUME_CONSTRUCTED",
        module="yang_mills_wightman_check.py::OSReconstructionCertificate",
        test="test_yang_mills_continuum_limits.py::TestHilbertSpaceAndAxioms",
        honesty_note=(
            "Finite-volume Hilbert space constructed from transfer matrix. "
            "Continuum reconstruction theorem not proved."
        ),
    ),
    "G4_nonperturbative_renormalization": ChecklistItem(
        id="G4",
        description="Non-perturbative renormalization of composite operators",
        status="present",
        scope="LATTICE_VERIFIED",
        module="yang_mills_ri_mom.py::RIMOMRenormalization",
        test="test_yang_mills_continuum_limits.py::TestRIMOM",
        honesty_note=(
            "RI/MOM Z-factors computed on lattice. Continuum limit of Z_O "
            "and scheme matching to MS-bar are applied but not proved to converge."
        ),
    ),
    "G5_continuum_mass_gap": ChecklistItem(
        id="G5",
        description="Mass gap Δ > 0 in continuum",
        status="partial",
        scope="EXTRAPOLATED_NOT_ESTABLISHED",
        module="yang_mills_continuum_limit.py::ContinuumMassGapCertificate",
        test="test_yang_mills_continuum_limits.py::TestContinuumExtrapolations",
        honesty_note=(
            "Double extrapolation (a→0, L→∞) performed. If positive, "
            "the value is EXTRAPOLATED, not proved."
        ),
    ),
    "G6_wightman_axioms": ChecklistItem(
        id="G6",
        description="Wightman axioms in reconstructed QFT",
        status="partial",
        scope="FINITE_VOLUME_CHECK",
        module="yang_mills_wightman_check.py::WightmanAxiomCheck",
        test="test_yang_mills_continuum_limits.py::TestHilbertSpaceAndAxioms",
        honesty_note=(
            "Wightman axioms checked at finite lattice volume. None are "
            "established in the continuum limit."
        ),
    ),
}


# =============================================================================
# DYNAMIC STATUS (pulls from live modules where possible)
# =============================================================================


def _dynamic_g4_status() -> Dict[str, Any]:
    """
    G4 is the only gap with a live computation. Confirm the RI/MOM
    module loads and reports LATTICE_VERIFIED scope.
    """
    try:
        from python_backend.hyba.quantum.yang_mills_ri_mom import (
            RIMOMRenormalization,
            LatticeMomentum,
        )

        configs = [{"id": i} for i in range(4)]
        ri = RIMOMRenormalization(configs, beta=2.3, L=16)
        mom = LatticeMomentum(n=[1, 0, 0, 0], L=16)
        result = ri.compute_Z("scalar", mom)
        return {
            "live": True,
            "scope": result.scope,
            "Z": result.Z,
            "honesty_note": result.honesty_note,
        }
    except Exception as e:
        return {
            "live": False,
            "error": str(e),
            "scope": "CONTINUUM_OPEN",
        }


def _dynamic_g6_status() -> Dict[str, Any]:
    """G6 - confirm Wightman checker runs and flags continuum_open."""
    try:
        from python_backend.hyba.quantum.yang_mills_wightman_check import (
            WightmanAxiomCheck,
        )

        checker = WightmanAxiomCheck([1.0, 0.8, 0.64], 0.1)
        result = checker.check_all()
        open_axioms = [
            k for k, v in result.items() if isinstance(v, dict) and v.get("continuum_open", False)
        ]
        return {
            "live": True,
            "scope": result["scope"],
            "open_axioms": open_axioms,
            "n_open": len(open_axioms),
        }
    except Exception as e:
        return {
            "live": False,
            "error": str(e),
            "scope": "CONTINUUM_OPEN",
        }


# =============================================================================
# PUBLIC API
# =============================================================================


def clay_status() -> Dict[str, Any]:
    """
    Return the full Clay checklist status.

    Guarantees:
      - No item is labelled ESTABLISHED
      - Every item has a scope label and an honesty_note
      - Live modules are queried where possible (G4, G6)
    """
    all_items = {**CLOSED_ITEMS, **OPEN_GAPS}

    by_scope: Dict[str, list] = {}
    for key, item in all_items.items():
        by_scope.setdefault(item.scope, []).append(item.id)

    established = [i.id for i in all_items.values() if i.scope == "ESTABLISHED"]
    continuum_open = [
        i.id
        for i in all_items.values()
        if i.scope in ("CONTINUUM_OPEN", "EXTRAPOLATED_NOT_ESTABLISHED")
    ]

    return {
        "total_items": len(all_items),
        "established_items": established,
        "established_count": len(established),
        "no_established_items": len(established) == 0,
        "continuum_open_count": len(continuum_open),
        "continuum_open_ids": continuum_open,
        "by_scope": by_scope,
        "live_checks": {
            "G4_ri_mom": _dynamic_g4_status(),
            "G6_wightman": _dynamic_g6_status(),
        },
        "honesty_note": (
            "This checklist locates the 6 continuum obligations to a Clay "
            "proof. G4 is the only item with a live lattice computation. "
            "G1, G2, G3, G5, G6 require mathematical breakthroughs, not "
            "engineering. 0 items are ESTABLISHED."
        ),
    }


def assert_no_established() -> None:
    """
    CI guard. Raise if any item is labelled ESTABLISHED.
    This function is called from tests and CI to enforce the discipline.
    """
    status = clay_status()
    if not status["no_established_items"]:
        raise AssertionError(
            f"ESTABLISHED items found in Clay checklist: "
            f"{status['established_items']}. "
            f"No item may be labelled ESTABLISHED without a continuum proof."
        )


if __name__ == "__main__":
    import json

    print(json.dumps(clay_status(), indent=2, default=str))
