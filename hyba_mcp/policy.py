"""Resource gate for the TURING maths wrapper.

Walls here are memory limits of this process, not a vendor quota. TURING stops
at finite-dimensional complex operators, so a hardware backend is refused.
"""

from __future__ import annotations

from typing import Any

STATEVECTOR = "statevector"
EXECUTE_MAX_QUBITS = 12
UNITARY_BUILD_MAX_QUBITS = 6
COST_REPORT_MAX_QUBITS = 30
AMPLITUDE_RETURN_MAX_QUBITS = 8
MAX_GATES = 64
BYTES_PER_COMPLEX = 16

SUPPORTED_BACKENDS = (STATEVECTOR,)


def memory_estimate(n_qubits: int) -> dict[str, int]:
    """Byte estimates for a dense state and, when small enough, a dense operator."""
    amplitudes = 1 << n_qubits
    estimate = {
        "statevector_complex_amplitudes": amplitudes,
        "statevector_bytes": amplitudes * BYTES_PER_COMPLEX,
    }
    if n_qubits <= UNITARY_BUILD_MAX_QUBITS:
        entries = amplitudes * amplitudes
        estimate["dense_operator_entries"] = entries
        estimate["dense_operator_bytes"] = entries * BYTES_PER_COMPLEX
    return estimate


def check_request(backend: str, n_qubits: int, *, operation: str) -> dict[str, Any]:
    """Return an allow/deny record. Does not allocate a state or an operator."""
    if not isinstance(n_qubits, int) or isinstance(n_qubits, bool):
        raise ValueError("n_qubits must be an integer")
    if n_qubits < 1 or n_qubits > COST_REPORT_MAX_QUBITS:
        raise ValueError(
            f"n_qubits must be between 1 and {COST_REPORT_MAX_QUBITS}"
        )
    if not isinstance(backend, str) or not backend:
        raise ValueError("backend must be a non-empty string")

    memory = memory_estimate(n_qubits)
    base = {
        "backend": backend,
        "operation": operation,
        "n_qubits": n_qubits,
        "memory": memory,
        "hardware": False,
        "sampling": False,
    }
    if backend != STATEVECTOR:
        if backend == "density" or backend.startswith("qpu:"):
            reason = (
                "unsupported backend: this wrapper stops at the TURING maths "
                "layer and has no density-matrix or hardware submission path"
            )
        else:
            reason = f"unknown backend: {backend}"
        return {**base, "decision": "deny", "execute_allowed": False, "reason": reason}

    if n_qubits > EXECUTE_MAX_QUBITS:
        return {
            **base,
            "decision": "deny",
            "execute_allowed": False,
            "reason": (
                f"statevector execution is limited to {EXECUTE_MAX_QUBITS} qubits "
                "in this wrapper; no state was allocated"
            ),
        }
    return {
        **base,
        "decision": "allow",
        "execute_allowed": True,
        "reason": None,
    }
