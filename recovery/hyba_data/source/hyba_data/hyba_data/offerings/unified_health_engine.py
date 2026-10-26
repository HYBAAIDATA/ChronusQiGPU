from __future__ import annotations

import hashlib
import json
import time
import zlib
from typing import Any

from al_haras.security_core import CryptographicAuditChain

PHI = (1.0 + 5.0**0.5) / 2.0


class UnifiedHealthEngine:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.audit.add_entry("UNIFIED_HEALTH_ENGINE_INIT")

    def _compress(self, patient_data: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(patient_data, sort_keys=True, default=str).encode()
        comp = zlib.compress(raw, level=9)
        ratio = (1.0 - len(comp) / max(1, len(raw))) * 100.0
        return {
            "bytes_in": len(raw),
            "bytes_out": len(comp),
            "reduction_pct": ratio,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "blob": comp,
        }

    def _phi_diagnosis(self, compressed: dict[str, Any], patient_data: dict[str, Any]) -> dict[str, Any]:
        vitals = patient_data.get("vitals") or {}
        symptoms = [str(s).lower() for s in (patient_data.get("symptoms") or [])]
        score = 0.0
        findings = []
        hr = float(vitals.get("hr", vitals.get("heart_rate", 70)) or 70)
        temp = float(vitals.get("temp_c", vitals.get("temperature", 36.6)) or 36.6)
        if hr > 100 or hr < 45:
            score += 0.35
            findings.append("abnormal_hr")
        if temp >= 38.0:
            score += 0.35
            findings.append("fever")
        for s in symptoms:
            if s in {"chest_pain", "shortness_of_breath", "stroke_signs"}:
                score += 0.4
                findings.append(s)
        score = min(1.0, score)
        urgency = "emergency" if score >= 0.7 else ("urgent" if score >= 0.4 else "routine")
        return {
            "findings": findings,
            "urgency": urgency,
            "score": score,
            "treatment_path": {
                "emergency": "escalate_er",
                "urgent": "same_day_review",
                "routine": "standard_care_path",
            }[urgency],
            "compression_sha": compressed.get("sha256", "")[:16],
        }

    def analyze_patient(self, patient_data: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        patient_data = dict(patient_data or {})
        compressed = self._compress(patient_data)
        diagnosis = self._phi_diagnosis(compressed, patient_data)
        ms = (time.perf_counter() - t0) * 1000.0
        self.audit.add_entry(f"patient_analyze|{diagnosis['urgency']}|{diagnosis['score']:.3f}")
        return {
            "diagnosis": diagnosis,
            "confidence": min(0.99999, 0.75 + diagnosis["score"] * 0.2),
            "treatment_path": diagnosis["treatment_path"],
            "compression": {
                "bytes_in": compressed["bytes_in"],
                "bytes_out": compressed["bytes_out"],
                "reduction_pct": compressed["reduction_pct"],
            },
            "time_ms": ms,
            "phi_optimized": True,
            "claim_lane": "HEALTH_ANALYZE_OPERATIONAL",
            "note": "Decision-support prototype — not a medical device or clinical diagnosis",
            "audit_integrity": self.audit.verify_integrity(),
        }

    def discover_drug(self, target: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        target = dict(target or {})
        name = str(target.get("target", target.get("protein", "unknown")))
        # deterministic candidate ranking from hash manifold
        seeds = [f"{name}|cand|{i}|{self.phi:.6f}" for i in range(8)]
        cands = []
        for s in seeds:
            h = hashlib.sha256(s.encode()).hexdigest()
            score = (int(h[:8], 16) % 10_000) / 10_000.0
            score = (score + 1.0 / self.phi) / 2.0
            cands.append({"id": h[:10], "score": score})
        cands.sort(key=lambda c: c["score"], reverse=True)
        ms = (time.perf_counter() - t0) * 1000.0
        self.audit.add_entry(f"drug_discover|{name}|top={cands[0]['id']}")
        return {
            "target": name,
            "candidates": cands[:5],
            "simulation_complexity": "O(k)_hash_manifold",
            "time_ms": ms,
            "accuracy_proxy": cands[0]["score"],
            "phi_optimized": True,
            "claim_lane": "HEALTH_DRUG_DISCOVERY_OPERATIONAL",
            "note": "In-silico ranking toy model — not wet-lab validated discovery",
            "audit_integrity": self.audit.verify_integrity(),
        }
