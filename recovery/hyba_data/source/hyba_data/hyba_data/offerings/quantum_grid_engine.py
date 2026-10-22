from __future__ import annotations

import time
from typing import Any

from al_haras.security_core import CryptographicAuditChain

PHI = (1.0 + 5.0**0.5) / 2.0


class QuantumGridEngine:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.audit.add_entry("QUANTUM_GRID_ENGINE_INIT")

    def optimize_grid(self, grid_state: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        g = dict(grid_state or {})
        load = float(g.get("load_mw", 100.0) or 100.0)
        gen = float(g.get("generation_mw", 105.0) or 105.0)
        renewable = float(g.get("renewable_mw", 40.0) or 40.0)
        reserve = gen - load
        balance = 1.0 - min(1.0, abs(reserve) / (load + 1e-9))
        ren_frac = min(1.0, renewable / (gen + 1e-9))
        stability = min(0.99999, (balance * 0.7 + ren_frac / self.phi * 0.3 + 0.5))
        # carbon reduction proxy vs fossil-only baseline
        carbon_reduction = min(0.999, ren_frac * (1.0 - 1.0 / (self.phi + 1.0)))
        ms = (time.perf_counter() - t0) * 1000.0
        self.audit.add_entry(f"grid_opt|stab={stability:.4f}|ren={ren_frac:.3f}")
        return {
            "stability": stability,
            "reserve_mw": reserve,
            "renewable_fraction": ren_frac,
            "renewable_integration": "optimal" if ren_frac >= 0.3 and reserve >= 0 else "constrained",
            "carbon_reduction": carbon_reduction,
            "time_ms": ms,
            "phi_optimized": True,
            "claim_lane": "ENERGY_GRID_OPERATIONAL",
            "note": "Operational balance model — not a grid-code certified controller",
            "audit_integrity": self.audit.verify_integrity(),
        }

    def predict_maintenance(self, equipment: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        e = dict(equipment or {})
        temp = float(e.get("temp_c", 60.0) or 60.0)
        vib = float(e.get("vibration", 0.2) or 0.2)
        age = float(e.get("age_years", 5.0) or 5.0)
        score = min(1.0, (temp / 120.0) * 0.4 + vib * 0.4 + (age / 40.0) * 0.2)
        score = score * (1.0 / self.phi) + score
        score = min(1.0, score)
        predicted = score >= 0.55
        hours = max(1.0, (1.0 - score) * 72.0 * self.phi)
        ms = (time.perf_counter() - t0) * 1000.0
        self.audit.add_entry(f"maint_pred|{predicted}|score={score:.3f}")
        return {
            "failure_predicted": predicted,
            "confidence": min(0.99999, 0.7 + score * 0.29),
            "risk_score": score,
            "time_window_hours": hours,
            "time_ms": ms,
            "phi_optimized": True,
            "claim_lane": "ENERGY_MAINT_OPERATIONAL",
            "audit_integrity": self.audit.verify_integrity(),
        }
