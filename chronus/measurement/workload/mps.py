"""MPS gate-application throughput — real QubitMPS work on the substrate.

Invariants:
    MPS1: every MPS measurement includes n_qubits and chi_max.
    MPS2: the measurement is repeated, not single-shot.
"""

from __future__ import annotations

from typing import Any, Dict

from .._common import distribution_of, timed_calls, unavailable


def measure_mps_gate(
    n_qubits: int = 32,
    chi_max: int = 32,
    repeats: int = 16,
) -> Dict[str, Any]:
    """Time one-qubit Hadamard applications on a real MPS.

    Lazily binds the substrate so importing this module never hard-fails when
    the substrate is absent — the workload reports unavailable instead.
    """
    try:
        from quantum_compute_substrate.phi_infinity_tensor import H_GATE, QubitMPS
    except Exception as exc:  # substrate absent or broken — say so
        return unavailable(f"quantum_compute_substrate import failed: {exc}")

    mps = QubitMPS(n_qubits=n_qubits, chi_max=chi_max)
    durations_ns = timed_calls(lambda: mps.apply_single_qubit_gate(H_GATE, 0), repeats)
    gate_ns = distribution_of(durations_ns)
    gps = distribution_of([1e9 / d for d in durations_ns if d > 0])
    return {
        "available": True,
        "n_qubits": n_qubits,
        "chi_max": chi_max,
        "gate_time_ns": gate_ns.as_dict(),
        "gates_per_second": gps.as_dict(),
        "method": "quantum_compute_substrate.QubitMPS.apply_single_qubit_gate(H@q0)",
    }
