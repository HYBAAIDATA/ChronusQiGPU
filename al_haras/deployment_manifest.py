"""12.10 Deployment <-> Platform: signed, versioned, reproducible manifests.

One manifest describes the whole platform; every service inside it must be
bound to the canonical object model, policy engine and lineage store — a
disconnected subsystem is rejected, not shipped. The signature is
HMAC-SHA256 over the canonical payload; verification fails closed when the
key is absent.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Any

SCHEMA = "hyba.platform/v1"
SIGNATURE_ALGORITHM = "HMAC-SHA256"
CANONICAL_OBJECT_MODEL = "prime-db"
CANONICAL_POLICY_ENGINE = "hyba-policy"
CANONICAL_LINEAGE_STORE = "cassini-ledger"


class ManifestRejected(ValueError):
    def __init__(self, reasons: tuple[str, ...]):
        self.reasons = tuple(reasons)
        super().__init__("; ".join(self.reasons))


@dataclass(frozen=True)
class ServiceBinding:
    name: str
    object_model: str
    policy_engine: str
    lineage_store: str


@dataclass(frozen=True)
class PlatformManifest:
    schema: str
    name: str
    profile: str
    version: str
    modules: tuple[str, ...]
    services: tuple[ServiceBinding, ...]
    compose_files: tuple[str, ...]
    compile_hash: str
    signature_algorithm: str = SIGNATURE_ALGORITHM
    signature: str = ""
    key_id: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "profile": self.profile,
            "version": self.version,
            "modules": list(self.modules),
            "services": [
                {
                    "name": s.name,
                    "object_model": s.object_model,
                    "policy_engine": s.policy_engine,
                    "lineage_store": s.lineage_store,
                }
                for s in self.services
            ],
            "compose_files": list(self.compose_files),
            "compile_hash": self.compile_hash,
            "signature_algorithm": self.signature_algorithm,
            "key_id": self.key_id,
        }

    def canonical(self) -> bytes:
        return json.dumps(self.payload(), sort_keys=True, separators=(",", ":")).encode()


def validate_manifest(manifest: PlatformManifest) -> PlatformManifest:
    """C1/C3/C6–C9: one manifest, versioned, every service canonically bound."""
    reasons: list[str] = []
    if manifest.schema != SCHEMA:
        reasons.append(f"schema must be {SCHEMA}")
    if not manifest.version:
        reasons.append("manifest is not versioned (C3)")
    if not manifest.modules:
        reasons.append("manifest describes no modules (C1)")
    if not manifest.services:
        reasons.append("manifest describes no services (C1)")
    for service in manifest.services:
        if (
            service.object_model != CANONICAL_OBJECT_MODEL
            or service.policy_engine != CANONICAL_POLICY_ENGINE
            or service.lineage_store != CANONICAL_LINEAGE_STORE
        ):
            reasons.append(
                f"service {service.name} is disconnected from the canonical "
                f"object/policy/lineage plane (C6–C9)"
            )
    if manifest.signature_algorithm != SIGNATURE_ALGORITHM:
        reasons.append(f"signature_algorithm must be {SIGNATURE_ALGORITHM}")
    if reasons:
        raise ManifestRejected(tuple(reasons))
    return manifest


def compile_deployment(manifest: PlatformManifest) -> dict[str, Any]:
    """C4/C5: deployment compiles FROM the manifest deterministically."""
    plan = {
        "manifest": manifest.name,
        "profile": manifest.profile,
        "version": manifest.version,
        "compose_files": sorted(manifest.compose_files),
        "modules": sorted(manifest.modules),
        "services": sorted(
            f"{s.name}:{s.object_model}:{s.policy_engine}:{s.lineage_store}"
            for s in manifest.services
        ),
    }
    plan["plan_hash"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return plan


def sign_manifest(manifest: PlatformManifest, key: bytes) -> PlatformManifest:
    if len(key) < 32:
        raise ManifestRejected(("deployment signing key must be at least 32 bytes",))
    unsigned = replace(manifest, signature="")
    validate_manifest(unsigned)
    sig = hmac.new(key, unsigned.canonical(), hashlib.sha256).hexdigest()
    return replace(manifest, signature=sig)


def verify_manifest(manifest: PlatformManifest, key: bytes) -> bool:
    """Fail closed: unsigned, invalid, or tampered manifests never verify."""
    if not manifest.signature or len(key) < 32:
        return False
    try:
        validate_manifest(manifest)
    except ManifestRejected:
        return False
    expected = hmac.new(
        key, replace(manifest, signature="").canonical(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, manifest.signature)


def load_manifest(path: str | Path) -> PlatformManifest:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = PlatformManifest(
        schema=str(document.get("schema", "")),
        name=str(document.get("name", "")),
        profile=str(document.get("profile", "")),
        version=str(document.get("version", "")),
        modules=tuple(str(m) for m in (document.get("modules") or [])),
        services=tuple(
            ServiceBinding(
                name=str(s.get("name", "")),
                object_model=str(s.get("object_model", "")),
                policy_engine=str(s.get("policy_engine", "")),
                lineage_store=str(s.get("lineage_store", "")),
            )
            for s in (document.get("services") or [])
        ),
        compose_files=tuple(str(c) for c in (document.get("compose_files") or [])),
        compile_hash=str(document.get("compile_hash", "")),
        signature_algorithm=str(document.get("signature_algorithm", "")),
        signature=str(document.get("signature", "")),
        key_id=str(document.get("key_id", "")),
    )
    return validate_manifest(manifest)


def write_manifest(manifest: PlatformManifest, path: str | Path) -> None:
    payload = manifest.payload()
    payload["signature"] = manifest.signature
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


__all__ = [name for name in globals() if not name.startswith("_")]
