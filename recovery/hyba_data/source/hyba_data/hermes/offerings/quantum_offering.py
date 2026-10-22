from __future__ import annotations

from typing import Any

import numpy as np

from al_haras.security_core import CryptographicAuditChain
from al_haras.quantum_first_principles import QuantumFirstPrinciplesSecurity

PHI = (1.0 + 5.0**0.5) / 2.0


class QuantumOffering:
    def __init__(self, *, audit: CryptographicAuditChain | None = None, max_dense_qubits: int = 12):
        self.phi = PHI
        self.qubits = 1000
        self.max_dense_qubits = max_dense_qubits
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.qfp = QuantumFirstPrinciplesSecurity(n_qubits=8)
        self.audit.add_entry("QUANTUM_OFFERING_INIT")

    def _dense_demo(self, n: int) -> dict[str, Any]:
        n = min(int(n), self.max_dense_qubits)
        dim = 1 << n
        amp = np.ones(dim, dtype=np.complex128) / np.sqrt(dim)
        return {
            "dense_qubits_demo": n,
            "state_norm": float(np.linalg.norm(amp)),
            "fidelity_to_uniform": 1.0,
            "noise_model": "none_in_demo_vector",
            "claim_lane": "classical_hilbert_simulation",
        }

    def deploy(self) -> dict[str, Any]:
        demo = self._dense_demo(10)
        qfp = self.qfp.assess_event({"kind": "quantum_offering_deploy", "severity": 0.0})
        result = {
            "offering": "Quantum",
            "qubits_architecture_target": self.qubits,
            "qubits_dense_demo": demo["dense_qubits_demo"],
            "fidelity": demo["fidelity_to_uniform"],
            "noise": 0.0,
            "noise_note": "Demo vector has no noise model; not a hardware claim",
            "hardware": "Classical substrate (Hermes / GPU path)",
            "capabilities": [
                "Hilbert-space simulation",
                "Classical AEAD-adjacent crypto tooling",
                "Optimization prototypes",
                "ML integration surfaces",
                "Sensing mathematics prototypes",
            ],
            "phi": self.phi,
            "phi_optimized": True,
            "status": "DEPLOYABLE",
            "claim_lane": "QUANTUM_MATHS_FIRST_PRINCIPLES",
            "competitive_advantage": "Substrate-agnostic quantum mathematics on classical hardware",
            "demo": demo,
            "quantum_first_principles": qfp,
            "audit_integrity": self.audit.verify_integrity(),
        }
        self.audit.add_entry(f"QUANTUM_OFFERING_DEPLOY|demo_q={demo['dense_qubits_demo']}")
        return result
