"""Product Authority Registry & Resource-Vector Admission Controller.

Implements Section 5 of the Native Quantum Fleet Elevation Mandate:
- Codifies exclusive product authorities (`Chronus`, `Kellogg`, `TURING`, `TOE`, `EUCLID`,
  `AL HARAS`, `THESEUS`, `OVID`, `Salamander`, `Hermitten`).
- Admits workloads by full `ResourceVector` (CPU time, peak memory, custody bytes/IOPS,
  network bytes, deadline, exactness plane, verification requirement, tenant budget).
- Refuses or defers fail-closed when capacity telemetry is unknown or stale.
- Enforces cryptographic `AuthorityGrant` verification (HMAC-SHA256 bound to tenant,
  workload, resource vector digest, policy epoch, nonce, and expiry). Proves that
  token format/length and tenant header shape alone never confer authority.
- Enforces replay protection, fencing/version checks, pre-mutation durable audit logging,
  and verified postconditions before issuing any success receipt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping

from .cohorts import ReferenceFleetAllocation
from .workload_contracts import ResourceVector


AUTHORITY_ADMISSION_SCHEMA = "chronus.fleet.authority-admission/v1"


PRODUCT_AUTHORITIES: dict[str, dict[str, str]] = {
    "Chronus": {
        "domain": "execution_and_compute_substrate",
        "contract": "ONE iGPU logical-device execution, HostGPUPlan scheduling, and native/overlay kernels",
    },
    "Kellogg": {
        "domain": "tensor_representations_and_bridges",
        "contract": "Exact F4 tensors, FP64 MPS/TT/MPO decompositions, contractions, and budgeted compression",
    },
    "TURING": {
        "domain": "quantum_circuits_and_certificates",
        "contract": "Quantum circuits, state semantics, Born measurement, VQCComputationCertificate, and RunWitness",
    },
    "TOE": {
        "domain": "mathematical_truth_criteria",
        "contract": "Propagator laws, invariant checks, and claim register boundaries",
    },
    "EUCLID": {
        "domain": "orchestration_and_routing",
        "contract": "Multi-organ routing, curriculum dispatch, and evidence aggregation without usurping owner proofs",
    },
    "AL HARAS": {
        "domain": "policy_entitlements_and_authorization",
        "contract": "Cryptographic authority grants, tenant entitlements, replay defense, and fail-closed security gates",
    },
    "THESEUS": {
        "domain": "rebuildable_query_index_and_lineage",
        "contract": "Rebuildable query, index, graph and semantic projections over OVID authority",
    },
    "OVID": {
        "domain": "authoritative_state_custody_and_integrity",
        "contract": "Authoritative durable folded state, checkpoints, integrity and representation custody",
    },
    "Salamander": {
        "domain": "self_healing_and_bounded_repair",
        "contract": "Diagnostic telemetry and bounded remediation without mutating safety policy or proof authority",
    },
    "Hermitten": {
        "domain": "formal_verification_and_proof_auditing",
        "contract": "Independent postcondition verification, exactness auditing, and semantic replay checks",
    },
}


class AdmissionDecisionStatus(str, Enum):
    ADMITTED = "admitted"
    REFUSED = "refused"
    DEFERRED = "deferred"


@dataclass(frozen=True, kw_only=True)
class TenantBudgetQuota:
    """Resource ceiling and slot quota for a tenant."""

    tenant_id: str
    max_cpu_time_ms: int = 60_000
    max_peak_memory_bytes: int = 1024 * 1024 * 1024
    max_custody_bytes: int = 64 * 1024 * 1024
    max_custody_io_bps: int = 100 * 1024 * 1024
    max_network_bytes: int = 16 * 1024 * 1024
    explicit_mining_pool_contract: str | None = None


@dataclass(frozen=True, kw_only=True)
class AuthorityGrant:
    """Cryptographically signed AL HARAS authority grant.

    Token format/length or tenant header shape never suffices; the HMAC-SHA256
    signature over all canonical grant fields must verify under the AL HARAS key.
    """

    grant_id: str
    issuer: str
    tenant_id: str
    workload_id: str
    owner_authority: str
    resource_vector_digest: str
    policy_epoch: int
    fencing_token: int
    nonce: str
    issued_at_ms: int
    expires_at_ms: int
    allow_live_mining: bool = False
    signature_hmac_sha256: str = ""

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "issuer": self.issuer,
            "tenant_id": self.tenant_id,
            "workload_id": self.workload_id,
            "owner_authority": self.owner_authority,
            "resource_vector_digest": self.resource_vector_digest,
            "policy_epoch": self.policy_epoch,
            "fencing_token": self.fencing_token,
            "nonce": self.nonce,
            "issued_at_ms": self.issued_at_ms,
            "expires_at_ms": self.expires_at_ms,
            "allow_live_mining": self.allow_live_mining,
        }

    @classmethod
    def issue(
        cls,
        *,
        signing_key: bytes,
        grant_id: str,
        tenant_id: str,
        workload_id: str,
        owner_authority: str,
        resource_vector: ResourceVector,
        policy_epoch: int = 1,
        fencing_token: int = 1,
        nonce: str,
        issued_at_ms: int | None = None,
        ttl_ms: int = 300_000,
        allow_live_mining: bool = False,
    ) -> AuthorityGrant:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("AL HARAS signing_key must be at least 32 bytes")
        if owner_authority not in PRODUCT_AUTHORITIES:
            raise ValueError(f"Unknown owner_authority: {owner_authority!r}")
        now_ms = int(time.time() * 1000) if issued_at_ms is None else int(issued_at_ms)
        unsigned = cls(
            grant_id=grant_id,
            issuer="AL HARAS",
            tenant_id=tenant_id,
            workload_id=workload_id,
            owner_authority=owner_authority,
            resource_vector_digest=resource_vector.digest,
            policy_epoch=int(policy_epoch),
            fencing_token=int(fencing_token),
            nonce=str(nonce),
            issued_at_ms=now_ms,
            expires_at_ms=now_ms + int(ttl_ms),
            allow_live_mining=bool(allow_live_mining),
            signature_hmac_sha256="",
        )
        raw = json.dumps(unsigned.unsigned_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig = hmac.new(signing_key, raw, hashlib.sha256).hexdigest()
        return cls(**{**unsigned.unsigned_payload(), "signature_hmac_sha256": sig})

    def verify_signature(self, signing_key: bytes) -> bool:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            return False
        if not self.signature_hmac_sha256 or len(self.signature_hmac_sha256) != 64:
            return False
        raw = json.dumps(self.unsigned_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = hmac.new(signing_key, raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature_hmac_sha256)


@dataclass(frozen=True, kw_only=True)
class CapacitySnapshot:
    """Point-in-time fleet capacity snapshot used by AdmissionController."""

    captured_at_ms: int
    known: bool
    available_slots_by_class: Mapping[str, int]
    active_fencing_token: int = 1
    current_state_version: int = 1


@dataclass(frozen=True, kw_only=True)
class PreMutationAuditRecord:
    """Durable pre-mutation audit record written and fsynced prior to any state mutation."""

    sequence: int
    grant_id: str
    tenant_id: str
    workload_id: str
    owner_authority: str
    resource_vector_digest: str
    fencing_token: int
    expected_version: int
    recorded_at_ms: int
    previous_digest: str
    record_digest: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, kw_only=True)
class AdmissionReceipt:
    """Final outcome of an admission + privileged execution request."""

    status: AdmissionDecisionStatus
    reason: str
    grant_id: str | None
    tenant_id: str
    workload_id: str
    owner_authority: str
    pre_mutation_audit_digest: str | None
    postcondition_verified: bool
    committed_version: int | None
    result_digest: str | None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class AdmissionController:
    """Fail-closed admission and privileged execution controller."""

    def __init__(
        self,
        *,
        audit_dir: Path,
        signing_key: bytes,
        fleet_allocation: ReferenceFleetAllocation | None = None,
        max_capacity_staleness_ms: int = 30_000,
        policy_epoch: int = 1,
    ) -> None:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("signing_key must be at least 32 bytes")
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_path = self.audit_dir / "pre_mutation_audit.jsonl"
        self._signing_key = signing_key
        self.fleet_allocation = fleet_allocation or ReferenceFleetAllocation()
        self.max_capacity_staleness_ms = int(max_capacity_staleness_ms)
        self.policy_epoch = int(policy_epoch)
        self._tenant_quotas: dict[str, TenantBudgetQuota] = {}
        self._used_nonces: set[str] = set()
        self._audit_seq = 0
        self._audit_head = "0" * 64
        self._active_fencing_token = 1
        self._state_version = 1
        self._lock = threading.RLock()

    def register_tenant(self, quota: TenantBudgetQuota) -> None:
        with self._lock:
            self._tenant_quotas[quota.tenant_id] = quota

    def rotate_fencing_token(self, new_fencing_token: int) -> int:
        with self._lock:
            if int(new_fencing_token) <= self._active_fencing_token:
                raise ValueError("new_fencing_token must strictly increase")
            self._active_fencing_token = int(new_fencing_token)
            return self._active_fencing_token

    @property
    def state_version(self) -> int:
        return self._state_version

    @property
    def active_fencing_token(self) -> int:
        return self._active_fencing_token

    def default_capacity_snapshot(self, *, now_ms: int | None = None) -> CapacitySnapshot:
        ts = int(time.time() * 1000) if now_ms is None else int(now_ms)
        return CapacitySnapshot(
            captured_at_ms=ts,
            known=True,
            available_slots_by_class={
                "interactive": self.fleet_allocation.interactive_slots,
                "batch": self.fleet_allocation.batch_slots,
                "exact_quantum": self.fleet_allocation.exact_quantum_scientific_slots,
                "tenant_burst": self.fleet_allocation.tenant_burst_slots,
                "mining": self.fleet_allocation.mining_default_slots,
            },
            active_fencing_token=self._active_fencing_token,
            current_state_version=self._state_version,
        )

    def _append_pre_mutation_audit(
        self,
        *,
        grant: AuthorityGrant,
        expected_version: int,
        now_ms: int,
    ) -> PreMutationAuditRecord:
        body = {
            "sequence": self._audit_seq,
            "grant_id": grant.grant_id,
            "tenant_id": grant.tenant_id,
            "workload_id": grant.workload_id,
            "owner_authority": grant.owner_authority,
            "resource_vector_digest": grant.resource_vector_digest,
            "fencing_token": grant.fencing_token,
            "expected_version": expected_version,
            "recorded_at_ms": now_ms,
            "previous_digest": self._audit_head,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        rec = PreMutationAuditRecord(**body, record_digest=digest)
        line = json.dumps(rec.as_dict(), sort_keys=True, separators=(",", ":")) + "\n"
        with self.audit_log_path.open("a", encoding="utf-8") as fp:
            fp.write(line)
            fp.flush()
            os.fsync(fp.fileno())
        self._audit_seq += 1
        self._audit_head = digest
        return rec

    def admit_and_execute(
        self,
        *,
        grant: AuthorityGrant | Mapping[str, Any] | str | None,
        resource_vector: ResourceVector,
        workload_id: str,
        owner_authority: str,
        capacity: CapacitySnapshot,
        expected_version: int | None = None,
        mutation_fn: Callable[[], dict[str, Any]],
        postcondition_fn: Callable[[dict[str, Any]], bool],
        now_ms: int | None = None,
    ) -> AdmissionReceipt:
        """Validate authority, capacity, quota, pre-mutation audit, fencing, and postconditions."""
        current_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)

        with self._lock:
            # 0. Reject bare token strings or unverified headers (shape/length != authority)
            if not isinstance(grant, AuthorityGrant):
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="unauthenticated_header_or_token_shape_is_not_authority",
                    grant_id=None,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            # 1. Verify exclusive product owner authority
            if owner_authority not in PRODUCT_AUTHORITIES or grant.owner_authority != owner_authority:
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="invalid_or_mismatched_product_owner_authority",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            # 2. Verify cryptographic HMAC-SHA256 signature on grant
            if not grant.verify_signature(self._signing_key):
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="invalid_or_forged_authority_grant_signature",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            # 3. Verify grant binding (tenant, workload_id, resource_vector_digest, policy_epoch, expiry)
            if (
                grant.tenant_id != resource_vector.tenant_id
                or grant.workload_id != workload_id
                or grant.resource_vector_digest != resource_vector.digest
            ):
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="grant_payload_mismatch_with_request_or_resource_vector",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )
            if grant.policy_epoch != self.policy_epoch or current_ms > grant.expires_at_ms:
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="expired_grant_or_stale_policy_epoch",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            # 4. Replay defense
            if grant.nonce in self._used_nonces:
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="replayed_authority_grant_nonce",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            # 5. Capacity freshness & availability check (refuse/defer when unknown or stale)
            if not capacity.known or (current_ms - capacity.captured_at_ms) > self.max_capacity_staleness_ms:
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.DEFERRED,
                    reason="capacity_telemetry_unknown_or_stale",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            # 6. Tenant quota & mining zero-default entitlement check
            quota = self._tenant_quotas.get(resource_vector.tenant_id)
            if quota is None:
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="unregistered_tenant_quota",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )
            if (
                resource_vector.cpu_time_ms > quota.max_cpu_time_ms
                or resource_vector.peak_memory_bytes > quota.max_peak_memory_bytes
                or resource_vector.custody_bytes > quota.max_custody_bytes
                or resource_vector.custody_io_bps > quota.max_custody_io_bps
                or resource_vector.network_bytes > quota.max_network_bytes
            ):
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="resource_vector_exceeds_tenant_budget_quota",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            if resource_vector.workload_class == "mining":
                if not grant.allow_live_mining or not quota.explicit_mining_pool_contract:
                    return AdmissionReceipt(
                        status=AdmissionDecisionStatus.REFUSED,
                        reason="mining_has_zero_default_entitlement_and_requires_explicit_pool_contract",
                        grant_id=grant.grant_id,
                        tenant_id=resource_vector.tenant_id,
                        workload_id=workload_id,
                        owner_authority=owner_authority,
                        pre_mutation_audit_digest=None,
                        postcondition_verified=False,
                        committed_version=None,
                        result_digest=None,
                    )

            avail_slots = int(capacity.available_slots_by_class.get(resource_vector.workload_class, 0))
            if avail_slots < 1:
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.DEFERRED,
                    reason=f"no_available_slots_for_class_{resource_vector.workload_class}",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            # 7. Version and fencing token check BEFORE mutation
            req_ver = self._state_version if expected_version is None else int(expected_version)
            if grant.fencing_token != self._active_fencing_token or req_ver != self._state_version:
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="stale_fencing_token_or_optimistic_concurrency_version_mismatch",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=None,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            # Consume nonce and write durable pre-mutation audit record BEFORE executing mutation
            self._used_nonces.add(grant.nonce)
            audit_rec = self._append_pre_mutation_audit(
                grant=grant,
                expected_version=req_ver,
                now_ms=current_ms,
            )

            # 8. Execute mutation & verify postcondition before emitting success receipt
            result = mutation_fn()
            post_ok = bool(postcondition_fn(result))
            if not post_ok:
                return AdmissionReceipt(
                    status=AdmissionDecisionStatus.REFUSED,
                    reason="postcondition_verification_failed_after_execution",
                    grant_id=grant.grant_id,
                    tenant_id=resource_vector.tenant_id,
                    workload_id=workload_id,
                    owner_authority=owner_authority,
                    pre_mutation_audit_digest=audit_rec.record_digest,
                    postcondition_verified=False,
                    committed_version=None,
                    result_digest=None,
                )

            self._state_version += 1
            res_digest = hashlib.sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest()
            return AdmissionReceipt(
                status=AdmissionDecisionStatus.ADMITTED,
                reason="admitted_and_postcondition_verified",
                grant_id=grant.grant_id,
                tenant_id=resource_vector.tenant_id,
                workload_id=workload_id,
                owner_authority=owner_authority,
                pre_mutation_audit_digest=audit_rec.record_digest,
                postcondition_verified=True,
                committed_version=self._state_version,
                result_digest=res_digest,
            )


__all__ = [
    "AUTHORITY_ADMISSION_SCHEMA",
    "PRODUCT_AUTHORITIES",
    "AdmissionController",
    "AdmissionDecisionStatus",
    "AdmissionReceipt",
    "AuthorityGrant",
    "CapacitySnapshot",
    "PreMutationAuditRecord",
    "TenantBudgetQuota",
]
