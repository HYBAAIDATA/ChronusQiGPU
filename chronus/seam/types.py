"""Seam primitives — Result[T], errors, distributions. Errors are values."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Generic, TypeVar, Union

T = TypeVar("T")


class SeamError(str, Enum):
    kernel_unavailable = "kernel_unavailable"
    buffer_corruption = "buffer_corruption"
    capability_mismatch = "capability_mismatch"
    attestation_failure = "attestation_failure"
    device_absent = "device_absent"
    device_quarantined = "device_quarantined"
    backpressure = "backpressure"
    rate_limited = "rate_limited"
    verification_failed = "verification_failed"
    privacy_violation = "privacy_violation"
    deadline_exceeded = "deadline_exceeded"
    adiabatic_unavailable = "adiabatic_unavailable"
    reversible_unavailable = "reversible_unavailable"
    checkpoint_failure = "checkpoint_failure"
    unknown = "unknown"


class ThresholdPolicy(str, Enum):
    majority = "majority"
    unanimous = "unanimous"
    at_least_k = "at_least_k"
    weighted = "weighted"


class RoutingPolicy(str, Enum):
    conservative = "conservative"
    balanced = "balanced"
    aggressive = "aggressive"


@dataclass(frozen=True)
class Err:
    error: SeamError
    detail: str = ""

    def is_ok(self) -> bool:
        return False

    def unwrap(self) -> Any:
        raise RuntimeError(f"unwrap on Err({self.error.value}): {self.detail}")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

    def is_ok(self) -> bool:
        return True

    def unwrap(self) -> T:
        return self.value


Result = Union[Ok[T], Err]


@dataclass(frozen=True)
class Distribution:
    mean: float
    stddev: float = 0.0
    samples: int = 1
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mean": self.mean,
            "stddev": self.stddev,
            "samples": self.samples,
            "p50": self.p50 or self.mean,
            "p95": self.p95 or self.mean,
            "p99": self.p99 or self.mean,
        }


@dataclass(frozen=True)
class PhysicalMeasurement:
    time_ns: int
    energy_j: float = 0.0
    temperature_c: float = 0.0
    error_rate: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "time_ns": self.time_ns,
            "energy_j": self.energy_j,
            "temperature_c": self.temperature_c,
            "error_rate": self.error_rate,
        }


class DeviceClass(str, Enum):
    gpu_integrated = "gpu_integrated"
    gpu_discrete = "gpu_discrete"
    gpu_datacenter = "gpu_datacenter"
    gpu_cloud_instance = "gpu_cloud_instance"
    asic = "asic"
    fpga = "fpga"
    tpu = "tpu"
    cpu_reference = "cpu_reference"
    adiabatic_cmos = "adiabatic_cmos"
    superconducting = "superconducting"


class DeviceState(str, Enum):
    present = "present"
    absent = "absent"
    provisioning = "provisioning"
    quarantined = "quarantined"
    rehabilitated = "rehabilitated"
    deprovisioned = "deprovisioned"


class PrivacyMode(str, Enum):
    none = "none"
    anonymous = "anonymous"
    zero_knowledge = "zero_knowledge"


class KernelName(str, Enum):
    matmul_f4 = "matmul_f4"
    matvec_f4 = "matvec_f4"
    qfi_pure = "qfi_pure"
    grover_iterate = "grover_iterate"
    grover_hendrix_iterate = "grover_hendrix_iterate"
    lucas_wind = "lucas_wind"
    pisot_wind = "pisot_wind"
    cassini_step = "cassini_step"
    morton_step = "morton_step"
    korobov_point = "korobov_point"
    sha256d_scan = "sha256d_scan"
    sha256d_verify = "sha256d_verify"
    attest_result = "attest_result"
    attest_compose = "attest_compose"
    attest_zk_prove = "attest_zk_prove"
    reversible_matmul_f4 = "reversible_matmul_f4"
    reversible_qfi_pure = "reversible_qfi_pure"
    reversible_grover_iterate = "reversible_grover_iterate"
    reversible_sha256d_scan = "reversible_sha256d_scan"
    uncompute_checkpoint = "uncompute_checkpoint"
    uncompute_rollback = "uncompute_rollback"


class KernelClass(str, Enum):
    compute_heavy = "compute_heavy"
    hash_heavy = "hash_heavy"
    traversal = "traversal"
    coordination = "coordination"
    attestation = "attestation"
    reversible = "reversible"


class BufferBacking(str, Enum):
    device_private = "device_private"
    host_visible = "host_visible"
    unified = "unified"
    host_mapped = "host_mapped"
    encrypted_at_rest = "encrypted_at_rest"


KERNEL_CLASS: Dict[KernelName, KernelClass] = {
    KernelName.matmul_f4: KernelClass.compute_heavy,
    KernelName.matvec_f4: KernelClass.compute_heavy,
    KernelName.qfi_pure: KernelClass.compute_heavy,
    KernelName.grover_iterate: KernelClass.compute_heavy,
    KernelName.grover_hendrix_iterate: KernelClass.compute_heavy,
    KernelName.sha256d_scan: KernelClass.hash_heavy,
    KernelName.sha256d_verify: KernelClass.hash_heavy,
    KernelName.lucas_wind: KernelClass.traversal,
    KernelName.pisot_wind: KernelClass.traversal,
    KernelName.cassini_step: KernelClass.traversal,
    KernelName.morton_step: KernelClass.traversal,
    KernelName.korobov_point: KernelClass.traversal,
    KernelName.attest_result: KernelClass.attestation,
    KernelName.attest_compose: KernelClass.attestation,
    KernelName.attest_zk_prove: KernelClass.attestation,
    KernelName.reversible_matmul_f4: KernelClass.reversible,
    KernelName.reversible_qfi_pure: KernelClass.reversible,
    KernelName.reversible_grover_iterate: KernelClass.reversible,
    KernelName.reversible_sha256d_scan: KernelClass.reversible,
    KernelName.uncompute_checkpoint: KernelClass.reversible,
    KernelName.uncompute_rollback: KernelClass.reversible,
}


def new_id(prefix: str = "s") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest_of(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sign_digest(subject: str, issuer: str) -> str:
    """Host-side chain link. Not a TPM quote — never presented as one."""
    material = f"{issuer}:{subject}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


@dataclass
class AttestationLink:
    subject: str
    issuer: str
    signature: str
    timestamp: str
    chain_root: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "issuer": self.issuer,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "chain_root": self.chain_root,
        }


def verify_link(link: AttestationLink) -> bool:
    expected = sign_digest(link.subject, link.issuer)
    return bool(link.signature) and link.signature == expected and bool(link.subject)


def attest(subject: str, issuer: str = "pythia.seam", chain_root: str = "") -> AttestationLink:
    ts = now_iso()
    sig = sign_digest(subject, issuer)
    root = chain_root or digest_of(f"{issuer}|{subject}|{ts}".encode("utf-8"))
    return AttestationLink(subject, issuer, sig, ts, root)
