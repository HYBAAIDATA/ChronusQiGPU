from __future__ import annotations
import hashlib, hmac, json
from dataclasses import asdict
from enum import Enum
from .gates import evaluate
from .model import AssemblyBlueprint, AssemblyIntent, AssemblyLock, CompilationResult
from .profiles import PROFILES
from .registry import MODULE_REGISTRY, dependency_closure


def _plain(value):
    if isinstance(value, Enum): return value.value
    if isinstance(value, dict): return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(v) for v in value]
    return value

def _canonical(value) -> bytes:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":")).encode()

def _digest(value) -> str: return hashlib.sha256(_canonical(value)).hexdigest()

def compile_assembly(intent: AssemblyIntent, *, signing_key: bytes) -> CompilationResult:
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        raise ValueError("assembly signing key must be at least 32 bytes")
    gate = evaluate(intent)
    ordered = dependency_closure(intent.modules)
    spec = PROFILES[intent.deployment_profile]
    policies = {
        "silent_fallback": False,
        "customer_managed_keys": intent.customer_managed_keys,
        "local_identity_provider": intent.local_identity_provider,
        "air_gapped": intent.air_gapped,
        "private_networking": intent.private_networking,
        "human_approval_for_high_risk_actions": intent.human_approval_for_high_risk_actions,
        "evidence_status": gate.status.value,
    }
    threats = ["credential_theft", "policy_tampering", "tenant_crossing", "rollback", "evidence_forgery", "resource_exhaustion"]
    if intent.air_gapped: threats += ["offline_update_tampering", "removable_media_compromise"]
    if intent.deployment_profile == "hyperscaler": threats += ["cross_region_failure", "noisy_neighbor"]
    crosswalk = tuple(sorted(set((intent.industry, intent.risk_level, intent.sovereignty))))
    blueprint = AssemblyBlueprint(spec.name, tuple(intent.modules), ordered, intent.dominant_tiers, policies, tuple(threats), crosswalk, {"economics": list(intent.economics), "resilience": intent.resilience, "exactness": intent.exactness})
    manifest_hash = _digest(asdict(intent)); policy_hash = _digest(policies)
    evidence_hash = _digest([asdict(e) for e in intent.module_evidence])
    unsigned = {"schema_version":"hyba.assembly-lock.v1","manifest_hash":manifest_hash,"modules":ordered,"versions":sorted((e.module,e.version) for e in intent.module_evidence),"policy_hash":policy_hash,"evidence_hash":evidence_hash,"signature_algorithm":"HMAC-SHA256"}
    signature = hmac.new(signing_key, _canonical(unsigned), hashlib.sha256).hexdigest()
    lock = AssemblyLock(unsigned["schema_version"], manifest_hash, ordered, tuple(unsigned["versions"]), policy_hash, evidence_hash, unsigned["signature_algorithm"], signature)
    explanation = (f"profile={spec.name}", f"gate={gate.status.value}", f"modules={len(ordered)}", "profile names do not elevate assurance without new evidence")
    return CompilationResult(blueprint, lock, gate, explanation)

def verify_lock(result: CompilationResult, signing_key: bytes) -> bool:
    lock = result.lock
    unsigned = {"schema_version":lock.schema_version,"manifest_hash":lock.manifest_hash,"modules":lock.modules,"versions":list(lock.versions),"policy_hash":lock.policy_hash,"evidence_hash":lock.evidence_hash,"signature_algorithm":lock.signature_algorithm}
    expected = hmac.new(signing_key, _canonical(unsigned), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, lock.signature)
