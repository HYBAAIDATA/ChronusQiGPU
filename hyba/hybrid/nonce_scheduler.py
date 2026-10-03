"""NonceScheduler — the device-agnostic solver contract for the hybrid substrate.

A NonceScheduler is any device that can grind a ``NonceWindow`` against a
consensus target and report an honest capability record. It is implemented
by the GPU solver (:mod:`hyba.hybrid.gpu_solver`) and the ASIC protocol
solver (:mod:`hyba.hybrid.asic_solver`); any other solver may implement it.

Rules every implementation must obey:

- ``capability()`` MUST probe. It MUST NOT fabricate a capability. If the
  device is absent or unusable it returns ``supported=False`` with a
  ``reason_if_unsupported`` — never a synthetic record.
- ``dispatch(window)`` MUST raise :class:`DeviceUnsupportedError` when the
  device is not supported, and MUST attest the dispatch BEFORE the first
  nonce is tried.
- ``poll(handle)`` returns a verified :class:`Share` or ``None``. Nothing
  returns a "candidate" that has not been verified.
- ``cancel(handle)`` is idempotent and attests the cancellation.
- Nothing in this module assumes SHA-256d except the host re-verification
  helper, which is the consensus authority per the repository contract.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

NONCE_SPACE = 1 << 32
_HANDLE_IDS = itertools.count(1)


class DeviceUnsupportedError(RuntimeError):
    """Raised when a dispatch is attempted on an unsupported device."""


class ASICNotPresent(DeviceUnsupportedError):
    """Raised when ASIC work is requested and no ASIC is attached."""


class AttestationViolation(RuntimeError):
    """A device returned data that fails host-side consensus re-verification."""


# ---------------------------------------------------------------------------
# Wire types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NonceWindow:
    """A contiguous span of the uint32 nonce field assigned to one device."""

    job_id: str
    session_epoch: int
    job_epoch: int
    base_nonce: int
    span: int  # number of nonces in the window
    target: bytes  # 32-byte big-endian consensus target
    face: int = 0  # winding-face index the window was assigned under

    def __post_init__(self) -> None:
        if len(self.target) != 32:
            raise ValueError(f"target must be 32 bytes, got {len(self.target)}")
        if not (0 <= self.base_nonce < NONCE_SPACE):
            raise ValueError(f"base_nonce out of uint32 range: {self.base_nonce}")
        if self.span <= 0:
            raise ValueError(f"span must be > 0, got {self.span}")
        if self.base_nonce + self.span > NONCE_SPACE:
            raise ValueError(
                f"window wraps the uint32 nonce field: "
                f"base={self.base_nonce} + span={self.span} > 2^32"
            )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "session_epoch": self.session_epoch,
            "job_epoch": self.job_epoch,
            "base_nonce": self.base_nonce,
            "span": self.span,
            "target_hex": self.target.hex(),
            "face": self.face,
        }


@dataclass(frozen=True)
class DeviceCapability:
    """Observed capability record — measured, never asserted."""

    device_id: str
    device_class: str  # "gpu" | "asic" | "cpu"
    measured_hashes_per_sec: float
    supported: bool
    reason_if_unsupported: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_class": self.device_class,
            "measured_hashes_per_sec": self.measured_hashes_per_sec,
            "supported": self.supported,
            "reason_if_unsupported": self.reason_if_unsupported,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class DispatchHandle:
    """An in-flight window. One handle per dispatch; dispatch is idempotent."""

    handle_id: int
    device_id: str
    window: NonceWindow
    dispatched_ns: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "handle_id": self.handle_id,
            "device_id": self.device_id,
            "window": self.window.as_dict(),
            "dispatched_ns": self.dispatched_ns,
        }


@dataclass(frozen=True)
class Share:
    """A device-reported candidate. Only valid after host re-verification.

    ``nonces_tried`` is the count of hashes physically executed by the
    winning launch. ``probe_index`` is the share's position in this
    device's emitted traversal order — the serial-equivalent depth at
    which the share was reached, independent of launch granularity.
    """

    device_id: str
    job_id: str
    nonce: int
    digest: bytes  # 32-byte double-SHA256 output as produced by the solver
    nonces_tried: int
    face: int = 0
    probe_index: int = 0

    def header_with_nonce(self, header_prefix: bytes) -> bytes:
        """Reconstruct the full 80-byte header for consensus re-check."""
        return bytes(header_prefix) + int(self.nonce).to_bytes(4, "little")


# ---------------------------------------------------------------------------
# Attestation — every dispatched window, auditable
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionAttestation:
    """One attested event in the dispatch lifecycle."""

    kind: str  # "dispatch" | "share" | "exhausted" | "cancelled" | "failed" | "gap"
    device_id: str
    device_class: str
    handle_id: Optional[int]
    window: Optional[NonceWindow]
    timestamp_ns: int
    device_time_ns: Optional[int] = None
    nonces_tried: int = 0
    found: bool = False
    reason: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "device_id": self.device_id,
            "device_class": self.device_class,
            "handle_id": self.handle_id,
            "window": self.window.as_dict() if self.window is not None else None,
            "timestamp_ns": self.timestamp_ns,
            "device_time_ns": self.device_time_ns,
            "nonces_tried": self.nonces_tried,
            "found": self.found,
            "reason": self.reason,
            "detail": dict(self.detail),
        }


class AttestationRegistry:
    """Process-wide append-only ledger for dispatch attestations and gaps."""

    _instance: Optional["AttestationRegistry"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._records: List[ExecutionAttestation] = []
        self._rlock = threading.RLock()

    @classmethod
    def get(cls) -> "AttestationRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = AttestationRegistry()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def record(self, attestation: ExecutionAttestation) -> ExecutionAttestation:
        with self._rlock:
            self._records.append(attestation)
        return attestation

    def record_gap(
        self, reason: str, *, device_id: str = "", **detail: Any
    ) -> ExecutionAttestation:
        """Record an explicit attestation gap (e.g. ASIC absent)."""
        return self.record(
            ExecutionAttestation(
                kind="gap",
                device_id=device_id or "none",
                device_class="none",
                handle_id=None,
                window=None,
                timestamp_ns=time.monotonic_ns(),
                reason=reason,
                detail=detail,
            )
        )

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._rlock:
            return [r.as_dict() for r in self._records]

    def summary(self) -> Dict[str, Any]:
        with self._rlock:
            kinds: Dict[str, int] = {}
            for r in self._records:
                kinds[r.kind] = kinds.get(r.kind, 0) + 1
            return {
                "total": len(self._records),
                "by_kind": kinds,
                "devices": sorted({r.device_id for r in self._records}),
            }


# ---------------------------------------------------------------------------
# Consensus re-verification — the sole accept authority
# ---------------------------------------------------------------------------


def double_sha256(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


def verify_share(share: Share, header_prefix: bytes, target_be: bytes) -> bool:
    """Host-side consensus re-check: sha256d(header+nonce) <= target (BE)."""
    digest = double_sha256(share.header_with_nonce(header_prefix))
    if digest != share.digest:
        return False
    return digest[::-1] <= target_be


@runtime_checkable
class NonceScheduler(Protocol):
    """Device-agnostic window solver. See module docstring for the rules."""

    def capability(self) -> DeviceCapability: ...

    def dispatch(self, window: NonceWindow) -> DispatchHandle: ...

    def poll(self, handle: DispatchHandle) -> Optional[Share]: ...

    def cancel(self, handle: DispatchHandle) -> None: ...

    def attestation(self) -> List[ExecutionAttestation]: ...


def next_handle_id() -> int:
    return next(_HANDLE_IDS)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


__all__ = [
    "ASICNotPresent",
    "AttestationRegistry",
    "AttestationViolation",
    "DeviceCapability",
    "DeviceUnsupportedError",
    "DispatchHandle",
    "ExecutionAttestation",
    "NONCE_SPACE",
    "NonceScheduler",
    "NonceWindow",
    "Share",
    "canonical_json",
    "double_sha256",
    "next_handle_id",
    "verify_share",
]
