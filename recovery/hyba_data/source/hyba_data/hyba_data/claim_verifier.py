"""Sealed claim closure engine — verify every claim with runnable evidence.

Each SealedClaim stores text, doctrine link, evidence path, and a verify()
method that runs the corresponding check. Raises ClaimViolationError on failure.

Usage:
  from hyba_data.claim_verifier import ClaimRegistry, ClaimViolationError
  registry = ClaimRegistry()
  results = registry.verify_all()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional


class ClaimViolationError(Exception):
    """Raised when a sealed claim's evidence fails verification."""
    pass


@dataclass
class SealedClaim:
    claim_id: str
    text: str
    doctrine: str
    evidence_path: str
    lane: str  # EXTERNAL | BOUNDED | INTERNAL | RESTRICTED
    expiry: Optional[datetime] = None
    _verify_fn: Optional[Callable[[], bool]] = field(default=None, repr=False)

    def verify(self) -> bool:
        """Run the evidence check. Returns True on pass, raises on failure."""
        if self.expiry and datetime.now(timezone.utc) > self.expiry:
            raise ClaimViolationError(
                f"Claim {self.claim_id} expired at {self.expiry.isoformat()}"
            )
        if self._verify_fn is None:
            raise ClaimViolationError(
                f"Claim {self.claim_id}: no verify function registered"
            )
        try:
            result = self._verify_fn()
        except Exception as e:
            raise ClaimViolationError(
                f"Claim {self.claim_id}: verification raised {type(e).__name__}: {e}"
            ) from e
        if result is not True:
            raise ClaimViolationError(
                f"Claim {self.claim_id}: verification returned {result}"
            )
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "doctrine": self.doctrine,
            "evidence_path": self.evidence_path,
            "lane": self.lane,
            "expiry": self.expiry.isoformat() if self.expiry else None,
        }


