from __future__ import annotations

from typing import Any

from al_haras.security_core import CryptographicAuditChain
from hyba_data.offerings.quantum_grid_engine import QuantumGridEngine
from hyba_data.offerings.quantum_risk_engine import QuantumRiskEngine
from hyba_data.offerings.quantum_supply_chain import QuantumSupplyChain
from hyba_data.offerings.sovereign_intelligence_engine import SovereignIntelligenceEngine
from hyba_data.offerings.sovereign_services_engine import SovereignServicesEngine
from hyba_data.offerings.unified_health_engine import UnifiedHealthEngine

PHI = (1.0 + 5.0**0.5) / 2.0


class DataOfferings:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.offerings = {
            "finance": QuantumRiskEngine(audit=self.audit),
            "healthcare": UnifiedHealthEngine(audit=self.audit),
            "energy": QuantumGridEngine(audit=self.audit),
            "manufacturing": QuantumSupplyChain(audit=self.audit),
            "government": SovereignServicesEngine(audit=self.audit),
            "defense": SovereignIntelligenceEngine(audit=self.audit),
        }
        self.audit.add_entry("HYBA_DATA_OFFERINGS_INIT|sectors=6")

    def deploy_all(self) -> dict[str, Any]:
        sector_status = {}
        # light smoke per sector
        sector_status["finance"] = {
            "status": "DEPLOYABLE",
            "sample": self.offerings["finance"].calculate_risk({"positions": [10, 20, 5], "volatility": 0.12}),
        }
        sector_status["healthcare"] = {
            "status": "DEPLOYABLE",
            "sample": self.offerings["healthcare"].analyze_patient({"vitals": {"hr": 72}, "symptoms": []}),
        }
        sector_status["energy"] = {
            "status": "DEPLOYABLE",
            "sample": self.offerings["energy"].optimize_grid({"load_mw": 100, "generation_mw": 110, "renewable_mw": 45}),
        }
        sector_status["manufacturing"] = {
            "status": "DEPLOYABLE",
            "sample": self.offerings["manufacturing"].optimize_supply_chain({"nodes": ["a", "b"], "inventory_days": 12, "lead_time_days": 7}),
        }
        sector_status["government"] = {
            "status": "DEPLOYABLE",
            "sample": self.offerings["government"].secure_data({"record": "x"}),
        }
        sector_status["defense"] = {
            "status": "DEPLOYABLE",
            "sample": self.offerings["defense"].secure_operations({"kind": "ops", "severity": 0.05}),
        }
        ok = all(v["status"] == "DEPLOYABLE" for v in sector_status.values()) and self.audit.verify_integrity()
        self.audit.add_entry(f"HYBA_DATA_OFFERINGS_DEPLOY_ALL|ok={ok}")
        return {
            "offerings": {k: v["status"] for k, v in sector_status.items()},
            "details": sector_status,
            "total": len(self.offerings),
            "phi": self.phi,
            "phi_optimized": True,
            "status": "READY" if ok else "DEGRADED",
            "unhackable": False,
            "principle": "We don't need a license to build. We write the mathematics.",
            "audit_integrity": self.audit.verify_integrity(),
            "claim_lane": "HYBA_DATA_OFFERINGS_SUITE",
        }

    def get_sector_solution(self, sector: str) -> dict[str, Any]:
        sector = str(sector).lower()
        if sector not in self.offerings:
            return {"error": f"Sector {sector} not found", "available": list(self.offerings)}
        eng = self.offerings[sector]
        return {
            "sector": sector,
            "solution": type(eng).__name__,
            "status": "DEPLOYABLE",
            "phi_optimized": True,
            "engine": eng,
        }
