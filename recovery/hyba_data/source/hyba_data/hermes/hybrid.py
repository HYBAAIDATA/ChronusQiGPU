from __future__ import annotations

from typing import Any

import numpy as np

PHI = (1.0 + 5.0**0.5) / 2.0


class HermesHybrid:
    def __init__(self):
        self.phi = PHI
        self.cpp_engine = self._load_cpp_engine()

    def _load_cpp_engine(self) -> str:
        try:
            import hermes_cpp  # type: ignore

            return getattr(hermes_cpp, "ENGINE_ID", "C++_Engine_Loaded")
        except ImportError:
            return "C++_Engine_Python_Fallback"

    def quantum_simulate(self, qubits: int) -> np.ndarray:
        n = int(qubits)
        if n < 0 or n > 24:
            raise ValueError("qubits must be in [0, 24] for dense state vector")
        dim = 1 << n
        amplitudes = np.ones(dim, dtype=np.complex128) / np.sqrt(dim)
        return amplitudes

    def geodesic_search(self, query: np.ndarray) -> dict[str, Any]:
        q = np.asarray(query, dtype=np.float64).ravel()
        if q.size == 0:
            return {"results": [], "distances": []}
        # deterministic ranking by absolute coordinate magnitude
        order = np.argsort(-np.abs(q))
        top = order[: min(3, order.size)]
        distances = (np.abs(q[top]) / (np.linalg.norm(q) + 1e-12) / self.phi).tolist()
        return {"results": top.astype(int).tolist(), "distances": distances}

    def compress(self, data: np.ndarray) -> bytes:
        arr = np.asarray(data)
        header = f"HERMES_PHI|{self.phi:.10f}|{arr.shape}|{arr.dtype}".encode()
        payload = arr.tobytes(order="C")
        return header + b"\x00" + payload