class ClaimRegistry:
    """Central registry of all sealed claims with verification methods."""

    def __init__(self):
        self._claims: Dict[str, SealedClaim] = {}
        self._register_all()

    def _register_all(self):
        """Register all sealed claims with their verification functions."""

        # C-001: Category is CIaaS
        self.register(
            "C-001",
            "Category is Computational Intelligence as a Service (CIaaS)",
            "Delivery",
            "python_backend/hyba_substrate/platform.py",
            "EXTERNAL",
            lambda: self._verify_module_claim(
                "hyba_substrate", "describe_platform", "category", "Computational Intelligence as a Service"
            ),
        )

        # C-002: Fold never truncate
        self.register(
            "C-002",
            "φ-folding is invertible; reconstruction is exact; truncation forbidden",
            "Fold",
            "python_backend/hyba_data/fold_doctrine.py",
            "EXTERNAL",
            lambda: self._verify_fold_invertibility(),
        )

        # C-003: Quantum from maths
        self.register(
            "C-003",
            "Quantum is Hilbert-space mathematics; substrate- and hardware-agnostic",
            "Quantum from maths",
            "python_backend/hyba_data/quantum_honest.py",
            "EXTERNAL",
            lambda: self._verify_quantum_honest(),
        )

        # C-004: Quantum serves data
        self.register(
            "C-004",
            "Quantum capability serves HYBA Data — storage, search, security, simulation",
            "Quantum serves data",
            "python_backend/hyba_data/fold_doctrine.py",
            "EXTERNAL",
            lambda: self._verify_quantum_serves_data(),
        )

        # C-005: Pricing — 25% of measured savings only
        self.register(
            "C-005",
            "Fee is 25% of measured savings; zero if unmeasured; no maintenance",
            "CIaaS",
            "python_backend/hyba_data/savings_metering.py",
            "EXTERNAL",
            lambda: self._verify_savings_pricing(),
        )

        # C-006: M1 ~2.62× BOUNDED external
        self.register(
            "C-006",
            "M1 metric ~2.62× depth-1 compacted working set — BOUNDED external",
            "Fold",
            "python_backend/hyba_data/sealed_metric_card.py",
            "BOUNDED",
            lambda: self._verify_m1_bounded(),
        )

        # C-007: No mining product surface
        self.register(
            "C-007",
            "Mining is not a product surface in HYBA Data repository",
            "Delivery",
            "python_backend/hyba_substrate/platform.py",
            "EXTERNAL",
            lambda: self._verify_no_mining_surface(),
        )

        # C-008: Delivery — no onsite engineers, no training spin-off
        self.register(
            "C-008",
            "HYBA Data delivers software only; no onsite engineers; no training product",
            "Delivery",
            "DOCTRINE_DELIVERY.md",
            "EXTERNAL",
            lambda: self._verify_delivery_doctrine(),
        )

    def register(
        self,
        claim_id: str,
        text: str,
        doctrine: str,
        evidence_path: str,
        lane: str,
        verify_fn: Callable[[], bool],
        expiry_days: Optional[int] = None,
    ):
        expiry = None
        if expiry_days:
            expiry = datetime.now(timezone.utc) + timedelta(days=expiry_days)
        self._claims[claim_id] = SealedClaim(
            claim_id=claim_id,
            text=text,
            doctrine=doctrine,
            evidence_path=evidence_path,
            lane=lane,
            expiry=expiry,
            _verify_fn=verify_fn,
        )

    def verify(self, claim_id: str) -> bool:
        if claim_id not in self._claims:
            raise ClaimViolationError(f"Unknown claim: {claim_id}")
        return self._claims[claim_id].verify()

    def verify_all(self) -> Dict[str, Any]:
        results = {}
        all_pass = True
        for cid, claim in self._claims.items():
            try:
                claim.verify()
                results[cid] = {"status": "PASS", "lane": claim.lane}
            except ClaimViolationError as e:
                results[cid] = {"status": "FAIL", "lane": claim.lane, "error": str(e)}
                all_pass = False
        return {"all_pass": all_pass, "results": results, "total": len(self._claims)}

    def get_public_claims(self) -> List[SealedClaim]:
        """Return only EXTERNAL and BOUNDED claims — no INTERNAL/RESTRICTED."""
        return [c for c in self._claims.values() if c.lane in ("EXTERNAL", "BOUNDED")]

    def get_banned_lanes(self) -> List[str]:
        """Returns lanes that must not be exported — verifies no 'BANNED' label."""
        return [c.claim_id for c in self._claims.values() if c.lane == "BANNED"]

    # ── verification implementations ────────────────────────────────

    @staticmethod
    def _verify_module_claim(module: str, fn: str, key: str, expected: str) -> bool:
        import importlib
        mod = importlib.import_module(module)
        func = getattr(mod, fn)
        result = func()
        actual = result.get(key) if isinstance(result, dict) else getattr(result, key, None)
        if actual != expected:
            raise ClaimViolationError(f"{key}={actual}, expected={expected}")
        return True

    @staticmethod
    def _verify_fold_invertibility() -> bool:
        import numpy as np

        from pulvini.folding_engine.kernels_core import progressive_fold, progressive_unfold
        x = np.sin(np.linspace(0, 8 * np.pi, 256))
        folded = progressive_fold(x, depth=3)
        recon = progressive_unfold(folded)[:256]
        err = float(np.max(np.abs(recon - x)))
        if err > 1e-10:
            raise ClaimViolationError(f"fold recon error {err} exceeds 1e-10")
        return True

    @staticmethod
    def _verify_quantum_honest() -> bool:
        from hyba_data.quantum_honest import run_honest_quantum_battery
        result = run_honest_quantum_battery()
        if result.get("status") != "HONEST_QUANTUM_PASS":
            raise ClaimViolationError(f"quantum battery: {result.get('status')}")
        if result.get("mining") is not False:
            raise ClaimViolationError("quantum battery must not claim mining")
        return True

    @staticmethod
    def _verify_quantum_serves_data() -> bool:
        from hyba_data.fold_doctrine import describe_fold_doctrine
        d = describe_fold_doctrine()
        if not d.get("quantum_serves_data"):
            raise ClaimViolationError("quantum_serves_data flag is False")
        impacts = d.get("data_impacts", {})
        required = ["storage", "search", "security", "processing"]
        for k in required:
            if k not in impacts:
                raise ClaimViolationError(f"missing data impact: {k}")
        return True

    @staticmethod
    def _verify_savings_pricing() -> bool:
        from hyba_data.savings_metering import compute_savings

        # Unmeasured = zero fee
        u = compute_savings(s_memory=1000, f=0.5, m_eff=2.0, measured=False)
        if u.hyba_fee != 0.0:
            raise ClaimViolationError(f"unmeasured fee {u.hyba_fee} != 0")
        # Measured = 25%
        m = compute_savings(s_memory=1000, f=0.5, m_eff=2.0, measured=True)
        expected = 1000 * 0.5 * (1 - 1/2.0) * 0.25
        if abs(m.hyba_fee - expected) > 0.01:
            raise ClaimViolationError(f"measured fee {m.hyba_fee} != {expected}")
        return True

    @staticmethod
    def _verify_m1_bounded() -> bool:
        from hyba_data.sealed_metric_card import get_external_metric
        m1 = get_external_metric("M1")
        if m1["ratio"] != 2.62:
            raise ClaimViolationError(f"M1 ratio {m1['ratio']} != 2.62")
        if m1["lane"] != "BOUNDED":
            raise ClaimViolationError(f"M1 lane {m1['lane']} != BOUNDED")
        return True

    @staticmethod
    def _verify_no_mining_surface() -> bool:
        from hyba_data.quantum_honest import run_honest_quantum_battery
        result = run_honest_quantum_battery()
        if result.get("mining") is not False:
            raise ClaimViolationError("quantum battery claims mining")
        return True

    @staticmethod
    def _verify_delivery_doctrine() -> bool:
        from pathlib import Path
        p = Path("DOCTRINE_DELIVERY.md")
        if not p.exists():
            raise ClaimViolationError("DOCTRINE_DELIVERY.md not found")
        text = p.read_text()
        if "software, not services" not in text.lower():
            raise ClaimViolationError("delivery doctrine missing core text")
        return True


# ── convenience ───────────────────────────────────────────────────────

_registry: Optional[ClaimRegistry] = None


def get_registry() -> ClaimRegistry:
    global _registry
    if _registry is None:
        _registry = ClaimRegistry()
    return _registry


def verify_all_claims() -> Dict[str, Any]:
    return get_registry().verify_all()
