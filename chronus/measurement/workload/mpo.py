"""MPO application throughput — real operator applied to a real MPS.

Invariants:
    MPO1: every MPO measurement includes the MPO and MPS shapes.
"""

from __future__ import annotations

from typing import Any, Dict

from .._common import distribution_of, timed_calls, unavailable


def measure_mpo_apply(
    n_sites: int = 8,
    mpo_kind: str = "ising",
    repeats: int = 8,
) -> Dict[str, Any]:
    """Time ``apply_to_mps`` on an Ising MPO against a real MPS core list."""
    try:
        from quantum_compute_substrate.phi_infinity_tensor import QubitMPS
        from quantum_compute_substrate.pulvini import IsingHamiltonianMPO
    except Exception as exc:
        return unavailable(f"quantum_compute_substrate import failed: {exc}")

    mpo = IsingHamiltonianMPO(num_sites=n_sites)
    mps = QubitMPS(n_qubits=n_sites, chi_max=8)
    cores = [site for site in mps.sites]

    durations_ns = timed_calls(lambda: mpo.apply_to_mps([c.copy() for c in cores]), repeats)
    apply_ns = distribution_of(durations_ns)
    mpo_shape = [n_sites]
    mps_shape = [n_sites, int(mps.sites[0].shape[0]) if mps.sites else 0]
    return {
        "available": True,
        "mpo_kind": mpo_kind,
        "mpo_shape": mpo_shape,
        "mps_shape": mps_shape,
        "apply_time_ns": apply_ns.as_dict(),
        "applications_per_second": distribution_of(
            [1e9 / d for d in durations_ns if d > 0]
        ).as_dict(),
        "method": "IsingHamiltonianMPO.apply_to_mps(QubitMPS cores)",
    }
