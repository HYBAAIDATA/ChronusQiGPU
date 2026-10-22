from __future__ import annotations

import hashlib
import math
import time
from typing import Any

from al_haras.security_core import CryptographicAuditChain

PHI = (1.0 + 5.0**0.5) / 2.0


class QuantumRiskEngine:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.audit.add_entry("QUANTUM_RISK_ENGINE_INIT")

    def calculate_risk(self, portfolio: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        portfolio = dict(portfolio or {})
        positions = portfolio.get("positions") or portfolio.get("assets") or []
        if isinstance(positions, dict):
            positions = [{"symbol": k, "value": v} for k, v in positions.items()]
        values = []
        for p in positions:
            if isinstance(p, (int, float)):
                values.append(float(p))
            elif isinstance(p, dict):
                values.append(float(p.get("value", p.get("notional", p.get("weight", 0.0))) or 0.0))
        if not values:
            values = [float(portfolio.get("nav", portfolio.get("value", 1.0)) or 1.0)]
        total = sum(abs(v) for v in values) or 1.0
        weights = [v / total for v in values]
        # φ-weighted concentration + volatility proxy
        conc = sum(w * w for w in weights)
        vol = float(portfolio.get("volatility", 0.15) or 0.15)
        var = min(0.5, max(1e-6, conc * vol / self.phi))
        ms = (time.perf_counter() - t0) * 1000.0
        self.audit.add_entry(f"risk_calc|var={var:.6f}|n={len(values)}")
        return {
            "value_at_risk": var,
            "confidence": min(0.99999, 0.9 + (1.0 - conc) * 0.09),
            "time_ms": ms,
            "positions": len(values),
            "concentration_hhi": conc,
            "complexity": "O(n)_linear_scan",
            "phi_optimized": True,
            "claim_lane": "FINANCE_RISK_OPERATIONAL",
            "note": "Operational φ-weighted risk proxy; not a regulatory VaR certification",
            "audit_integrity": self.audit.verify_integrity(),
        }

    def detect_fraud(self, transaction: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        tx = dict(transaction or {})
        amount = abs(float(tx.get("amount", 0.0) or 0.0))
        baseline = abs(float(tx.get("baseline_amount", tx.get("avg_amount", 100.0)) or 100.0))
        ratio = amount / (baseline + 1e-9)
        score = 1.0 - math.exp(-max(0.0, ratio - 1.0) / self.phi)
        flags = []
        if ratio > self.phi:
            flags.append("amount_spike")
        if str(tx.get("country", "")).upper() in {"KP", "IR", "SY"}:
            flags.append("geo_risk")
            score = max(score, 0.8)
        if tx.get("velocity_1h", 0) and float(tx.get("velocity_1h", 0)) > 20:
            flags.append("velocity")
            score = max(score, 0.7)
        digest = hashlib.sha256(repr(sorted(tx.items())).encode()).hexdigest()[:12]
        fraud = score >= 0.55 or bool(flags)
        ms = (time.perf_counter() - t0) * 1000.0
        self.audit.add_entry(f"fraud|{fraud}|score={score:.4f}|{digest}")
        return {
            "fraud_detected": fraud,
            "confidence": min(0.99999, 0.6 + score * 0.39),
            "score": score,
            "flags": flags,
            "time_ms": ms,
            "method": "phi_weighted_anomaly",
            "phi_optimized": True,
            "claim_lane": "FINANCE_FRAUD_OPERATIONAL",
            "audit_integrity": self.audit.verify_integrity(),
        }
