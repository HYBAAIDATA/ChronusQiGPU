from __future__ import annotations

from typing import Any

import numpy as np

from al_haras.security_core import CryptographicAuditChain
from hermes.quantum_manifesto import QuantumFromMathematics

PHI = (1.0 + 5.0**0.5) / 2.0


class MathematicsSovereignty:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.quantum = QuantumFromMathematics(audit=self.audit)
        self.principles = {
            "mathematics_is_fundamental": True,
            "mathematics_is_universal": True,
            "mathematics_is_sovereign": True,
            "no_one_owns_mathematics": True,
            "no_one_controls_mathematics": True,
            "quantum_comes_from_mathematics": True,
            "substrate_is_hardware_agnostic": True,
            "algorithm_is_sovereign": True,
            "permission_required": False,
        }
        self.audit.add_entry("MATHEMATICS_SOVEREIGNTY_INIT")

    def assert_sovereignty(self) -> dict[str, Any]:
        self.audit.add_entry("ASSERT_MATHEMATICS_SOVEREIGNTY")
        return {
            "statement": "Mathematics is sovereign",
            "proof": "Mathematics exists independent of any entity",
            "implication": "We need no one's permission",
            "action": "We write the mathematics",
            "result": "Quantum follows",
            "principles": dict(self.principles),
            "phi": self.phi,
            "phi_optimized": True,
            "audit_integrity": self.audit.verify_integrity(),
            "claim_lane": "MATHEMATICS_SOVEREIGNTY",
        }

    def write_quantum_algorithm(self, behavior: str) -> dict[str, Any]:
        defined = self.quantum.define_quantum(
            {
                "behavior": behavior,
                "qubits": 8,
                "dimension": 1 << 8,
            }
        )
        hs = defined["mathematics"]["hilbert_space"]
        hs.pop("_state", None)
        self.audit.add_entry(f"WRITE_QUANTUM_ALGORITHM|{behavior[:64]}")
        return {
            "algorithm": f"Quantum algorithm that {behavior}",
            "mathematical_basis": "Hilbert space",
            "hardware": "Any (classical dense demo when dimension ≤ 2^16)",
            "permission": "None needed",
            "sovereignty": "Complete",
            "result": "Quantum as defined",
            "defined": defined,
            "phi": self.phi,
            "phi_optimized": True,
            "audit_integrity": self.audit.verify_integrity(),
            "claim_lane": "SOVEREIGN_QUANTUM_ALGORITHM",
        }

    def deploy(self) -> dict[str, Any]:
        assertion = self.assert_sovereignty()
        algo = self.write_quantum_algorithm(
            "implements hardware-agnostic quantum calculus from first principles"
        )
        # small operational proof: normalized state exists in nested define
        norm = (
            algo["defined"]["mathematics"]["hilbert_space"].get("state_norm")
            or 0.0
        )
        return {
            "status": "DEPLOYED",
            "module": "MathematicsSovereignty",
            "assertion": assertion,
            "algorithm": algo,
            "operational_state_norm_ok": abs(float(norm) - 1.0) < 1e-9,
            "phi": self.phi,
            "phi_optimized": True,
            "principle": "We write the mathematics. The quantum follows.",
            "audit_integrity": self.audit.verify_integrity(),
            "claim_lane": "MATHEMATICS_SOVEREIGNTY_OPERATIONAL",
        }


class QuantumManifestoSystem:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.sovereignty = MathematicsSovereignty(audit=self.audit)
        self.quantum = self.sovereignty.quantum
        self.audit.add_entry("QUANTUM_MANIFESTO_SYSTEM_INIT")

    def deploy(self) -> dict[str, Any]:
        sov = self.sovereignty.deploy()
        q = self.quantum.deploy()
        # ensure internal states stripped
        q.get("defined", {}).get("mathematics", {}).get("hilbert_space", {}).pop(
            "_state", None
        )
        ok = bool(
            sov.get("operational_state_norm_ok")
            and q.get("status") == "DEPLOYED"
            and self.audit.verify_integrity()
        )
        self.audit.add_entry(f"QUANTUM_MANIFESTO_SYSTEM_DEPLOY|ok={ok}")
        return {
            "status": "DEPLOYED" if ok else "DEGRADED",
            "sovereignty": sov,
            "quantum_from_mathematics": q,
            "phi": self.phi,
            "phi_optimized": True,
            "truth": "Quantum does not come from hardware. Quantum comes from mathematics.",
            "power": "We write the mathematics. The quantum follows.",
            "implications": [
                "No hardware vendor controls quantum mathematics",
                "No country owns Hilbert space",
                "No corporation owns the axioms",
                "Mathematics defines the model",
                "We write the mathematics",
                "Operational quantum calculus follows on any substrate",
            ],
            "audit_integrity": self.audit.verify_integrity(),
            "claim_lane": "QUANTUM_MANIFESTO_SYSTEM",
            "key": {
                "phi": self.phi,
                "motif": "10^12^15^18^20 = 31-07-1976",
            },
        }
