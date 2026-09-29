"""Deployment manifest: one manifest spanning every declared profile.

Schema (the ease-of-deployment contract):

    product: prime-db-mla1517
    profile: developer | edge | enterprise | sovereign | hyperscaler
    mode: cpu_reference | mla1517_gpu | host_gpu_overlay | cluster
    security: standard | regulated | air_gapped
    storage: embedded | local_persistent | object_tiered | distributed
    ai: {training, inference, vector, graph}
    proof_policy: required
    performance_claim_policy: measured_only

``compile_manifest`` turns a validated manifest into the service/policy/
volume/device/health/upgrade plan for that profile. Unknown values fail
closed — an undeclared profile is never silently coerced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping

from .core import sha256_json

__all__ = [
    "PROFILES",
    "MODES",
    "SECURITY_LEVELS",
    "STORAGE_MODES",
    "DeploymentManifest",
    "DeploymentPlan",
    "ManifestRejected",
    "load_manifest",
    "compile_manifest",
]

PROFILES = ("developer", "edge", "enterprise", "sovereign", "hyperscaler")
MODES = ("cpu_reference", "mla1517_gpu", "host_gpu_overlay", "cluster")
SECURITY_LEVELS = ("standard", "regulated", "air_gapped")
STORAGE_MODES = ("embedded", "local_persistent", "object_tiered", "distributed")


class ManifestRejected(ValueError):
    """A deployment manifest failed schema validation. Fails closed."""


@dataclass(frozen=True)
class DeploymentManifest:
    """The validated one-manifest deployment description."""

    product: str
    profile: str
    mode: str
    security: str
    storage: str
    ai: Dict[str, bool]
    proof_policy: str
    performance_claim_policy: str
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        body = {
            "product": self.product,
            "profile": self.profile,
            "mode": self.mode,
            "security": self.security,
            "storage": self.storage,
            "ai": dict(self.ai),
            "proof_policy": self.proof_policy,
            "performance_claim_policy": self.performance_claim_policy,
        }
        body.update(self.extra)
        return body


@dataclass(frozen=True)
class DeploymentPlan:
    """The compiled deployment: services, policies, evidence."""

    manifest_digest: str
    profile: str
    services: tuple
    policies: Dict[str, Any]
    volumes: tuple
    device_mappings: tuple
    health_checks: tuple
    dashboards: tuple
    upgrade_plan: tuple
    evidence_manifest: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "manifest_digest": self.manifest_digest,
            "profile": self.profile,
            "services": list(self.services),
            "policies": dict(self.policies),
            "volumes": list(self.volumes),
            "device_mappings": list(self.device_mappings),
            "health_checks": list(self.health_checks),
            "dashboards": list(self.dashboards),
            "upgrade_plan": list(self.upgrade_plan),
            "evidence_manifest": dict(self.evidence_manifest),
        }


def load_manifest(document: Mapping[str, Any]) -> DeploymentManifest:
    """Validate a manifest mapping. Unknown values fail closed."""
    if not isinstance(document, Mapping):
        raise ManifestRejected("manifest must be a mapping")
    required = ("product", "profile", "mode", "security", "storage")
    missing = [key for key in required if key not in document]
    if missing:
        raise ManifestRejected(f"manifest missing required keys: {missing}")
    product = str(document["product"])
    if product != "prime-db-mla1517":
        raise ManifestRejected(f"unsupported product: {product!r}")
    profile = str(document["profile"])
    if profile not in PROFILES:
        raise ManifestRejected(f"unsupported profile {profile!r}; declared: {list(PROFILES)}")
    mode = str(document["mode"])
    if mode not in MODES:
        raise ManifestRejected(f"unsupported mode {mode!r}; declared: {list(MODES)}")
    security = str(document["security"])
    if security not in SECURITY_LEVELS:
        raise ManifestRejected(
            f"unsupported security {security!r}; declared: {list(SECURITY_LEVELS)}"
        )
    storage = str(document["storage"])
    if storage not in STORAGE_MODES:
        raise ManifestRejected(f"unsupported storage {storage!r}; declared: {list(STORAGE_MODES)}")
    ai = document.get("ai", {})
    if not isinstance(ai, Mapping):
        raise ManifestRejected("ai must be a mapping of capability -> bool")
    ai_flags = {str(k): bool(v) for k, v in ai.items()}
    proof_policy = str(document.get("proof_policy", "required"))
    if proof_policy != "required":
        raise ManifestRejected("proof_policy must be 'required'")
    claim_policy = str(document.get("performance_claim_policy", "measured_only"))
    if claim_policy != "measured_only":
        raise ManifestRejected("performance_claim_policy must be 'measured_only'")
    extra = {
        str(k): v
        for k, v in document.items()
        if k
        not in {
            "product",
            "profile",
            "mode",
            "security",
            "storage",
            "ai",
            "proof_policy",
            "performance_claim_policy",
        }
    }
    return DeploymentManifest(
        product=product,
        profile=profile,
        mode=mode,
        security=security,
        storage=storage,
        ai=ai_flags,
        proof_policy=proof_policy,
        performance_claim_policy=claim_policy,
        extra=extra,
    )


def compile_manifest(manifest: DeploymentManifest) -> DeploymentPlan:
    """Generate the service/policy/volume/device/upgrade plan for a profile."""
    services = ["prime-db", "mla1517-runtime", "telemetry"]
    if manifest.mode in ("mla1517_gpu", "host_gpu_overlay"):
        services.append("opencl-adapter")
    if manifest.mode == "host_gpu_overlay":
        services.append("host-overlay")
    if manifest.mode == "cluster":
        services.extend(["salamander", "stratum-adapter"])
    if manifest.ai.get("vector") or manifest.ai.get("graph"):
        services.append("semantic-plane")
    if manifest.ai.get("training") or manifest.ai.get("inference"):
        services.append("ai-lifecycle")
    if manifest.security in ("regulated", "air_gapped"):
        services.append("audit-export")

    volumes: list = []
    if manifest.storage != "embedded":
        volumes.append("prime-db-data")
    if manifest.storage in ("object_tiered", "distributed"):
        volumes.append("cold-tier")

    device_mappings: list = []
    if manifest.mode == "mla1517_gpu":
        device_mappings.append("/dev/dri")
    if manifest.mode == "host_gpu_overlay":
        device_mappings.extend(["/dev/dri", "/dev/shm"])

    policies = {
        "proof_policy": manifest.proof_policy,
        "performance_claim_policy": manifest.performance_claim_policy,
        "residency": "air_gapped" if manifest.security == "air_gapped" else manifest.security,
        "retention": "append_only_audit" if manifest.security != "standard" else "standard",
    }

    health = tuple(f"health:{svc}" for svc in services)
    dashboards = ("topology", "proof-failures", "resource-use", "lineage")
    upgrade_plan = ("snapshot", "verify_state", "migrate", "seal", "resume")

    evidence = {
        "profile": manifest.profile,
        "object_semantics": "11D canonical MLAObject",
        "backend_identity": manifest.mode,
        "tests": "requirements_audit + conformance + behavioural",
        "policy": policies,
        "signed": manifest.security in ("regulated", "air_gapped"),
    }
    return DeploymentPlan(
        manifest_digest=sha256_json(manifest.as_dict()),
        profile=manifest.profile,
        services=tuple(services),
        policies=policies,
        volumes=tuple(volumes),
        device_mappings=tuple(device_mappings),
        health_checks=health,
        dashboards=dashboards,
        upgrade_plan=upgrade_plan,
        evidence_manifest=evidence,
    )
