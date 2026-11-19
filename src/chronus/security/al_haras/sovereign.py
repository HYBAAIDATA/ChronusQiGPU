"""
AL HARAS governance register and product SDK (HYBA Security).

The governance register maps the 14 UK NCSC Cloud Security Principles to the
mechanisms present in this repository. It reports facts the code can establish
(for example, which key provider is configured) and records that no principle
has been independently assessed. HYBA holds no certification, accreditation or
authorisation for AL HARAS, and nothing here claims one (see
docs/claim-audit.md and STATUS.md).
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any, Dict, List, Optional

from chronus.security.al_haras.engine import (
    ALHarasSecurityFabric,
    CellularSheafCohomology,
    CyclotomicAnyonBraidEngine,
    DSW4DInstantonMonopoleHealer,
    HeckeModularChecksum,
    RamanujanExpanderSpectralGapGuard,
)
from chronus.security.al_haras.exact import decimal_string
from chronus.security.ovid import OVIDStorage

__all__ = [
    "ExactQ5",
    "GaloisField257Phi",
    "SovereignGovernanceEngine",
    "ALHarasSovereignProductSDK",
    "sovereign_ovid_chain",
    # re-exported engines used by older import paths
    "CellularSheafCohomology",
    "DSW4DInstantonMonopoleHealer",
    "RamanujanExpanderSpectralGapGuard",
    "CyclotomicAnyonBraidEngine",
    "HeckeModularChecksum",
    "ALHarasSecurityFabric",
]

sovereign_ovid_chain = OVIDStorage()


# ------------------------------------------------------------------------------
# 1. EXACT ALGEBRAIC FIELD DEFINITIONS
# ------------------------------------------------------------------------------


class ExactQ5:
    """Exact element a + b*sqrt(5) of Q(sqrt(5)) with rational a and b."""

    def __init__(self, a_num: int, a_den: int = 1, b_num: int = 0, b_den: int = 1):
        self.a = Fraction(a_num, a_den)
        self.b = Fraction(b_num, b_den)

    @property
    def a_num(self) -> int:
        return self.a.numerator

    @property
    def a_den(self) -> int:
        return self.a.denominator

    @property
    def b_num(self) -> int:
        return self.b.numerator

    @property
    def b_den(self) -> int:
        return self.b.denominator

    def __add__(self, other: "ExactQ5") -> "ExactQ5":
        out = ExactQ5(0)
        out.a, out.b = self.a + other.a, self.b + other.b
        return out

    def __mul__(self, other: "ExactQ5") -> "ExactQ5":
        out = ExactQ5(0)
        out.a = self.a * other.a + 5 * self.b * other.b
        out.b = self.a * other.b + self.b * other.a
        return out

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ExactQ5) and self.a == other.a and self.b == other.b

    def norm(self) -> Fraction:
        """Field norm a^2 - 5 b^2 (exact)."""
        return self.a * self.a - 5 * self.b * self.b

    def decimal(self, places: int = 12) -> str:
        """Decimal value computed with integer square roots only."""
        from math import isqrt

        scale = 10 ** places
        b_abs = abs(self.b)
        root = Fraction(isqrt(5 * b_abs.numerator**2 * scale * scale // b_abs.denominator**2), scale)
        value = self.a + (root if self.b >= 0 else -root)
        return decimal_string(value, places)

    def __repr__(self) -> str:
        return f"({self.a}) + ({self.b})√5"


class GaloisField257Phi:
    """F_257[phi] = F_257[x]/(x^2 - x - 1), exact modular arithmetic."""

    PRIME = 257

    def __init__(self, c0: int, c1: int):
        self.c0 = c0 % self.PRIME
        self.c1 = c1 % self.PRIME

    def __add__(self, other: "GaloisField257Phi") -> "GaloisField257Phi":
        return GaloisField257Phi(self.c0 + other.c0, self.c1 + other.c1)

    def __mul__(self, other: "GaloisField257Phi") -> "GaloisField257Phi":
        ac = self.c0 * other.c0
        bd = self.c1 * other.c1
        ad_bc = self.c0 * other.c1 + self.c1 * other.c0
        return GaloisField257Phi(ac + bd, ad_bc + bd)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GaloisField257Phi) and (self.c0, self.c1) == (other.c0, other.c1)


# ------------------------------------------------------------------------------
# 2. GOVERNANCE REGISTER (EVIDENCE POINTERS, NOT CERTIFICATIONS)
# ------------------------------------------------------------------------------

NCSC_PRINCIPLES: List[Dict[str, Any]] = [
    {"id": 1, "name": "Data in transit protection", "evidence": ["TLS termination is a deployment responsibility; not configured in this repository"]},
    {"id": 2, "name": "Asset protection and resilience", "evidence": ["src/chronus/security/al_haras/reed_solomon.py (trace repair)", "src/chronus/security/ovid.py (content addressing)"]},
    {"id": 3, "name": "Separation between customers", "evidence": ["src/chronus/service/auth_middleware.py (tenant-scoped tokens)"]},
    {"id": 4, "name": "Governance framework", "evidence": ["docs/claim-audit.md", "STATUS.md"]},
    {"id": 5, "name": "Operational security", "evidence": [".github/workflows/ci.yml (tests, static analysis, dependency audit)"]},
    {"id": 6, "name": "Personnel security", "evidence": []},
    {"id": 7, "name": "Secure development", "evidence": [".github/workflows/ci.yml", "AGENTS.md"]},
    {"id": 8, "name": "Supply chain security", "evidence": ["pinned GitHub Actions in .github/workflows", "pip-audit job in ci.yml"]},
    {"id": 9, "name": "Secure user management", "evidence": ["src/chronus/service/auth_middleware.py"]},
    {"id": 10, "name": "Identity and authentication", "evidence": ["src/chronus/service/auth_middleware.py"]},
    {"id": 11, "name": "External interface protection", "evidence": ["pydantic request validation in src/chronus/service/routers"]},
    {"id": 12, "name": "Secure service administration", "evidence": []},
    {"id": 13, "name": "Audit information and alerting for customers", "evidence": ["src/chronus/security/al_haras/receipts.py (decision receipts signed with Ed25519 and ML-DSA-87)"]},
    {"id": 14, "name": "Secure use of the service", "evidence": []},
]


def describe_key_custody() -> Dict[str, Any]:
    """Report the configured key provider without overstating custody."""
    from chronus.security.kms import LocalMemoryKeyProvider, get_kms_provider

    provider = get_kms_provider()
    local = isinstance(provider, LocalMemoryKeyProvider)
    return {
        "configured_provider": type(provider).__name__,
        "custody_mode": "local process memory (development only)"
        if local
        else "provider abstraction configured; remote or HSM custody not demonstrated",
        "customer_held_hsm_demonstrated": False,
        "reference": "docs/claim-audit.md (Cloud KMS, Vault, PKCS#11, HSM)",
    }


class SovereignGovernanceEngine:
    """Governance register for AL HARAS (evidence pointers, no certification)."""

    NCSC_PRINCIPLES = [p["name"] for p in NCSC_PRINCIPLES]

    @classmethod
    def audit_sovereign_compliance(cls, tenant_id: str) -> Dict[str, Any]:
        principles = {
            f"P{p['id']}_{p['name'].replace(' ', '_')}": {
                "assessment": "NOT_ASSESSED",
                "repository_evidence": p["evidence"],
            }
            for p in NCSC_PRINCIPLES
        }
        return {
            "tenant_id": tenant_id,
            "framework": "UK NCSC Cloud Security Principles (14)",
            "ncsc_14_principles": principles,
            "principles_independently_assessed": 0,
            "certifications_held": [],
            "statement": "No certification, accreditation or authorisation (for example FedRAMP, DoD IL levels, "
            "FIPS 140 or Common Criteria) is held or claimed for AL HARAS.",
            "key_custody": describe_key_custody(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ------------------------------------------------------------------------------
# 3. AL HARAS PRODUCT SDK
# ------------------------------------------------------------------------------


class ALHarasSovereignProductSDK:
    """Inspect a workload before execution and record a signed decision receipt."""

    def __init__(self, sovereign_state_id: str = "sovereign_state_default", hsm_kms_key_id: Optional[str] = None):
        self.sovereign_state_id = sovereign_state_id
        self.kms_key_id = hsm_kms_key_id

    def inspect_and_admit_workload(
        self,
        payload: bytes,
        state_vectors: Optional[List[List[Any]]] = None,
        passphrase: Optional[str] = None,
        edges: Optional[List[Any]] = None,
        tolerance: Any = 0,
        node_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        payload = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        edge_pairs = [tuple(e) for e in edges] if edges else None
        ingress = ALHarasSecurityFabric.evaluate_ingress(
            payload, state_vectors, passphrase, edges=edge_pairs, tolerance=tolerance, node_names=node_names
        )
        admitted = ingress["admitted"]
        envelope = json.dumps(
            {
                "tenant": self.sovereign_state_id,
                "admitted": admitted,
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
                "receipt_body_sha256": ingress["receipt"]["signature"]["body_sha256"],
            },
            sort_keys=True,
        ).encode("utf-8")
        ovid_id = sovereign_ovid_chain.store(envelope)
        elapsed_ns = time.perf_counter_ns() - t0
        slug = "".join(c for c in self.sovereign_state_id.lower() if c.isalnum())[:12] or "tenant"
        handle = f"o1_{slug}_{ovid_id[:8]}"
        ovid_receipt = sovereign_ovid_chain.create_receipt(
            ovid_id,
            ed25519_signature=ingress["receipt"]["signature"]["signature_hex"],
            latency_ms=elapsed_ns // 1_000_000,
            receipt_handle=handle,
            metadata={"tenant": self.sovereign_state_id, "admitted": admitted},
        )
        return {
            "product": "AL HARAS (HYBA Security)",
            "tenant": self.sovereign_state_id,
            "admitted_to_execution": admitted,
            "admitted_to_execution_fabric": admitted,
            "decision": ingress,
            "sheaf_cohomology": ingress["sheaf_cohomology"],
            "signature_standard": "Ed25519 (RFC 8032) and ML-DSA-87 (FIPS 204); both must verify",
            "receipt": ingress["receipt"],
            "ovid_receipt_handle": handle,
            "ovid_receipt_id": ovid_id,
            "ovid_receipt": ovid_receipt.to_dict(),
            "inspection_latency_ms_measured": decimal_string(Fraction(elapsed_ns, 1_000_000), 4),
        }

    def get_full_governance_report(self, tenant_id: str = "sovereign_default") -> Dict[str, Any]:
        """Governance register plus a fresh, signed inspection of a fixed audit payload."""
        inspection = self.inspect_and_admit_workload(b"GOVERNANCE_AUDIT")
        return {
            "tenant_id": tenant_id,
            "governance": SovereignGovernanceEngine.audit_sovereign_compliance(tenant_id),
            "inspection": inspection,
        }
