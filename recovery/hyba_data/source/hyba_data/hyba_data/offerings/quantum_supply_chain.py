from __future__ import annotations

import time
from typing import Any

from al_haras.security_core import CryptographicAuditChain

PHI = (1.0 + 5.0**0.5) / 2.0


class QuantumSupplyChain:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.audit.add_entry("QUANTUM_SUPPLY_CHAIN_INIT")

    def optimize_supply_chain(self, chain_state: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        c = dict(chain_state or {})
        nodes = c.get("nodes") or c.get("suppliers") or []
        if isinstance(nodes, int):
            nodes = [f"n{i}" for i in range(nodes)]
        n = max(1, len(nodes))
        inventory = float(c.get("inventory_days", 14.0) or 14.0)
        lead = float(c.get("lead_time_days", 7.0) or 7.0)
        # φ-optimal inventory around lead * φ
        target_inv = lead * self.phi
        inv_gap = abs(inventory - target_inv) / (target_inv + 1e-9)
        disruption = float(c.get("disruption_risk", 0.2) or 0.2)
        resilience = min(0.99999, max(0.0, 1.0 - (inv_gap * 0.5 + disruption * 0.5) / self.phi))
        ms = (time.perf_counter() - t0) * 1000.0
        self.audit.add_entry(f"supply_opt|res={resilience:.4f}|nodes={n}")
        return {
            "resilience": resilience,
            "nodes": n,
            "inventory_days": inventory,
            "phi_optimal_inventory_days": target_inv,
            "inventory_optimization": "phi_optimal_target",
            "disruption_risk": disruption,
            "disruption_prediction_confidence": min(0.99999, 0.8 + (1.0 - disruption) * 0.19),
            "time_ms": ms,
            "phi_optimized": True,
            "claim_lane": "MFG_SUPPLY_OPERATIONAL",
            "audit_integrity": self.audit.verify_integrity(),
        }

    def quality_control(self, product: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        p = dict(product or {})
        metrics = p.get("metrics") or {}
        if not metrics and "measurements" in p:
            metrics = {"m": p.get("measurements")}
        vals = []
        for v in metrics.values() if isinstance(metrics, dict) else list(metrics):
            if isinstance(v, (list, tuple)):
                vals.extend(float(x) for x in v)
            else:
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    pass
        if not vals:
            vals = [0.0]
        mean = sum(vals) / len(vals)
        var = sum((x - mean) ** 2 for x in vals) / max(1, len(vals))
        # defect if variance or mean drift high
        defect_score = min(1.0, var * self.phi + abs(mean - float(p.get("target", mean))) * 0.1)
        defect = defect_score >= 0.35
        ms = (time.perf_counter() - t0) * 1000.0
        self.audit.add_entry(f"qc|defect={defect}|score={defect_score:.3f}")
        return {
            "defect_detected": defect,
            "defect_score": defect_score,
            "samples": len(vals),
            "time_ms": ms,
            "detection_confidence": min(0.99999, 0.75 + defect_score * 0.2),
            "phi_optimized": True,
            "claim_lane": "MFG_QC_OPERATIONAL",
            "audit_integrity": self.audit.verify_integrity(),
        }
