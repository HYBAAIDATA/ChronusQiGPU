"""HYBA Data — Fold doctrine (machine-readable).

φ is an instruction: compress by folding, not by truncating.
Quantum serves data. Quantum comes from maths — substrate- and hardware-agnostic.
"""

from __future__ import annotations

from typing import Any, Dict

FOLD_DOCTRINE: Dict[str, Any] = {
    "instruction": "compress by folding, not by truncating",
    "primitive": "Golden Ratio Transform / Discrete φ-Fold (DφT / GRT)",
    "product": "PULVINI (engine) · HERMES (product face) · HYBA Data (company)",
    "fold_never_truncate": True,
    "quantum_serves_data": True,
    "quantum_from_maths": True,
    "substrate_agnostic": True,
    "hardware_agnostic": True,
    "no_physical_qubit_required": True,
    "mining_bound": False,
    "repo_paths": {
        "engine": "python_backend/phi_folding_engine/",
        "ufe": "python_backend/phi_folding_engine/ufe.py",
        "hyperbolic": "python_backend/phi_folding_engine/hyperbolic_nd.py",
        "holograph": "python_backend/phi_folding_engine/holograph_nd.py",
        "cf_tower": "python_backend/phi_folding_engine/cf_tower_iir.py",
        "zphi_exact": "python_backend/phi_folding_engine/zphi_exact.py",
        "honest_quantum": "python_backend/hyba_data/quantum_honest.py",
        "qatl": "python_backend/hyba_data/quantum_adaptive_tensor.py",
    },
    "frontier_program": [
        "hyperbolic_phi_folding_nd",
        "infinite_depth_cf_tower",
        "quantum_phi_folding_algebra",
        "fractal_phi_holography",
        "zphi_integer_exact",
        "biological_phi_compression",
        "experimental_validation_at_scale",
    ],
    "data_impacts": {
        "storage": "store folded state + reconstruct by unfold; not hoard-all raw",
        "security": "topology / number-theoretic integrity; PQC-era readiness posture",
        "search": "navigation on folded manifold; structure-first then grover-cost sim",
        "processing": "optimization and simulation via φ-elevated tensors",
    },
}


def describe_fold_doctrine() -> Dict[str, Any]:
    return dict(FOLD_DOCTRINE)


def assert_fold_not_truncate(recon_error: float, max_err: float = 1e-6) -> bool:
    """Gate: reconstruction error must stay bounded — fold, not truncate."""
    if recon_error != recon_error:  # NaN
        raise ValueError("recon_error is NaN — not a valid fold")
    if recon_error > max_err:
        raise PermissionError(
            f"recon_error {recon_error} exceeds fold gate {max_err} — truncation-like loss"
        )
    return True
