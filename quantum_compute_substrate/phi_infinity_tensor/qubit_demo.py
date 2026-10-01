"""Concrete demonstration at 1000 qubits."""

from __future__ import annotations
from .qubit_scale import (
    QubitMPS,
    uniform_superposition,
    ghz_state,
    H_GATE,
)
from .phi_fold_compression import PhiFoldCompressor


def demonstrate_n_qubits(n: int = 1000, chi_max: int = 128) -> dict:
    """Initialise n qubits in |0...0>, apply Hadamards, then compress.

    Returns a metrics dict with measured (not asserted) memory numbers.
    """
    mps = QubitMPS(n_qubits=n, chi_max=chi_max)
    for k in range(n):
        mps.apply_single_qubit_gate(H_GATE, k)
    d = mps.describe()
    d["amplitude_all_zero"] = complex(mps.amplitude([0] * n))
    d["expected_z_qubit_0"] = mps.expectation_pauli_z(0)
    d["norm_squared"] = mps.norm_squared()
    return d


def demonstrate_compression_across_scales() -> list:
    """Compress product, Hadamard, and GHZ states at several sizes."""
    scales = [50, 100, 500]
    results = []
    for n in scales:
        for name, factory in [
            ("product |0..0>", lambda k: QubitMPS(n_qubits=k, chi_max=64)),
            ("|+>^n", lambda k: uniform_superposition(k, chi_max=64)),
            ("|GHZ_n>", lambda k: ghz_state(k, chi_max=64)),
        ]:
            mps = factory(n)
            comp = PhiFoldCompressor(fib_index=12, lossless_tolerance=1e-9)
            _, metrics = comp.compress(mps)
            results.append(
                {
                    "n": n,
                    "state": name,
                    "original_bytes": metrics.original_bytes,
                    "compressed_bytes": metrics.compressed_bytes,
                    "ratio": metrics.ratio,
                    "fidelity": metrics.fidelity,
                    "lossless": metrics.lossless,
                }
            )
    return results
