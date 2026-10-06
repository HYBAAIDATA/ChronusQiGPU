"""Canonical, JSON-safe Chronus Virtual iGPU ABI (virtual_igpu_v1).

Product identity is independent of any particular physical GPU. Delivery mode,
requested execution policy, and observed backend are separate fields. Trust
classes distinguish runtime-signed provenance from hardware-rooted attestation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


ABI_VERSION = "virtual_igpu_v1"
SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    """Stable JSON for hashing and receipts (sorted keys, compact separators)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest_json(value: Any) -> str:
    """SHA-256 hex digest of canonical JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class WorkloadKind(str, Enum):
    """Canonical workload kinds advertised per adapter only when implemented."""

    PROBE = "probe"
    FOLD = "fold"
    UNFOLD = "unfold"
    STORE = "store"
    RETRIEVE = "retrieve"
    TENSOR_OP = "tensor_op"
    CGEMV = "cgemv"
    PHI_TRANSFORM = "phi_transform"
    LUCAS_TRANSFORM = "lucas_transform"
    PISOT_TRANSFORM = "pisot_transform"
    SHA256D_SCAN = "sha256d_scan"
    CHECKPOINT = "checkpoint"
    CUSTOM = "custom"


class AdapterKind(str, Enum):
    """Physical/software backend that executed (or would execute) a job."""

    SOFTWARE = "software"
    OPENCL = "opencl"
    CUDA = "cuda"
    ROCM = "rocm"
    ONEAPI = "oneapi"
    METAL = "metal"
    CPU_REFERENCE = "cpu_reference"
    UNKNOWN = "unknown"


class RuntimeState(str, Enum):
    """Control-plane lifecycle (attach → … → detached)."""

    DETACHED = "detached"
    ATTACHING = "attaching"
    PROBING = "probing"
    NEGOTIATING = "negotiating"
    READY = "ready"
    DRAINING = "draining"
    FAILED = "failed"
    RECOVERING = "recovering"


class DeliveryMode(str, Enum):
    """Where the client talks to the runtime (not the GPU backend)."""

    EMBEDDED = "embedded"
    LOCAL_SIDECAR = "local_sidecar"
    REMOTE_SERVICE = "remote_service"


class ExecutionPolicy(str, Enum):
    """Requested execution preference; independent of delivery mode."""

    STANDALONE_SOFTWARE = "standalone_software"
    PREFERRED_ACCELERATOR = "preferred_accelerator"
    REQUIRED_ADAPTER = "required_adapter"
    REQUIRED_DEVICE = "required_device"


class TrustClass(str, Enum):
    """Provenance strength. Hardware-rooted is never inferred from a content hash."""

    RUNTIME_SIGNED = "runtime_signed"
    DEVICE_OBSERVED = "device_observed"
    HARDWARE_ROOTED = "hardware_rooted"
    UNAVAILABLE = "unavailable"


class DeploymentTarget(str, Enum):
    """Deployment layer (selects an adapter underneath; not a GPU capability)."""

    LOCAL = "local"
    AZURE = "azure"
    GOOGLE_CLOUD = "google_cloud"
    STANDALONE = "standalone"


@dataclass(frozen=True)
class CapabilityManifest:
    """Advertised capabilities for one adapter after probe/negotiate."""

    adapter_id: str
    kind: str
    operations: tuple[str, ...] = ()
    dtypes: tuple[str, ...] = ()
    max_shape: tuple[int, ...] = ()
    max_bytes: int = 0
    evidence_support: tuple[str, ...] = ()
    limits: dict[str, Any] = field(default_factory=dict)
    arithmetic: dict[str, Any] = field(default_factory=dict)
    available: bool = True
    reason: str = ""
    device_ids: tuple[str, ...] = ()
    software_impl: bool = False
    physical_run_status: str = "unverified"
    build_status: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["operations"] = list(self.operations)
        d["dtypes"] = list(self.dtypes)
        d["max_shape"] = list(self.max_shape)
        d["evidence_support"] = list(self.evidence_support)
        d["device_ids"] = list(self.device_ids)
        return d

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityManifest":
        return cls(
            adapter_id=str(value["adapter_id"]),
            kind=str(value.get("kind", AdapterKind.UNKNOWN.value)),
            operations=tuple(value.get("operations", ())),
            dtypes=tuple(value.get("dtypes", ())),
            max_shape=tuple(int(x) for x in value.get("max_shape", ())),
            max_bytes=int(value.get("max_bytes", 0)),
            evidence_support=tuple(value.get("evidence_support", ())),
            limits=dict(value.get("limits", {})),
            arithmetic=dict(value.get("arithmetic", {})),
            available=bool(value.get("available", True)),
            reason=str(value.get("reason", "")),
            device_ids=tuple(value.get("device_ids", ())),
            software_impl=bool(value.get("software_impl", False)),
            physical_run_status=str(value.get("physical_run_status", "unverified")),
            build_status=str(value.get("build_status", "unknown")),
        )


@dataclass(frozen=True)
class AdapterAttestation:
    """Adapter-local probe attestation (not hardware-rooted unless stated)."""

    adapter_id: str
    kind: str
    available: bool
    fingerprint: str
    chain_digest: str
    recorded_at: str = field(default_factory=_utc_now)
    detail: dict[str, Any] = field(default_factory=dict)
    trust_class: str = TrustClass.RUNTIME_SIGNED.value
    hardware_rooted: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AdapterAttestation":
        return cls(
            adapter_id=str(value["adapter_id"]),
            kind=str(value.get("kind", AdapterKind.UNKNOWN.value)),
            available=bool(value.get("available", False)),
            fingerprint=str(value.get("fingerprint", "")),
            chain_digest=str(value.get("chain_digest", "")),
            recorded_at=str(value.get("recorded_at", _utc_now())),
            detail=dict(value.get("detail", {})),
            trust_class=str(value.get("trust_class", TrustClass.RUNTIME_SIGNED.value)),
            hardware_rooted=bool(value.get("hardware_rooted", False)),
        )


@dataclass
class Workload:
    """Portable execution request (operation graph + inputs + policy)."""

    id: str
    kind: WorkloadKind | str
    tenant: str = "default"
    input: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    execution_policy: str = ExecutionPolicy.PREFERRED_ACCELERATOR.value
    required_adapter_id: str | None = None
    required_device_id: str | None = None
    idempotency_key: str | None = None
    delivery_mode: str = DeliveryMode.EMBEDDED.value
    deadline_ms: int | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    allow_software_fallback: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.tenant:
            raise ValueError("workload id and tenant are required")
        if isinstance(self.kind, str):
            try:
                self.kind = WorkloadKind(self.kind)
            except ValueError as exc:
                raise ValueError(f"unsupported workload kind: {self.kind!r}") from exc
        try:
            self.execution_policy = ExecutionPolicy(self.execution_policy).value
        except ValueError as exc:
            raise ValueError(
                f"unsupported execution policy: {self.execution_policy!r}"
            ) from exc
        try:
            self.delivery_mode = DeliveryMode(self.delivery_mode).value
        except ValueError as exc:
            raise ValueError(f"unsupported delivery mode: {self.delivery_mode!r}") from exc
        if self.deadline_ms is not None:
            if isinstance(self.deadline_ms, bool) or int(self.deadline_ms) <= 0:
                raise ValueError("deadline_ms must be a positive integer")
            self.deadline_ms = int(self.deadline_ms)
        if (
            self.execution_policy == ExecutionPolicy.REQUIRED_ADAPTER.value
            and not self.required_adapter_id
        ):
            raise ValueError("required_adapter policy requires required_adapter_id")
        if (
            self.execution_policy == ExecutionPolicy.REQUIRED_DEVICE.value
            and not self.required_device_id
        ):
            raise ValueError("required_device policy requires required_device_id")
        expected_hash = digest_json(self._identity_payload())
        if self.content_hash is not None and self.content_hash != expected_hash:
            raise ValueError("workload content_hash does not match canonical request")
        self.content_hash = expected_hash

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "abi_version": ABI_VERSION,
            "id": self.id,
            "kind": self.kind.value,
            "tenant": self.tenant,
            "input": self.input,
            "constraints": self.constraints,
            "execution_policy": self.execution_policy,
            "required_adapter_id": self.required_adapter_id,
            "required_device_id": self.required_device_id,
            "delivery_mode": self.delivery_mode,
            "deadline_ms": self.deadline_ms,
            "allow_software_fallback": bool(self.allow_software_fallback),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value if isinstance(self.kind, WorkloadKind) else str(self.kind),
            "tenant": self.tenant,
            "input": self.input,
            "constraints": self.constraints,
            "execution_policy": self.execution_policy,
            "required_adapter_id": self.required_adapter_id,
            "required_device_id": self.required_device_id,
            "idempotency_key": self.idempotency_key,
            "delivery_mode": self.delivery_mode,
            "deadline_ms": self.deadline_ms,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "allow_software_fallback": self.allow_software_fallback,
            "abi_version": ABI_VERSION,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Workload":
        version = str(value.get("abi_version", ABI_VERSION))
        if version != ABI_VERSION:
            raise ValueError(
                f"unsupported ABI version {version!r}; expected {ABI_VERSION!r}"
            )
        return cls(
            id=str(value["id"]),
            kind=value.get("kind", WorkloadKind.CUSTOM),
            tenant=str(value.get("tenant", "default")),
            input=dict(value.get("input", {})),
            constraints=dict(value.get("constraints", {})),
            execution_policy=str(
                value.get("execution_policy", ExecutionPolicy.PREFERRED_ACCELERATOR.value)
            ),
            required_adapter_id=value.get("required_adapter_id"),
            required_device_id=value.get("required_device_id"),
            idempotency_key=value.get("idempotency_key"),
            delivery_mode=str(value.get("delivery_mode", DeliveryMode.EMBEDDED.value)),
            deadline_ms=value.get("deadline_ms"),
            content_hash=value.get("content_hash"),
            metadata=dict(value.get("metadata", {})),
            allow_software_fallback=bool(value.get("allow_software_fallback", True)),
        )


@dataclass(frozen=True)
class PortablePackage:
    """Portable execution package bound to content hashes (no universal binary)."""

    package_id: str
    operation: str
    input_refs: tuple[str, ...] = ()
    shapes: tuple[tuple[int, ...], ...] = ()
    dtypes: tuple[str, ...] = ()
    byte_order: str = "little"
    arithmetic: str = "ieee754"
    determinism: str = "fixed_build"
    constraints: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    abi_version: str = ABI_VERSION

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["input_refs"] = list(self.input_refs)
        d["shapes"] = [list(s) for s in self.shapes]
        d["dtypes"] = list(self.dtypes)
        return d

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PortablePackage":
        shapes_raw = value.get("shapes", ())
        shapes = tuple(tuple(int(x) for x in s) for s in shapes_raw)
        return cls(
            package_id=str(value.get("package_id", "")),
            operation=str(value.get("operation", "")),
            input_refs=tuple(value.get("input_refs", ())),
            shapes=shapes,
            dtypes=tuple(value.get("dtypes", ())),
            byte_order=str(value.get("byte_order", "little")),
            arithmetic=str(value.get("arithmetic", "ieee754")),
            determinism=str(value.get("determinism", "fixed_build")),
            constraints=dict(value.get("constraints", {})),
            content_hash=str(value.get("content_hash", "")),
            abi_version=str(value.get("abi_version", ABI_VERSION)),
        )


@dataclass(frozen=True)
class ExecutionReceipt:
    """Per-operation provenance under an explicit trust model."""

    receipt_id: str
    workload_id: str
    attempt_id: str
    package_version: str
    protocol_version: str
    delivery_mode: str
    requested_policy: str
    actual_backend: str
    actual_device: str
    runtime_identity: str
    build_identity: str
    kernel_identity: str
    input_digest: str
    output_digest: str
    verified_work_count: int
    seed: str | None
    timing: dict[str, Any]
    verification: dict[str, Any]
    trust_class: str
    hardware_rooted: bool
    content_hash: str
    recorded_at: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutionReceipt":
        return cls(
            receipt_id=str(value["receipt_id"]),
            workload_id=str(value.get("workload_id", "")),
            attempt_id=str(value.get("attempt_id", "")),
            package_version=str(value.get("package_version", "")),
            protocol_version=str(value.get("protocol_version", ABI_VERSION)),
            delivery_mode=str(value.get("delivery_mode", DeliveryMode.EMBEDDED.value)),
            requested_policy=str(value.get("requested_policy", "")),
            actual_backend=str(value.get("actual_backend", "")),
            actual_device=str(value.get("actual_device", "")),
            runtime_identity=str(value.get("runtime_identity", "")),
            build_identity=str(value.get("build_identity", "")),
            kernel_identity=str(value.get("kernel_identity", "")),
            input_digest=str(value.get("input_digest", "")),
            output_digest=str(value.get("output_digest", "")),
            verified_work_count=int(value.get("verified_work_count", 0)),
            seed=value.get("seed"),
            timing=dict(value.get("timing", {})),
            verification=dict(value.get("verification", {})),
            trust_class=str(value.get("trust_class", TrustClass.RUNTIME_SIGNED.value)),
            hardware_rooted=bool(value.get("hardware_rooted", False)),
            content_hash=str(value.get("content_hash", "")),
            recorded_at=str(value.get("recorded_at", _utc_now())),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class WorkloadResult:
    """Native result: outputs + evidence handles (success flag alone is insufficient)."""

    workload_id: str
    status: str
    adapter_id: str
    kind: str
    output: dict[str, Any] = field(default_factory=dict)
    object_id: str | None = None
    attestation: dict[str, Any] = field(default_factory=dict)
    evidence_digest: str = ""
    wall_time_ns: int = 0
    device_time_ns: int | None = None
    # Elevation fields (2 Oct 2026 prompt)
    trust_class: str = TrustClass.RUNTIME_SIGNED.value
    hardware_rooted: bool = False
    requested_policy: str = ExecutionPolicy.PREFERRED_ACCELERATOR.value
    actual_adapter_id: str = ""
    actual_device_id: str = ""
    route_reason: str = ""
    delivery_mode: str = DeliveryMode.EMBEDDED.value
    receipt: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    abi_version: str = ABI_VERSION
    digest: str = ""  # alias used by older tests for evidence_digest
    error: str | None = None

    def __post_init__(self) -> None:
        # frozen dataclass: use object.__setattr__
        if not self.actual_adapter_id and self.adapter_id:
            object.__setattr__(self, "actual_adapter_id", self.adapter_id)
        if not self.digest and self.evidence_digest:
            object.__setattr__(self, "digest", self.evidence_digest)
        if not self.evidence_digest and self.digest:
            object.__setattr__(self, "evidence_digest", self.digest)

    @property
    def executed_on(self) -> str:
        """Legacy alias for actual_adapter_id / adapter_id."""
        return self.actual_adapter_id or self.adapter_id

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_dict(self) -> dict[str, Any]:
        """Legacy alias used by mining_bridge."""
        return self.as_dict()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkloadResult":
        return cls(
            workload_id=str(value.get("workload_id", "")),
            status=str(value.get("status", "unknown")),
            adapter_id=str(value.get("adapter_id", value.get("executed_on", ""))),
            kind=str(value.get("kind", "")),
            output=dict(value.get("output", {})),
            object_id=value.get("object_id"),
            attestation=dict(value.get("attestation", {})),
            evidence_digest=str(value.get("evidence_digest") or value.get("digest") or ""),
            wall_time_ns=int(value.get("wall_time_ns", 0)),
            device_time_ns=value.get("device_time_ns"),
            trust_class=str(value.get("trust_class", TrustClass.RUNTIME_SIGNED.value)),
            hardware_rooted=bool(value.get("hardware_rooted", False)),
            requested_policy=str(
                value.get("requested_policy", ExecutionPolicy.PREFERRED_ACCELERATOR.value)
            ),
            actual_adapter_id=str(
                value.get("actual_adapter_id")
                or value.get("adapter_id")
                or value.get("executed_on")
                or ""
            ),
            actual_device_id=str(value.get("actual_device_id", "")),
            route_reason=str(value.get("route_reason", "")),
            delivery_mode=str(value.get("delivery_mode", DeliveryMode.EMBEDDED.value)),
            receipt=dict(value.get("receipt", {})),
            metrics=dict(value.get("metrics", {})),
            abi_version=str(value.get("abi_version", ABI_VERSION)),
            digest=str(value.get("digest") or value.get("evidence_digest") or ""),
            error=value.get("error"),
        )


@dataclass(frozen=True)
class AdmissionRecord:
    """Atomic admission reservation outcome."""

    admitted: bool
    adapter_id: str
    reason: str
    queue_depth: int = 0
    reserved_bytes: int = 0
    deadline_ms: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_declared_output_shape(
    operation: str,
    input_shapes: list[tuple[int, ...]] | tuple[tuple[int, ...], ...],
    output_shape: tuple[int, ...] | list[int] | None,
) -> tuple[int, ...]:
    """Reject shape mismatches before allocation/dispatch (PR #95 gap class)."""
    if output_shape is None:
        raise ValueError(f"{operation}: declared output_shape is required")
    out = tuple(int(x) for x in output_shape)
    if not out:
        raise ValueError(f"{operation}: output_shape must be non-empty")
    if any(d < 0 for d in out):
        raise ValueError(f"{operation}: output_shape dims must be non-negative")
    # Elementwise / scale: output must match first input when provided
    if input_shapes:
        primary = tuple(int(x) for x in input_shapes[0])
        if operation in {"elementwise", "scale", "add", "mul", "axpy"} and out != primary:
            raise ValueError(
                f"{operation}: output_shape {out} does not match input shape {primary}"
            )
    return out


__all__ = [
    "ABI_VERSION",
    "SCHEMA_VERSION",
    "canonical_json",
    "digest_json",
    "WorkloadKind",
    "AdapterKind",
    "RuntimeState",
    "DeliveryMode",
    "ExecutionPolicy",
    "TrustClass",
    "DeploymentTarget",
    "CapabilityManifest",
    "AdapterAttestation",
    "Workload",
    "PortablePackage",
    "ExecutionReceipt",
    "WorkloadResult",
    "AdmissionRecord",
    "validate_declared_output_shape",
    "replace",
]
