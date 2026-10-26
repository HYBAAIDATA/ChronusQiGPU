from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

import numpy as np

PHI = (1.0 + 5.0**0.5) / 2.0


def _load_qms():
    path = Path(__file__).resolve().parent / "security" / "quantum_math_security.py"
    spec = importlib.util.spec_from_file_location("al_haras_qms_direct", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_QMS = _load_qms()
QuantumState = _QMS.QuantumState
QuantumInterferenceDetector = _QMS.QuantumInterferenceDetector
QuantumWalkSecurityAnalyzer = _QMS.QuantumWalkSecurityAnalyzer
QuantumHashFunction = _QMS.QuantumHashFunction


class QuantumFirstPrinciplesSecurity:
    def __init__(self, *, n_qubits: int = 8):
        self.phi = PHI
        self.n_qubits = int(n_qubits)
        dim = 1 << self.n_qubits
        amps = np.ones(dim, dtype=np.complex128)
        self.state = QuantumState(amplitudes=amps)
        self.interference = QuantumInterferenceDetector(n_paths=min(32, dim))
        self.walk = QuantumWalkSecurityAnalyzer(graph_size=min(64, dim))
        self.qhash = QuantumHashFunction(output_size=256)
        baseline = list(np.sin(np.linspace(0.0, 2.0 * np.pi, 64)))
        self.interference.establish_baseline(baseline)
        self.walk.initialize_walk(start_node=0)
        self._events = 0

    def hilbert_fingerprint(self, payload: bytes) -> dict[str, Any]:
        digest = hashlib.sha256(payload).digest()
        dim = len(self.state.amplitudes)
        coeffs = np.zeros(dim, dtype=np.complex128)
        for i, b in enumerate(digest):
            coeffs[i % dim] += (b + 1j * ((b * 7) % 256)) / 255.0
        probe = QuantumState(amplitudes=coeffs)
        fid = float(self.state.fidelity(probe))
        ip = complex(self.state.inner_product(probe))
        return {
            "fidelity": fid,
            "inner_product_abs": float(abs(ip)),
            "norm": float(np.linalg.norm(probe.amplitudes)),
            "qhash": self.qhash.hash(payload),
            "claim_lane": "first_principles_hilbert",
        }

    def interfere(self, series: list[float]) -> dict[str, Any]:
        if len(series) < 4:
            series = list(series) + [0.0] * (4 - len(series))
        anomalous, score = self.interference.detect_anomaly([float(x) for x in series])
        pattern = self.interference.compute_interference_pattern([float(x) for x in series])
        return {
            "anomaly": bool(anomalous),
            "score": float(score),
            "pattern_energy": float(np.linalg.norm(np.asarray(pattern))),
            "claim_lane": "quantum_interference",
        }

    def walk_pattern(self, series: list[float]) -> dict[str, Any]:
        if len(series) < 2:
            series = [0.0, 1.0]
        analysis = self.walk.analyze_pattern([float(x) for x in series])
        self.walk.step_walk(steps=1)
        return {
            "analysis": analysis,
            "claim_lane": "quantum_walk",
        }

    def assess_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self._events += 1
        raw = repr(sorted(event.items())).encode()
        fp = self.hilbert_fingerprint(raw)
        sev = float(event.get("severity", 0.0) or 0.0)
        series = [
            sev,
            float(len(str(event.get("source", "")))) / 32.0,
            float(len(str(event.get("vector", "")))) / 32.0,
            float(hash(str(event.get("kind", ""))) % 1000) / 1000.0,
        ]
        # expand series deterministically from payload bytes
        for b in hashlib.sha256(raw).digest()[:16]:
            series.append(b / 255.0)
        interf = self.interfere(series)
        walk = self.walk_pattern(series)
        kind = str(event.get("kind", "")).lower()
        benign_kinds = {"heartbeat", "deploy_probe", "quantum_offering_deploy", "health", "ping"}
        if kind in benign_kinds and sev < 0.35:
            hostile = False
        else:
            hostile = bool(
                interf["anomaly"]
                or fp["fidelity"] < 0.85
                or sev >= 0.35
                or kind in {"attack", "probe", "exploit", "scan", "intrusion", "recon", "breach"}
            )
        return {
            "hilbert": fp,
            "interference": interf,
            "walk": walk,
            "hostile_geometry": hostile,
            "phi": self.phi,
            "n_qubits": self.n_qubits,
            "events_seen": self._events,
            "substrate": "classical_hilbert_first_principles",
            "claim_lane": "quantum_maths_first_principles",
        }
