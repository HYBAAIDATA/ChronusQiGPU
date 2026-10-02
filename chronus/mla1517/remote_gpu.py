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
import hmac
import ipaddress
import json
import os
import struct
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .core import fib, lucas
from .scaling import LUCAS_PISOT_LADDER, padovan

PROTOCOL_VERSION = "remote_opencl_v2"
DEFAULT_TIMEOUT_S = 5.0
#: Scans run far longer than a probe, so sha256d calls get their own budget.
SHA256D_DEFAULT_TIMEOUT_S = 300.0
#: Largest contiguous / m32 window one remote call may scan.
SHA256D_MAX_WINDOW = 1 << 24
#: Largest explicit nonce list one remote call may carry (the upload is real).
SHA256D_MAX_BATCH = 1 << 20
SHA256D_MAX_RESPONSE_BYTES = 1 << 20
_ALLOWED_SHA256D_BACKENDS = frozenset(("opencl:gpu", "opencl:cpu"))

__all__ = [
    "PROTOCOL_VERSION",
    "SHA256D_MAX_BATCH",
    "DEFAULT_TIMEOUT_S",
    "SHA256D_DEFAULT_TIMEOUT_S",
    "SHA256D_MAX_WINDOW",
    "RemoteGPUError",
    "RemoteGPUUnavailable",
    "RemoteGPUVerificationError",
    "RemoteDevice",
    "LadderResult",
    "RemoteTelemetry",
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
    device_id: str
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
            "id": self.device_id,
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
class RemoteTelemetry:
    """One honest sample of the agent's physical telemetry.

    Every field is ``None`` unless the agent actually measured it — a
    device without a power/temperature probe reports ``None``, never an
    estimate. ``sources`` records which probes the agent attempted and
    why each produced or withheld a value.
    """

    device: str
    vendor: str
    temperature_c: Optional[float]
    power_w: Optional[float]
    utilization_pct: Optional[float]
    sources: Tuple[Dict[str, Any], ...] = ()


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
    hardware_provenance_verified: bool = False

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
            "hardware_provenance_verified": self.hardware_provenance_verified,
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
    device_id: str = "",
    protocol: str = PROTOCOL_VERSION,
    execution_backend: str = "opencl:gpu",
    measured_ns: Optional[int] = None,
    order: str = "contiguous",
    window_commitment: str = "",
    key: Optional[bytes] = None,
) -> str:
    """Bind a SHA-256d verdict to the complete execution record.

    With ``key`` this is an HMAC-SHA256 authentication token. Without a key
    it is only an integrity checksum and MUST NOT be treated as hardware
    provenance. The record includes protocol/backend/timing, stable device
    identity, scan order, and a commitment to the exact nonce sequence.
    """
    record = {
        "schema": "remote-sha256d-share-v2",
        "protocol": protocol,
        "header": header_hex,
        "target": target_hex,
        "order": order,
        "window_commitment": window_commitment,
        "base_nonce": int(base_nonce),
        "count": int(count),
        "hashes": int(hashes),
        "nonce": nonce,
        "hash": digest_hex,
        "device": device,
        "device_id": device_id,
        "execution_backend": execution_backend,
        "measured_ns": measured_ns,
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if key:
        return "RSHA256D-HMAC-" + hmac.new(key, canonical, hashlib.sha256).hexdigest()
    return "RSHA256D-SHA256-" + hashlib.sha256(canonical).hexdigest()


def _window_commitment(order: str, nonces: List[int]) -> str:
    payload = json.dumps(
        {"order": order, "nonces": [int(n) & 0xFFFFFFFF for n in nonces]},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _token() -> str:
    return os.environ.get("MLA1517_REMOTE_GPU_TOKEN", "").strip()


def _attestation_key() -> bytes:
    value = os.environ.get("MLA1517_REMOTE_GPU_ATTESTATION_KEY", "").strip() or _token()
    return value.encode("utf-8")


def _is_loopback_endpoint(endpoint: str) -> bool:
    host = (urlsplit(endpoint).hostname or "").casefold()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


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
        parsed = urlsplit(self.endpoint)
        if parsed.scheme != "https" and not _is_loopback_endpoint(self.endpoint):
            raise ValueError("non-loopback remote GPU endpoints require HTTPS")
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
                declared = int(resp.headers.get("Content-Length", "0") or 0)
                if declared > SHA256D_MAX_RESPONSE_BYTES:
                    raise RemoteGPUVerificationError("remote response exceeds size limit")
                raw = resp.read(SHA256D_MAX_RESPONSE_BYTES + 1)
                if len(raw) > SHA256D_MAX_RESPONSE_BYTES:
                    raise RemoteGPUVerificationError("remote response exceeds size limit")
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise RemoteGPUVerificationError("remote response must be a JSON object")
                return payload
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
                    device_id=str(d.get("id", "")),
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

    def telemetry(self) -> List[RemoteTelemetry]:
        """Sample the agent's physical telemetry. Empty = no devices."""
        reply = self._request("GET", "/v1/telemetry")
        out: List[RemoteTelemetry] = []
        sources = reply.get("sources") or []
        for d in reply.get("devices", []):
            out.append(
                RemoteTelemetry(
                    device=str(d.get("name", "")),
                    vendor=str(d.get("vendor", "")),
                    temperature_c=d.get("temperature_c"),
                    power_w=d.get("power_w"),
                    utilization_pct=d.get("utilization_pct"),
                    sources=tuple(sources),
                )
            )
        return out

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
        target: Optional[bytes] = None,
        *,
        target_be: Optional[bytes] = None,
        order: str = "contiguous",
        base_nonce: int = 0,
        count: int = SHA256D_MAX_WINDOW,
        lane_order: Optional[List[int]] = None,
        nonces: Optional[List[int]] = None,
        device_id: Optional[str] = None,
        timeout: Optional[float] = SHA256D_DEFAULT_TIMEOUT_S,
    ) -> Sha256dResult:
        """Dispatch a bounded SHA-256d scan and fail closed on malformed provenance."""
        if target is not None and target_be is not None:
            raise ValueError("specify target or target_be, not both")
        target = target if target is not None else target_be
        if len(header) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if target is None or len(target) != 32:
            raise ValueError("target must be exactly 32 bytes")
        if type(base_nonce) is not int:
            raise ValueError("base_nonce must be an integer")
        body: Dict[str, Any] = {"header": header.hex(), "target": target.hex(), "order": order}
        if device_id:
            body["device_id"] = str(device_id)
        if order == "batch":
            if not isinstance(nonces, list) or not nonces:
                raise ValueError("batch order requires a non-empty nonces list")
            if len(nonces) > SHA256D_MAX_BATCH:
                raise ValueError(f"batch exceeds {SHA256D_MAX_BATCH} nonces")
            if any(type(n) is not int or not 0 <= n <= 0xFFFFFFFF for n in nonces):
                raise ValueError("nonces must be uint32 integers")
            selected_nonces = list(nonces)
            body["nonces"] = selected_nonces
            base_nonce, count = 0, len(selected_nonces)
        elif order in ("contiguous", "m32"):
            if type(count) is not int:
                raise ValueError("count must be an integer")
            if not 0 <= base_nonce <= 0xFFFFFFFF:
                raise ValueError("base_nonce must be a uint32")
            if not 1 <= count <= SHA256D_MAX_WINDOW:
                raise ValueError(f"count must be in [1, {SHA256D_MAX_WINDOW}]")
            body.update({"base_nonce": base_nonce, "count": count})
            if order == "m32":
                if not isinstance(lane_order, list) or any(type(x) is not int for x in lane_order):
                    raise ValueError("m32 lane_order must contain integers")
                lanes = list(lane_order)
                if len(lanes) != 32 or sorted(lanes) != list(range(32)):
                    raise ValueError("m32 order requires all 32 lanes exactly once")
                if count % 32:
                    raise ValueError("m32 grind window must be a multiple of 32")
                body["lane_order"] = lanes
                selected_nonces = [
                    (base_nonce + lanes[i % 32] + 32 * (i // 32)) & 0xFFFFFFFF
                    for i in range(count)
                ]
            else:
                selected_nonces = [(base_nonce + i) & 0xFFFFFFFF for i in range(count)]
        else:
            raise ValueError(f"unsupported sha256d order {order!r}")

        commitment = _window_commitment(order, selected_nonces)
        try:
            reply = self._request("POST", "/v1/sha256d", body, timeout=timeout)
            required = {
                "protocol", "device", "execution_backend", "measured_ns", "window",
                "order", "window_commitment", "hashes", "share", "attestation",
            }
            if set(reply) != required:
                raise RemoteGPUVerificationError(
                    f"{self.endpoint} returned unexpected response fields: "
                    f"missing={sorted(required - set(reply))}, "
                    f"extra={sorted(set(reply) - required)}"
                )
            if reply["protocol"] != PROTOCOL_VERSION:
                raise RemoteGPUVerificationError("remote SHA-256d protocol mismatch")
            backend = reply["execution_backend"]
            if backend not in _ALLOWED_SHA256D_BACKENDS:
                raise RemoteGPUVerificationError(f"unapproved execution backend {backend!r}")
            device_obj = reply["device"]
            if not isinstance(device_obj, dict) or set(device_obj) != {"id", "name"}:
                raise RemoteGPUVerificationError("malformed device identity")
            device = device_obj["name"]
            returned_device_id = device_obj["id"]
            if not all(isinstance(x, str) and x for x in (device, returned_device_id)):
                raise RemoteGPUVerificationError("empty device identity")
            if device_id and returned_device_id != device_id:
                raise RemoteGPUVerificationError("agent executed on a different device")
            measured_ns = reply["measured_ns"]
            if type(measured_ns) is not int or measured_ns < 0:
                raise RemoteGPUVerificationError("malformed measured_ns")
            if reply["order"] != order or reply["window_commitment"] != commitment:
                raise RemoteGPUVerificationError("scan order/window commitment mismatch")
            window = reply["window"]
            if window != {"base_nonce": base_nonce, "count": count}:
                raise RemoteGPUVerificationError("returned window does not match request")
            hashes = reply["hashes"]
            window_size = len(selected_nonces)
            if type(hashes) is not int or not 0 < hashes <= window_size:
                raise RemoteGPUVerificationError("incoherent hash count")
            share = reply["share"]
            if share is not None and (
                not isinstance(share, dict) or set(share) != {"nonce", "hash"}
            ):
                raise RemoteGPUVerificationError("malformed share")
            nonce = None if share is None else share["nonce"]
            digest_hex = None if share is None else share["hash"]
            expected = sha256d_share_attestation(
                header_hex=header.hex(), target_hex=target.hex(), base_nonce=base_nonce,
                count=count, hashes=hashes, nonce=nonce, digest_hex=digest_hex,
                device=device, device_id=returned_device_id, protocol=PROTOCOL_VERSION,
                execution_backend=backend, measured_ns=measured_ns, order=order,
                window_commitment=commitment, key=_attestation_key() or None,
            )
            if not hmac.compare_digest(str(reply["attestation"]), expected):
                raise RemoteGPUVerificationError("attestation mismatch")
            provenance = bool(_attestation_key()) and self.endpoint.startswith("https://")
            if share is None:
                if hashes != window_size:
                    raise RemoteGPUVerificationError(
                        "no-share verdict did not scan the full window"
                    )
                return Sha256dResult(base_nonce, count, hashes, None, None, device, backend,
                                     measured_ns, expected, False, provenance)
            if type(nonce) is not int or nonce not in selected_nonces:
                raise RemoteGPUVerificationError("returned nonce is outside the requested sequence")
            if type(digest_hex) is not str:
                raise RemoteGPUVerificationError("share digest must be hex text")
            try:
                reported = bytes.fromhex(digest_hex)
            except ValueError as exc:
                raise RemoteGPUVerificationError("non-hex share digest") from exc
            if len(reported) != 32:
                raise RemoteGPUVerificationError("share digest must be 32 bytes")
            exact = hashlib.sha256(
                hashlib.sha256(header[:76] + struct.pack("<I", nonce)).digest()
            ).digest()
            if exact != reported:
                raise RemoteGPUVerificationError("share fails exact hashlib recheck")
            if int.from_bytes(exact, "little") > int.from_bytes(target, "big"):
                raise RemoteGPUVerificationError("share does not meet the target")
            return Sha256dResult(base_nonce, count, hashes, nonce, reported, device, backend,
                                 measured_ns, expected, True, provenance)
        except RemoteGPUError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise RemoteGPUVerificationError(
                f"{self.endpoint} returned a malformed SHA-256d response: {exc}"
            ) from exc


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
