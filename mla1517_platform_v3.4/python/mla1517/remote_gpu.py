"""Remote OpenCL device binding — a GPU/iGPU anywhere counts as hardware.

A real OpenCL device is a real OpenCL device whether it sits in this
machine, in the user's other PC, or in a rented cloud VM (AirGPU-class).
This module is the client side of that binding: it probes a
:class:`~mla1517.remote_gpu_agent` endpoint, imports its devices as
measured hardware, and dispatches the canonical Lucas/Pisot ladder and
bounded SHA-256d window scans to it.

HONESTY CONTRACT (same as OpenCLLadderExecutor)
----------------------------------------------
The remote device is *verified*, not trusted. Every ladder result the
agent returns is re-derived against the exact CPU reference here, and
every SHA-256d winner is recomputed against hashlib, checked against
the target, and checked for window membership; a mismatch raises
:class:`RemoteGPUVerificationError` rather than reporting device
output the substrate cannot prove. An unreachable or deviceless
endpoint reports honest unavailability — never a silent fallback and
never a fabricated device.

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

#: Largest contiguous / m32 window one remote call may scan.
SHA256D_MAX_WINDOW = 1 << 24
#: Largest explicit nonce list one remote call may carry (the upload is real).
SHA256D_MAX_BATCH = 1 << 20

__all__ = [
    "PROTOCOL_VERSION",
    "SHA256D_MAX_BATCH",
    "SHA256D_MAX_WINDOW",
    "RemoteGPUError",
    "RemoteGPUUnavailable",
    "RemoteGPUVerificationError",
    "RemoteDevice",
    "LadderResult",
    "Sha256dResult",
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
    device_type: str  # gpu | igpu | cpu | accelerator | other
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
    """One verified remote SHA-256d window scan.

    ``nonce``/``digest`` are ``None`` when the window produced no winner —
    that is a true result, not a failure. ``execution_backend`` records
    the substrate that actually ran on the agent host (``opencl:gpu``,
    ``opencl:cpu`` or ``cpu``), never the requested one.
    """

    nonce: Optional[int]
    digest: Optional[bytes]
    hashes: int
    device: str
    execution_backend: str
    measured_ns: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "nonce": self.nonce,
            "digest": self.digest.hex() if self.digest is not None else None,
            "hashes": self.hashes,
            "device": self.device,
            "execution_backend": self.execution_backend,
            "measured_ns": self.measured_ns,
            "verified_against_exact_reference": True,
        }


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

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
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
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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
        """Devices that can actually execute — gpu/igpu/accelerator only."""
        return [d for d in self.devices() if d.device_type in ("gpu", "igpu", "accelerator")]

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
        target_be: bytes,
        *,
        order: str = "contiguous",
        base_nonce: int = 0,
        count: int = 0,
        lane_order: Optional[List[int]] = None,
        nonces: Optional[List[int]] = None,
    ) -> Sha256dResult:
        """Dispatch one bounded SHA-256d window to the agent and VERIFY it.

        ``order`` selects the traversal the agent must run:

        * ``contiguous`` — ``nonce = base_nonce + i`` for ``count`` steps.
        * ``m32`` — the lane-order traversal; requires ``lane_order``.
        * ``batch`` — an explicit ``nonces`` list (the upload is real work).

        The exact hashlib reference is the invariant here — identical to
        ``execute_ladder``. A reported winner is accepted only when its
        recomputed double-SHA256 equals the returned digest, meets the
        target, and lies inside the dispatched window; a no-winner reply
        is accepted only when the agent reports having ground the whole
        window. Anything else raises :class:`RemoteGPUVerificationError`.
        """
        if len(header) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be exactly 32 bytes")
        body: Dict[str, Any] = {
            "header": header.hex(),
            "target": target_be.hex(),
            "order": order,
        }
        window_size: int
        if order == "batch":
            if not nonces:
                raise ValueError("batch order requires a non-empty nonces list")
            if len(nonces) > SHA256D_MAX_BATCH:
                raise ValueError(f"batch exceeds {SHA256D_MAX_BATCH} nonces")
            body["nonces"] = [int(n) & 0xFFFFFFFF for n in nonces]
            window_size = len(nonces)
        else:
            count = int(count)
            if not 1 <= count <= SHA256D_MAX_WINDOW:
                raise ValueError(f"count must be in [1, {SHA256D_MAX_WINDOW}]")
            body["base_nonce"] = int(base_nonce) & 0xFFFFFFFF
            body["count"] = count
            window_size = count
            if order == "m32":
                lanes = [int(l) for l in (lane_order or [])]
                if len(lanes) != 32 or sorted(lanes) != list(range(32)):
                    raise ValueError("m32 order requires all 32 lanes exactly once")
                if count % 32:
                    raise ValueError("m32 grind window must be a multiple of 32")
                body["lane_order"] = lanes
            elif order != "contiguous":
                raise ValueError(f"unsupported sha256d order {order!r}")
        reply = self._request("POST", "/v1/sha256d", body)
        device = str((reply.get("device") or {}).get("name", "remote"))
        backend = str(reply.get("execution_backend", "unknown"))
        measured_ns = reply.get("measured_ns")
        hashes = reply.get("hashes")
        if not isinstance(hashes, int) or hashes < 0 or hashes > window_size:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} reported hashes={hashes!r} for a window of {window_size}"
            )
        winner = reply.get("winner")
        if not winner:
            if hashes != window_size:
                raise RemoteGPUVerificationError(
                    f"{self.endpoint} reported no winner but only {hashes}/{window_size} hashes"
                )
            return Sha256dResult(None, None, hashes, device, backend, measured_ns)
        nonce = winner.get("nonce")
        digest_hex = winner.get("digest")
        if not isinstance(nonce, int) or not 0 <= nonce <= 0xFFFFFFFF or not digest_hex:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} returned malformed winner {winner!r}"
            )
        try:
            digest = bytes.fromhex(str(digest_hex))
        except ValueError as exc:
            raise RemoteGPUVerificationError(f"{self.endpoint} winner digest is not hex") from exc
        if len(digest) != 32:
            raise RemoteGPUVerificationError(f"{self.endpoint} winner digest must be 32 bytes")
        if order == "batch":
            in_window = nonce in body["nonces"]
        else:
            in_window = ((nonce - int(body["base_nonce"])) & 0xFFFFFFFF) < window_size
        if not in_window:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} winner nonce {nonce} lies outside the dispatched window"
            )
        blob = header[:76] + struct.pack("<I", nonce & 0xFFFFFFFF)
        reference = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        if digest != reference:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} winner digest fails the hashlib recheck (nonce {nonce})"
            )
        if reference[::-1] > target_be:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} winner digest does not meet the target (nonce {nonce})"
            )
        return Sha256dResult(nonce, digest, hashes, device, backend, measured_ns)


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
        reasons.append(f"{ep}: reachable but no usable gpu/igpu/accelerator")
    return None, [], "; ".join(reasons) if reasons else "no remote endpoints configured"
