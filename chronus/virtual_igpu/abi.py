"""Canonical, JSON-safe Chronus Virtual iGPU ABI."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Mapping

ABI_VERSION = "virtual_igpu_v1"


class WorkloadKind(str, Enum):
    FOLD = "fold"
    UNFOLD = "unfold"
    STORE = "store"
    RETRIEVE = "retrieve"
    TENSOR_CONTRACT = "tensor_contract"
    TENSOR_SVD = "tensor_svd"
    PHI_TRANSFORM = "phi_transform"
    LUCAS_TRANSFORM = "lucas_transform"
    SHA256D_SCAN = "sha256d_scan"
    SHA256D_VERIFY = "sha256d_verify"


class Capability(str, Enum):
    FOLD = "fold"
    UNFOLD = "unfold"
    STORE = "store"
    RETRIEVE = "retrieve"
    TENSOR_CONTRACT = "tensor_contract"
    TENSOR_SVD = "tensor_svd"
    PHI_TRANSFORM = "phi_transform"
    LUCAS_TRANSFORM = "lucas_transform"
    SHA256D_SCAN = "sha256d_scan"
    SHA256D_VERIFY = "sha256d_verify"


class AdapterKind(str, Enum):
    CPU_EMULATOR = "cpu_emulator"
    CUDA = "cuda"
    ROCM = "rocm"
    ONEAPI = "oneapi"
    METAL = "metal"
    OPENCL_INTEL_UHD = "opencl_intel_uhd"
    OPENCL_INTEL_IRIS = "opencl_intel_iris"
    OPENCL_AMD = "opencl_amd"
    OPENCL_NVIDIA = "opencl_nvidia"
    AZURE = "azure"
    GOOGLE_CLOUD = "google_cloud"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _iso(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("deadline must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class Workload:
    id: str
    kind: WorkloadKind
    input: Mapping[str, Any]
    tenant: str
    priority: int = 0
    deadline: str | None = None
    attestation: tuple[str, ...] = ()
    abi_version: str = ABI_VERSION

    def __post_init__(self) -> None:
        if self.abi_version != ABI_VERSION:
            raise ValueError(f"unsupported ABI {self.abi_version!r}")
        if not self.id or not self.tenant:
            raise ValueError("workload id and tenant are required")
        if not isinstance(self.kind, WorkloadKind):
            object.__setattr__(self, "kind", WorkloadKind(self.kind))
        if not isinstance(self.input, Mapping):
            raise ValueError("workload input must be a JSON object")
        canonical_json(self.input)
        object.__setattr__(self, "deadline", _iso(self.deadline))

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Workload":
        return cls(
            id=str(value.get("id", "")),
            kind=WorkloadKind(value.get("kind")),
            input=dict(value.get("input") or {}),
            tenant=str(value.get("tenant", "")),
            priority=int(value.get("priority", 0)),
            deadline=value.get("deadline"),
            attestation=tuple(value.get("attestation") or ()),
            abi_version=str(value.get("abi_version", ABI_VERSION)),
        )


@dataclass(frozen=True)
class AdapterAttestation:
    adapter_id: str
    kind: AdapterKind
    capabilities: tuple[str, ...]
    fingerprint: str
    firmware_hash: str | None
    chain: tuple[str, ...]
    timestamp: str
    abi_version: str = ABI_VERSION

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        return value


@dataclass(frozen=True)
class WorkloadResult:
    workload_id: str
    status: str
    output: Mapping[str, Any]
    digest: str
    attestation: tuple[str, ...]
    executed_on: str
    wall_time_ns: int
    device_time_ns: int | None = None
    energy_j: float | None = None
    temperature_c: float | None = None
    evidence_digest: str | None = None
    object_id: str | None = None
    error: str | None = None
    abi_version: str = ABI_VERSION

    def __post_init__(self) -> None:
        if self.status not in {"ok", "err"}:
            raise ValueError("result status must be ok or err")
        if self.abi_version != ABI_VERSION:
            raise ValueError("result ABI mismatch")
        if self.wall_time_ns < 0:
            raise ValueError("wall time cannot be negative")
        if self.status == "ok":
            expected = digest_json(self.output)
            if self.digest != expected or not self.attestation:
                raise ValueError("successful result digest/attestation invariant failed")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkloadResult":
        return cls(
            workload_id=str(value["workload_id"]),
            status=str(value["status"]),
            output=dict(value.get("output") or {}),
            digest=str(value.get("digest", "")),
            attestation=tuple(value.get("attestation") or ()),
            executed_on=str(value.get("executed_on", "")),
            wall_time_ns=int(value.get("wall_time_ns", 0)),
            device_time_ns=value.get("device_time_ns"),
            energy_j=value.get("energy_j"),
            temperature_c=value.get("temperature_c"),
            evidence_digest=value.get("evidence_digest"),
            object_id=value.get("object_id"),
            error=value.get("error"),
            abi_version=str(value.get("abi_version", ABI_VERSION)),
        )