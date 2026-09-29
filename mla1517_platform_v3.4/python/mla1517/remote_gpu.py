"""Remote OpenCL device binding — a GPU/iGPU anywhere counts as hardware.

A real OpenCL device is a real OpenCL device whether it sits in this
machine, in the user's other PC, or in a rented cloud VM (AirGPU-class).
This module is the client side of that binding: it probes a
:class:`~mla1517.remote_gpu_agent` endpoint, imports its devices as
measured hardware, and dispatches the canonical Lucas/Pisot ladder to it.

HONESTY CONTRACT (same as OpenCLLadderExecutor)
----------------------------------------------
The remote device is *verified*, not trusted. Every ladder result the
agent returns is re-derived against the exact CPU reference here; a
mismatch raises :class:`RemoteGPUVerificationError` rather than
reporting device output the substrate cannot prove. An unreachable or
deviceless endpoint reports honest unavailability — never a silent
fallback and never a fabricated device.

Endpoints come from ``MLA1517_REMOTE_GPU_ENDPOINT`` (single URL) or
``HYBA_REMOTE_OPENCL_ENDPOINTS`` (comma-separated list) for the HYBA
inventory tier. An optional shared bearer token lives in
``MLA1517_REMOTE_GPU_TOKEN`` — it gates the wire, it is not sent in
URLs and it is never logged.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .core import fib, lucas
from .scaling import LUCAS_PISOT_LADDER, padovan

PROTOCOL_VERSION = "remote_opencl_v1"
DEFAULT_TIMEOUT_S = 5.0

__all__ = [
    "PROTOCOL_VERSION",
    "RemoteGPUError",
    "RemoteGPUUnavailable",
    "RemoteGPUVerificationError",
    "RemoteDevice",
    "LadderResult",
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
