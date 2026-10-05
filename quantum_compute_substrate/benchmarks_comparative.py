"""
Comparative benchmarks against third-party quantum frameworks.

Provides adapter interfaces for Qiskit, Cirq, PennyLane, and physical
quantum-hardware providers (IBM Q, Rigetti). Adapters degrade gracefully
when the third-party package is not installed — they return a status of
"framework unavailable" instead of failing.

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC) — framework only. No cross-framework
benchmark numbers are baked in; users must run the adapters against their
own installed frameworks to obtain results.
"""

import time
import importlib
from typing import Any, Dict, Optional

import numpy as np

from .phi_tensor_core import QuantumFoldTensorCore, FoldState


def _try_import(name: str) -> Optional[Any]:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


class QiskitAdapter:
    """Adapter for Qiskit (IBM Q)."""

    def __init__(self):
        self.qiskit = _try_import("qiskit")
        self.available = self.qiskit is not None

    def status(self) -> Dict:
        return {"framework": "qiskit", "available": self.available}

    def grover_reference(self, n_qubits: int, target: int) -> Dict:
        """Grover search reference against Qiskit statevector simulator."""
        if not self.available:
            return {"error": "qiskit not installed", "available": False}
        return {"available": True, "note": "Adapter scaffold — user supplies circuit"}


class CirqAdapter:
    """Adapter for Google Cirq."""

    def __init__(self):
        self.cirq = _try_import("cirq")
        self.available = self.cirq is not None

    def status(self) -> Dict:
        return {"framework": "cirq", "available": self.available}


class PennyLaneAdapter:
    """Adapter for Xanadu PennyLane."""

    def __init__(self):
        self.pennylane = _try_import("pennylane")
        self.available = self.pennylane is not None

    def status(self) -> Dict:
        return {"framework": "pennylane", "available": self.available}


class RigettiAdapter:
    """Adapter for Rigetti pyQuil."""

    def __init__(self):
        self.pyquil = _try_import("pyquil")
        self.available = self.pyquil is not None

    def status(self) -> Dict:
        return {"framework": "pyquil", "available": self.available}


class ScalingStudy:
    """
    Systematic scaling study — measure per-op latency vs state-vector size.

    This complements the φ-scaling *mathematical* tiers with a real
    *hardware* scaling curve.
    """

    def __init__(self):
        pass

    def latency_curve(self, sizes=(64, 128, 256, 512, 1024, 2048)) -> Dict:
        """Measure Grover-diffusion latency for a range of state sizes."""
        results = {}
        for N in sizes:
            tc = QuantumFoldTensorCore(core_id=0, dim=N)
            state = FoldState(np.ones(N, dtype=np.complex128) / np.sqrt(N), 0, N)
            # Warmup
            tc.amplitude_amplification(state)
            # Timed run
            t0 = time.perf_counter()
            iterations = 100
            for _ in range(iterations):
                tc.amplitude_amplification(state)
            elapsed = time.perf_counter() - t0
            results[N] = {
                "iterations": iterations,
                "elapsed_s": elapsed,
                "per_iter_us": (elapsed / iterations) * 1e6,
                "ops_per_iter": 3 * N,
            }
        return results

    def fit_scaling_exponent(self, curve: Dict) -> Dict:
        """Fit log-log slope to characterise scaling."""
        sizes = np.array(sorted(curve.keys()))
        latencies = np.array([curve[s]["per_iter_us"] for s in sizes])
        # Log-log regression
        log_s = np.log(sizes)
        log_l = np.log(latencies)
        slope, intercept = np.polyfit(log_s, log_l, 1)
        return {
            "scaling_exponent": float(slope),
            "prefactor": float(np.exp(intercept)),
            "interpretation": (
                "exponent ≈ 1.0 confirms O(N) classical Grover diffusion"
                if 0.7 < slope < 1.3
                else f"unexpected scaling exponent {slope:.2f}"
            ),
            "sample_sizes": sizes.tolist(),
            "latencies_us": latencies.tolist(),
        }


class ComparativeBenchmarks:
    """Aggregate all comparative benchmarks and framework adapters."""

    def __init__(self):
        self.qiskit = QiskitAdapter()
        self.cirq = CirqAdapter()
        self.pennylane = PennyLaneAdapter()
        self.rigetti = RigettiAdapter()
        self.scaling = ScalingStudy()

    def framework_availability(self) -> Dict:
        return {
            "qiskit": self.qiskit.status(),
            "cirq": self.cirq.status(),
            "pennylane": self.pennylane.status(),
            "pyquil": self.rigetti.status(),
        }

    def run(self, sizes=(64, 128, 256, 512)) -> Dict:
        curve = self.scaling.latency_curve(sizes)
        scaling_fit = self.scaling.fit_scaling_exponent(curve)
        return {
            "framework_availability": self.framework_availability(),
            "scaling_curve": curve,
            "scaling_fit": scaling_fit,
            "claim_lane": "MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC) — measured on host CPU",
        }
