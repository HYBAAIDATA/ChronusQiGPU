"""Remote OpenCL device binding — a GPU/iGPU anywhere counts as hardware.

A real OpenCL device is a real OpenCL device whether it sits in this
machine, in the user's other PC, or in a rented cloud VM (AirGPU-class).
This module is the client side of that binding: it probes a
:class:`~chronus.mla1517.remote_gpu_agent` endpoint, imports its devices as
measured hardware, and dispatches the canonical Lucas/Pisot ladder or a
SHA-256d window scan to it.

HONESTY CONTRACT (same as OpenCLLadderExecutor)
----------------------------------------------
The remote device is *verified*, not trusted. Every ladder result the
agent returns is re-derived against the exact CPU reference here; a
mismatch raises :class:`RemoteGPUVerificationError` rather than
reporting device output the substrate cannot prove. For ``/v1/sha256d``
the same rule binds byte-for-byte: a returned share must carry the nonce
inside the requested window, a digest equal to the exact hashlib
recomputation, and a value meeting the job target — and the whole
verdict must carry the recomputed attestation token binding it to this
exact job, so replay of another window's answer is detected. A miss is
reported with its measured hash count; the negative cannot be
re-executed cheaply, so the contract verifies shares exactly and reports
scans honestly. An unreachable or deviceless endpoint reports honest
unavailability — never a silent fallback and never a fabricated device.

Endpoints come from ``MLA1517_REMOTE_GPU_ENDPOINT`` (single URL) or
``HYBA_REMOTE_OPENCL_ENDPOINTS`` (comma-separated list) for the HYBA
inventory tier. An optional shared bearer token lives in
``MLA1517_REMOTE_GPU_TOKEN`` — it gates the wire, it is not sent in
URLs and it is never logged.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .core import fib, lucas
from .scaling import LUCAS_PISOT_LADDER, padovan

PROTOCOL_VERSION = "remote_opencl_v1"
DEFAULT_TIMEOUT_S = 5.0
#: Scans run far longer than a probe, so sha256d calls get their own budget.
SHA256D_DEFAULT_TIMEOUT_S = 300.0
#: Upper bound on one remote scan request. It equals the m32 pipeline
#: window cap so a single POST can carry exactly one pipeline window and
#: no more — chunking inside the window is the agent's device policy.
SHA256D_MAX_WINDOW = 1 << 27

__all__ = [
    "PROTOCOL_VERSION",
    "DEFAULT_TIMEOUT_S",
    "SHA256D_DEFAULT_TIMEOUT_S",
    "SHA256D_MAX_WINDOW",
    "RemoteGPUError",
    "RemoteGPUUnavailable",
    "RemoteGPUVerificationError",
    "RemoteDevice",
    "LadderResult",
    "Sha256dResult",
    "sha256d_share_attestation",
    "RemoteGPUClient",
    "remote_endpoints",
    "probe_first_reachable",
]


class RemoteGPUError(RuntimeError):
    """Base class for remote-GPU binding failures."""


class RemoteGPUUnavailable(RemoteGPUError):
    """The endpoint cannot be reached or reports no usable device."""


class RemoteGPUVerificationError(RemoteGPUError):
    """The endpoint answered, but its result failed the exact invariant."""


@dataclass(frozen=True)
class RemoteDevice:
    """One OpenCL device measured by a remote agent."""

    name: str
    vendor: str
    device_type: str  # gpu | chronus | cpu | accelerator | other
    compute_units: Optional[int]
    global_mem_mb: Optional[int]
    platform: str
    endpoint: str
    capabilities: Tuple[Tuple[str, Any], ...] = ()

    def capability(self, key: str, default: Any = None) -> Any:
        return dict(self.capabilities).get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "type": self.device_type,
            "compute_units": self.compute_units,
            "global_mem_mb": self.global_mem_mb,
            "platform": self.platform,
            "endpoint": self.endpoint,
            "capabilities": dict(self.capabilities),
            "backend": "opencl_remote",
        }


@dataclass(frozen=True)
class LadderResult:
    """One verified remote ladder rung."""

    scale: int
    fibonacci: int
    lucas: int
    padovan: int
    device: str
    measured_ns: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scale": self.scale,
            "fibonacci": self.fibonacci,
            "lucas": self.lucas,
            "padovan": self.padovan,
            "device": self.device,
            "measured_ns": self.measured_ns,
            "verified_against_exact_reference": True,
        }


@dataclass(frozen=True)
class Sha256dResult:
    """A remote SHA-256d window scan with a client-verified verdict.

    ``nonce``/``digest`` are set only when the window contained a share.
    ``share_verified`` is True exactly when a share came back and passed
    the exact hashlib recomputation; on a miss it is False — nothing was
    returned to verify, and the ``hashes`` count is the agent's measured
    work report rather than a re-executed proof.
    """

    base_nonce: int
    count: int
    hashes: int
    nonce: Optional[int]
    digest: Optional[bytes]
    device: str
    execution_backend: str
    measured_ns: Optional[int]
    attestation: str
    share_verified: bool

    @property
    def found(self) -> bool:
        return self.nonce is not None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "window": {"base_nonce": self.base_nonce, "count": self.count},
            "hashes": self.hashes,
            "share": (
                None
                if self.nonce is None
                else {"nonce": self.nonce, "hash": self.digest.hex()}
            ),
            "device": self.device,
            "execution_backend": self.execution_backend,
            "measured_ns": self.measured_ns,
            "attestation": self.attestation,
            "share_verified_against_exact_reference": self.share_verified,
        }


def sha256d_share_attestation(
    *,
    header_hex: str,
    target_hex: str,
    base_nonce: int,
    count: int,
    hashes: int,
    nonce: Optional[int],
    digest_hex: Optional[str],
    device: str,
) -> str:
    """Domain-separated SHA-256 binding a share verdict to its exact job.

    Agent and client compute the token over the same canonical record, so
    a verdict replayed from another job (or a tampered window, count, or
    device name) fails the recomputation check. This is a binding
    certificate, not authentication — the bearer token gates the wire.
    """
    record = {
        "schema": "remote-sha256d-share-v1",
        "header": header_hex,
        "target": target_hex,
        "base_nonce": int(base_nonce),
        "count": int(count),
        "hashes": int(hashes),
        "nonce": nonce,
        "hash": digest_hex,
        "device": device,
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "RSHA256D-" + hashlib.sha256(canonical).hexdigest()


def _token() -> str:
    return os.environ.get("MLA1517_REMOTE_GPU_TOKEN", "").strip()


def remote_endpoints() -> List[str]:
    """Configured remote endpoints, HYBA list first, then the single var."""
    out: List[str] = []
    raw = os.environ.get("HYBA_REMOTE_OPENCL_ENDPOINTS", "")
    for part in raw.split(","):
        part = part.strip()
        if part:
            out.append(part)
    single = os.environ.get("MLA1517_REMOTE_GPU_ENDPOINT", "").strip()
    if single and single not in out:
        out.append(single)
    return out


class RemoteGPUClient:
    """HTTP/JSON client for one remote GPU agent endpoint."""

    def __init__(self, endpoint: str, timeout: float = DEFAULT_TIMEOUT_S):
        if not endpoint.startswith(("http://", "https://")):
            endpoint = "http://" + endpoint
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint + path,
            data=data,
            method=method,
            headers={"Accept": "application/json"},
        )
        if data is not None:
            req.add_header("Content-Type", "application/json")
        token = _token()
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RemoteGPUUnavailable(
                f"{self.endpoint}{path} -> HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise RemoteGPUUnavailable(f"{self.endpoint}{path} unreachable: {exc}") from exc

    def health(self) -> Dict[str, Any]:
        reply = self._request("GET", "/v1/health")
        if reply.get("protocol") != PROTOCOL_VERSION:
            raise RemoteGPUUnavailable(
                f"{self.endpoint} speaks protocol {reply.get('protocol')!r}, "
                f"expected {PROTOCOL_VERSION!r}"
            )
        return reply

    def devices(self) -> List[RemoteDevice]:
        """Enumerate the agent's measured devices. Empty = honestly absent."""
        reply = self._request("GET", "/v1/devices")
        out: List[RemoteDevice] = []
        for d in reply.get("devices", []):
            caps = d.get("capabilities") or {}
            out.append(
                RemoteDevice(
                    name=str(d.get("name", "")),
                    vendor=str(d.get("vendor", "")),
                    device_type=str(d.get("type", "other")),
                    compute_units=d.get("compute_units"),
                    global_mem_mb=d.get("global_mem_mb"),
                    platform=str(d.get("platform", "")),
                    endpoint=self.endpoint,
                    capabilities=tuple(sorted(caps.items())),
                )
            )
        return out

    def usable_devices(self) -> List[RemoteDevice]:
        """Devices that can actually execute — gpu/chronus/accelerator only."""
        return [d for d in self.devices() if d.device_type in ("gpu", "chronus", "accelerator")]

    def execute_ladder(
        self, scales: Tuple[int, ...] = LUCAS_PISOT_LADDER
    ) -> Tuple[LadderResult, ...]:
        """Dispatch the ladder to the remote device and VERIFY it.

        The exact CPU reference is the invariant check here — identical
        to what OpenCLLadderExecutor does with a local device. A remote
        answer that does not match exact arithmetic is rejected, because
        a network hop must not weaken the proof.
        """
        for scale in scales:
            if scale not in LUCAS_PISOT_LADDER:
                raise ValueError(f"{scale} is not a declared Lucas-Pisot rung")
        reply = self._request("POST", "/v1/ladder", {"scales": list(scales)})
        rows = reply.get("results") or []
        device_name = str((reply.get("device") or {}).get("name", "remote"))
        measured_ns = reply.get("measured_ns")
        if len(rows) != len(scales):
            raise RemoteGPUVerificationError(
                f"{self.endpoint} returned {len(rows)} rows for {len(scales)} rungs"
            )
        verified: List[LadderResult] = []
        for scale, row in zip(scales, rows):
            f_exact, l_exact, p_exact = fib(scale), lucas(scale), padovan(scale)
            got = (
                int(row.get("fibonacci", -1)),
                int(row.get("lucas", -1)),
                int(row.get("padovan", -1)),
            )
            if got != (f_exact, l_exact, p_exact):
                raise RemoteGPUVerificationError(
                    f"{self.endpoint} rung {scale} failed exact check: "
                    f"device={got} exact={(f_exact, l_exact, p_exact)}"
                )
            verified.append(LadderResult(scale, got[0], got[1], got[2], device_name, measured_ns))
        return tuple(verified)

    def execute_sha256d(
        self,
        header: bytes,
        target: bytes,
        base_nonce: int = 0,
        count: int = SHA256D_MAX_WINDOW,
        timeout: Optional[float] = SHA256D_DEFAULT_TIMEOUT_S,
    ) -> Sha256dResult:
        """Dispatch a contiguous SHA-256d window scan and VERIFY the verdict.

        The agent grinds ``[base_nonce, base_nonce + count)`` in serial
        scan order on its real device and returns the first nonce whose
        double-SHA256 meets ``target`` (32-byte big-endian, matching
        ``BitcoinHasher.grind_target_range``). A returned share is
        re-derived byte-for-byte here — nonce inside the window, digest
        equal to the exact hashlib recomputation, value meeting the
        target — and the attestation token is recomputed so the verdict
        provably belongs to this job. A miss returns ``found == False``
        with the measured ``hashes`` count.
        """
        if len(header) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target) != 32:
            raise ValueError("target must be exactly 32 bytes")
        base_nonce = int(base_nonce)
        count = int(count)
        if not 0 <= base_nonce <= 0xFFFFFFFF:
            raise ValueError("base_nonce must be a uint32")
        if not 1 <= count <= SHA256D_MAX_WINDOW:
            raise ValueError(f"count must be in [1, {SHA256D_MAX_WINDOW}]")
        reply = self._request(
            "POST",
            "/v1/sha256d",
            {
                "header": header.hex(),
                "target": target.hex(),
                "base_nonce": base_nonce,
                "count": count,
            },
            timeout=timeout,
        )
        device_name = str((reply.get("device") or {}).get("name", "remote"))
        measured_ns = reply.get("measured_ns")
        backend = str(reply.get("execution_backend", "remote_opencl"))
        hashes = int(reply.get("hashes") or 0)
        share = reply.get("share")
        nonce = None if share is None else share.get("nonce")
        digest_hex = None if share is None else str(share.get("hash", ""))
        expected = sha256d_share_attestation(
            header_hex=header.hex(),
            target_hex=target.hex(),
            base_nonce=base_nonce,
            count=count,
            hashes=hashes,
            nonce=nonce,
            digest_hex=digest_hex,
            device=device_name,
        )
        if str(reply.get("attestation", "")) != expected:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} attestation mismatch — the verdict is not "
                "bound to this exact job"
            )
        if not 0 < hashes <= count or (share is None and hashes != count):
            raise RemoteGPUVerificationError(
                f"{self.endpoint} reported incoherent hash count {hashes} "
                f"for a window of {count}"
            )
        if share is None:
            return Sha256dResult(
                base_nonce,
                count,
                hashes,
                None,
                None,
                device_name,
                backend,
                measured_ns,
                expected,
                share_verified=False,
            )
        nonce_int = int(nonce)
        if not 0 <= nonce_int <= 0xFFFFFFFF or (
            (nonce_int - base_nonce) & 0xFFFFFFFF
        ) >= count:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} returned nonce {nonce_int} outside the window"
            )
        try:
            reported = bytes.fromhex(digest_hex)
        except ValueError as exc:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} returned a non-hex share digest"
            ) from exc
        if len(reported) != 32:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} returned a {len(reported)}-byte share digest"
            )
        blob = header[:76] + struct.pack("<I", nonce_int)
        exact = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        if exact != reported:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} share at nonce {nonce_int} fails the exact "
                "hashlib recheck"
            )
        if int.from_bytes(exact, "little") > int.from_bytes(target, "big"):
            raise RemoteGPUVerificationError(
                f"{self.endpoint} share at nonce {nonce_int} does not meet the "
                "job target"
            )
        return Sha256dResult(
            base_nonce,
            count,
            hashes,
            nonce_int,
            reported,
            device_name,
            backend,
            measured_ns,
            expected,
            share_verified=True,
        )


def probe_first_reachable(
    endpoints: Optional[List[str]] = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> "tuple[RemoteGPUClient | None, List[RemoteDevice], str]":
    """Probe configured endpoints in order; return first with a usable device.

    Returns ``(client, devices, reason)``. ``client`` is None when no
    endpoint yielded a usable device — the reason says exactly why each
    failed, which is the honest output callers must surface.
    """
    eps = endpoints if endpoints is not None else remote_endpoints()
    reasons: List[str] = []
    for ep in eps:
        client = RemoteGPUClient(ep, timeout=timeout)
        try:
            devices = client.usable_devices()
        except RemoteGPUError as exc:
            reasons.append(str(exc))
            continue
        if devices:
            return client, devices, f"remote device bound at {ep}"
        reasons.append(f"{ep}: reachable but no usable gpu/chronus/accelerator")
    return None, [], "; ".join(reasons) if reasons else "no remote endpoints configured"
