from __future__ import annotations

from typing import Any

from al_haras.security_core import CryptographicAuditChain
from intelligence.unified_security import UnifiedIntelligenceSecurity

PHI = (1.0 + 5.0**0.5) / 2.0


class SovereignIntelligenceEngine:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.unified = UnifiedIntelligenceSecurity(audit=self.audit, n_agents=12, n_nodes=10)
        self.audit.add_entry("SOVEREIGN_INTELLIGENCE_ENGINE_INIT")

    def analyze_intelligence(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        data = dict(data or {})
        # map intel packet onto threat detect path
        threat = {
            "kind": data.get("kind", data.get("type", "probe")),
            "source": data.get("source", data.get("origin", "unknown")),
            "target": data.get("target", "sovereign-core"),
            "vector": data.get("vector", data.get("indicator", "unknown")),
            "severity": float(data.get("severity", data.get("priority", 0.5)) or 0.5),
            "payload": data.get("payload", data.get("snippet", "")),
        }
        out = self.unified.detect_threat(threat)
        self.audit.add_entry(
            f"intel_analyze|moria={out.get('you_shall_not_pass')}|pred={out.get('threat_detected')}"
        )
        return {
            "threat_detection": "pre_emptive" if out.get("threat_detected") else "clear",
            "you_shall_not_pass": out.get("you_shall_not_pass"),
            "gandalf_moria": out.get("gandalf_moria"),
            "confidence": out.get("confidence"),
            "intelligence": "six_form_unified",
            "six_intelligences": list(out.get("intelligence_results", {}).keys()),
            "five_form_swarm": out.get("five_form_swarm"),
            "phi_optimized": True,
            "unhackable": False,
            "claim_lane": "DEFENSE_INTEL_OPERATIONAL",
            "audit_integrity": self.audit.verify_integrity(),
            "raw": out,
        }

    def secure_operations(self, operation: dict[str, Any] | None = None) -> dict[str, Any]:
        operation = dict(operation or {})
        secured = self.unified.secure_system(operation)
        self.audit.add_entry(f"ops_secure|{secured.get('status')}")
        return {
            "security": "six_intel_plus_mesh_plus_audit",
            "status": secured.get("status"),
            "audit": "AL_HARAS",
            "mesh": secured.get("mesh"),
            "gandalf_moria": secured.get("gandalf_moria"),
            "unhackable": False,
            "phi_optimized": True,
            "claim_lane": "DEFENSE_OPS_OPERATIONAL",
            "audit_integrity": self.audit.verify_integrity(),
            "evidence_ok": secured.get("evidence_ok"),
        }
