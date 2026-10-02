"""Remote GPU agent — runs ON the machine that has the OpenCL device.

Start it on any host with a GPU/iGPU — a local PC, a workstation, or a
cloud VM (AirGPU-class). The platform then binds to it with
``MLA1517_REMOTE_GPU_ENDPOINT=http://<host>:<port>`` and the remote
device counts as real hardware everywhere hardware is required.

    python -m chronus.mla1517.remote_gpu_agent --host 0.0.0.0 --port 8632

Endpoints:
    GET  /v1/health   -> liveness + protocol version + device count
    GET  /v1/devices  -> measured OpenCL devices (never fabricated)
    POST /v1/ladder   -> {"scales":[...]} executes the exact Lucas/Pisot
                         ladder on the real device and returns the rows
                         plus measured wall time. The client re-verifies
                         every row against exact integer arithmetic.
    GET  /v1/telemetry -> device temperature/power/utilization — every
                         field null unless a vendor probe on this host
                         really measured it; ``sources`` records which
                         probes ran, failed, or were absent.
    POST /v1/sha256d  -> {"header":<160-hex>, "target":<64-hex>,
                         "order":...} grinds a bounded nonce window on the
                         real device in contiguous, m32, or explicit-batch
                         order. The winning share is
                         rechecked with hashlib before it leaves the
                         agent, the verdict carries a domain-separated
                         attestation the client recomputes, and the
                         client re-verifies the share byte-for-byte —
                         a network hop must not weaken the proof.

Honesty contract: pyopencl is imported lazily so the agent answers
honestly on a host without OpenCL — ``devices: []`` plus the recorded
reason — instead of crashing or pretending. Set
``MLA1517_REMOTE_GPU_TOKEN`` to require a shared bearer token on both
sides; the agent binds to localhost by default and only listens
externally when explicitly told.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .remote_gpu import (
    PROTOCOL_VERSION,
    SHA256D_MAX_BATCH,
    SHA256D_MAX_WINDOW,
    _attestation_key,
    _window_commitment,
    sha256d_share_attestation,
)

__all__ = ["enumerate_devices", "build_server", "main"]

_SERVICE = "mla1517-remote-gpu-agent"
MAX_REQUEST_BYTES = 16 * 1024 * 1024
REQUEST_READ_TIMEOUT_S = 15.0
DEFAULT_MAX_WORKERS = 8
_SHA256D_BINDINGS: Dict[str, Tuple[Any, threading.Lock]] = {}
_SHA256D_BINDING_ERRORS: Dict[str, str] = {}
_SHA256D_BINDINGS_LOCK = threading.Lock()


def _opencl_error() -> Optional[str]:
    """Return the reason no OpenCL device can be used, or None."""
    try:
        import pyopencl as cl  # noqa: F401
    except ImportError:
        return "pyopencl is not installed on the agent host"
    try:
        platforms = cl.get_platforms()
    except Exception as exc:
        return f"OpenCL runtime reported no platforms: {exc}"
    if not any(platform.get_devices() for platform in platforms):
        return "OpenCL platforms present but no devices enumerated"
    return None


def _device_type_name(cl: Any, device: Any) -> str:
    dtype = int(getattr(device, "type", 0) or 0)
    if dtype & int(getattr(cl.device_type, "GPU", 0) or 0):
        try:
            unified = bool(device.get_info(getattr(cl.device_info, "HOST_UNIFIED_MEMORY")))
        except Exception:
            unified = False
        vendor = str(getattr(device, "vendor", "") or "").lower()
        return "chronus" if (unified or vendor.startswith(("intel", "apple"))) else "gpu"
    if dtype & int(getattr(cl.device_type, "CPU", 0) or 0):
        return "cpu"
    if dtype & int(getattr(cl.device_type, "ACCELERATOR", 0) or 0):
        return "accelerator"
    return "other"


def _stable_device_id(
    platform: Any, device: Any, platform_index: int, device_index: int
) -> str:
    fields = (
        getattr(platform, "name", ""), getattr(platform, "vendor", ""),
        getattr(platform, "version", ""), getattr(device, "vendor_id", ""),
        getattr(device, "name", ""), getattr(device, "version", ""),
        getattr(device, "driver_version", ""), platform_index, device_index,
    )
    material = "\x1f".join(str(value).strip() for value in fields).encode("utf-8")
    return "opencl-" + hashlib.sha256(material).hexdigest()[:24]


def _binding_for_device(device_id: str, device: Any) -> Tuple[Optional[Any], Optional[str]]:
    with _SHA256D_BINDINGS_LOCK:
        cached = _SHA256D_BINDINGS.get(device_id)
        if cached:
            return cached[0], None
        if device_id in _SHA256D_BINDING_ERRORS:
            return None, _SHA256D_BINDING_ERRORS[device_id]
        try:
            from mining.bitcoin_hasher import BitcoinHasher

            hasher = BitcoinHasher(backend="opencl", device=device)
            if not str(hasher.backend).startswith("opencl:"):
                raise RuntimeError(f"unexpected backend {hasher.backend!r}")
            _SHA256D_BINDINGS[device_id] = (hasher, threading.Lock())
            return hasher, None
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            _SHA256D_BINDING_ERRORS[device_id] = error
            return None, error


def enumerate_devices() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Enumerate devices and advertise SHA-256d only after per-device self-check."""
    try:
        import pyopencl as cl
    except ImportError:
        return [], "pyopencl is not installed on the agent host"
    try:
        platforms = cl.get_platforms()
    except Exception as exc:
        return [], f"OpenCL runtime reported no platforms: {exc}"
    out: List[Dict[str, Any]] = []
    for platform_index, platform in enumerate(platforms):
        try:
            devices = platform.get_devices()
        except Exception:
            continue
        for device_index, dev in enumerate(devices):
            device_id = _stable_device_id(
                platform, dev, platform_index, device_index
            )
            caps: Dict[str, Any] = {}
            try:
                caps["fp64"] = "cl_khr_fp64" in str(getattr(dev, "extensions", "") or "")
                caps["local_mem_kb"] = int(dev.local_mem_size) // 1024
                caps["max_workgroup"] = int(dev.max_work_group_size)
                caps["host_unified_memory"] = bool(
                    dev.get_info(cl.device_info.HOST_UNIFIED_MEMORY)
                )
            except Exception:
                pass
            hasher, bind_error = _binding_for_device(device_id, dev)
            caps["sha256d_kernel"] = hasher is not None
            caps["m32_lane_kernel"] = bool(
                hasher is not None and getattr(hasher, "k_m32", None) is not None
            )
            caps["sha256d_self_check"] = "pass" if hasher is not None else "failed"
            if bind_error:
                caps["sha256d_error"] = bind_error[:240]
            caps["lucas_ladder_kernel"] = True
            rec: Dict[str, Any] = {
                "id": device_id,
                "name": str(getattr(dev, "name", "") or "").strip(),
                "vendor": str(getattr(dev, "vendor", "") or "").strip(),
                "type": _device_type_name(cl, dev),
                "platform": str(getattr(platform, "name", "") or "").strip(),
                "capabilities": caps,
            }
            try:
                rec["compute_units"] = int(dev.max_compute_units)
                rec["global_mem_mb"] = int(dev.global_mem_size) // (1024 * 1024)
            except Exception:
                pass
            out.append(rec)
    return out, None


def _probe_nvidia_smi() -> Optional[List[Dict[str, Any]]]:
    """NVIDIA device telemetry via nvidia-smi, or None when absent."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [
                exe,
                "--query-gpu=name,temperature.gpu,power.draw,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    rows: List[Dict[str, Any]] = []
    for line in out.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue

        def _num(value: str) -> Optional[float]:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        rows.append(
            {
                "name": parts[0],
                "vendor": "NVIDIA",
                "temperature_c": _num(parts[1]),
                "power_w": _num(parts[2]),
                "utilization_pct": _num(parts[3]),
            }
        )
    return rows or None


def _probe_rocm_smi() -> Optional[List[Dict[str, Any]]]:
    """AMD device telemetry via rocm-smi JSON, or None when absent."""
    exe = shutil.which("rocm-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--showtemp", "--showpower", "--showuse", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        payload = json.loads(out.stdout)
    except ValueError:
        return None
    rows: List[Dict[str, Any]] = []
    for card, fields in payload.items():
        if not isinstance(fields, dict):
            continue

        def _first(substr: str) -> Optional[float]:
            for key, value in fields.items():
                if substr in str(key).lower():
                    try:
                        return float(str(value).split()[0])
                    except (TypeError, ValueError, IndexError):
                        continue
            return None

        rows.append(
            {
                "name": str(card),
                "vendor": "AMD",
                "temperature_c": _first("temperature"),
                "power_w": _first("power"),
                "utilization_pct": _first("gpu use"),
            }
        )
    return rows or None


#: Vendor probes the agent actually attempts, in order. OpenCL itself
#: carries no standard power/temperature query — a device with no vendor
#: tool installed reports nulls, never estimates.
_TELEMETRY_PROBES = (
    ("nvidia-smi", _probe_nvidia_smi),
    ("rocm-smi", _probe_rocm_smi),
)


def _telemetry() -> Dict[str, Any]:
    """Physical telemetry for the reply — measured fields or honest nulls."""
    devices, _ = enumerate_devices()
    rows: List[Dict[str, Any]] = [
        {
            "name": str(d.get("name", "")),
            "vendor": str(d.get("vendor", "")),
            "temperature_c": None,
            "power_w": None,
            "utilization_pct": None,
        }
        for d in devices
    ]
    sources: List[Dict[str, Any]] = []
    for tool, probe in _TELEMETRY_PROBES:
        try:
            measured = probe()
        except Exception as exc:
            sources.append({"tool": tool, "status": "error", "reason": str(exc)})
            continue
        if measured is None:
            sources.append({"tool": tool, "status": "unavailable"})
            continue
        sources.append({"tool": tool, "status": "measured"})
        for i, row in enumerate(measured):
            if i < len(rows):
                rows[i]["temperature_c"] = row.get("temperature_c")
                rows[i]["power_w"] = row.get("power_w")
                rows[i]["utilization_pct"] = row.get("utilization_pct")
    return {"devices": rows, "sources": sources}


def _run_ladder(scales: List[int]) -> Dict[str, Any]:
    """Execute the canonical ladder on the agent's real device."""
    from .scaling import LUCAS_PISOT_LADDER, OpenCLLadderExecutor

    for scale in scales:
        if scale not in LUCAS_PISOT_LADDER:
            raise ValueError(f"{scale} is not a declared Lucas-Pisot rung")
    executor = OpenCLLadderExecutor()
    start = time.perf_counter_ns()
    results = executor._execute_scales(tuple(scales))
    measured_ns = time.perf_counter_ns() - start
    device = executor.device
    return {
        "device": {
            "name": str(getattr(device, "name", "") or "").strip(),
            "vendor": str(getattr(device, "vendor", "") or "").strip(),
        },
        "execution_backend": executor.execution_backend,
        "measured_ns": measured_ns,
        "results": [
            {
                "scale": r.scale,
                "fibonacci": r.fibonacci,
                "lucas": r.lucas,
                "padovan": r.padovan,
            }
            for r in results
        ],
    }


def _sha256d_hasher(device_id: Optional[str]) -> Tuple[str, Any, threading.Lock]:
    devices, error = enumerate_devices()
    capable = [d for d in devices if d.get("capabilities", {}).get("sha256d_kernel")]
    if not capable:
        raise RuntimeError(error or "no self-checked SHA-256d OpenCL device")
    if device_id is None:
        if len(capable) != 1:
            raise ValueError("device_id is required when multiple SHA-256d devices are available")
        device_id = str(capable[0]["id"])
    match = next((d for d in capable if d["id"] == device_id), None)
    if match is None:
        raise ValueError(f"unknown or incapable device_id {device_id!r}")
    hasher, lock = _SHA256D_BINDINGS[device_id]
    return device_id, hasher, lock


def _require_int(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def _run_sha256d(body: Dict[str, Any]) -> Dict[str, Any]:
    """Validate, execute, recheck, and authenticate one exact nonce sequence."""
    allowed = {
        "header", "target", "order", "base_nonce", "count", "lane_order",
        "nonces", "device_id",
    }
    extra = set(body) - allowed
    if extra:
        raise ValueError(f"unknown fields: {sorted(extra)}")
    if type(body.get("header")) is not str or type(body.get("target")) is not str:
        raise ValueError("header and target must be hex strings")
    try:
        header = bytes.fromhex(body["header"])
        target = bytes.fromhex(body["target"])
    except ValueError as exc:
        raise ValueError(f"header and target must be valid hex: {exc}") from exc
    if len(header) != 80:
        raise ValueError("header must be exactly 80 bytes")
    if len(target) != 32:
        raise ValueError("target must be exactly 32 bytes")
    order = body.get("order", "contiguous")
    if type(order) is not str:
        raise ValueError("order must be text")
    requested_device = body.get("device_id")
    if requested_device is not None and (type(requested_device) is not str or not requested_device):
        raise ValueError("device_id must be non-empty text")
    if order == "batch":
        nonces = body.get("nonces")
        if not isinstance(nonces, list) or not nonces:
            raise ValueError("batch order requires a non-empty nonces list")
        if len(nonces) > SHA256D_MAX_BATCH:
            raise ValueError(f"batch exceeds {SHA256D_MAX_BATCH} nonces")
        nonces = [_require_int(n, "nonce", minimum=0, maximum=0xFFFFFFFF) for n in nonces]
        base_nonce, count = 0, len(nonces)
        selected_nonces = list(nonces)
        lanes = None
    elif order in ("contiguous", "m32"):
        base_nonce = _require_int(
            body.get("base_nonce", 0), "base_nonce", minimum=0, maximum=0xFFFFFFFF
        )
        count = _require_int(body.get("count"), "count", minimum=1, maximum=SHA256D_MAX_WINDOW)
        nonces = None
        if order == "m32":
            raw_lanes = body.get("lane_order")
            if not isinstance(raw_lanes, list) or len(raw_lanes) != 32:
                raise ValueError("m32 order requires 32 lane indices")
            lanes = [_require_int(x, "lane", minimum=0, maximum=31) for x in raw_lanes]
            if sorted(lanes) != list(range(32)) or count % 32:
                raise ValueError("m32 requires each lane once and a multiple-of-32 window")
            selected_nonces = [
                (base_nonce + lanes[i % 32] + 32 * (i // 32)) & 0xFFFFFFFF
                for i in range(count)
            ]
        else:
            lanes = None
            selected_nonces = [(base_nonce + i) & 0xFFFFFFFF for i in range(count)]
    else:
        raise ValueError(f"unsupported scan order {order!r}")

    device_id, hasher, device_lock = _sha256d_hasher(requested_device)
    with device_lock:
        start = time.perf_counter_ns()
        if order == "batch":
            nonce, digest, hashes = hasher.grind_target_batch(header, target, nonces)
        elif order == "m32":
            nonce, digest, hashes = hasher.grind_target_m32(
                header, target, base_nonce, lanes, count
            )
        else:
            nonce, digest, hashes = hasher.grind_target_range_chunked(
                header, target, base_nonce, count
            )
        measured_ns = time.perf_counter_ns() - start
    if type(hashes) is not int or not 0 < hashes <= count:
        raise RuntimeError(f"hasher returned incoherent hash count {hashes!r}")
    if nonce is None and hashes != count:
        raise RuntimeError("hasher reported a miss without scanning the full sequence")
    if nonce is not None:
        if type(nonce) is not int or nonce not in selected_nonces:
            raise RuntimeError("device returned a nonce outside the requested sequence")
        exact = hashlib.sha256(
            hashlib.sha256(header[:76] + struct.pack("<I", nonce)).digest()
        ).digest()
        if exact != digest or int.from_bytes(exact, "little") > int.from_bytes(target, "big"):
            raise RuntimeError("device-reported share failed the agent-side hashlib recheck")
    device_name = str(hasher.device)
    backend = str(hasher.backend)
    if backend not in ("opencl:gpu", "opencl:cpu"):
        raise RuntimeError(f"unapproved execution backend {backend!r}")
    digest_hex = digest.hex() if digest is not None else None
    commitment = _window_commitment(order, selected_nonces)
    attestation = sha256d_share_attestation(
        header_hex=header.hex(), target_hex=target.hex(), base_nonce=base_nonce,
        count=count, hashes=hashes, nonce=nonce, digest_hex=digest_hex,
        device=device_name, device_id=device_id, protocol=PROTOCOL_VERSION,
        execution_backend=backend, measured_ns=measured_ns, order=order,
        window_commitment=commitment, key=_attestation_key() or None,
    )
    return {
        "device": {"id": device_id, "name": device_name},
        "execution_backend": backend,
        "measured_ns": measured_ns,
        "window": {"base_nonce": base_nonce, "count": count},
        "order": order,
        "window_commitment": commitment,
        "hashes": hashes,
        "share": None if nonce is None else {"nonce": nonce, "hash": digest_hex},
        "attestation": attestation,
    }


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    required = os.environ.get("MLA1517_REMOTE_GPU_TOKEN", "").strip()
    if not required:
        return True
    header = handler.headers.get("Authorization", "")
    return header == f"Bearer {required}"


class _Handler(BaseHTTPRequestHandler):
    server_version = "MLA1517RemoteGPU/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # keep the wire quiet
        return

    def _send(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not _authorized(self):
            self._send(401, {"error": "unauthorized"})
            return
        if self.path == "/v1/health":
            devices, error = enumerate_devices()
            self._send(
                200,
                {
                    "status": "ok",
                    "service": _SERVICE,
                    "protocol": PROTOCOL_VERSION,
                    "device_count": len(devices),
                    "opencl_error": error,
                    # Routes this agent actually serves — the client binds
                    # only what is advertised here, never an assumed arm.
                    "endpoints": ["ladder", "sha256d", "telemetry"],
                },
            )
            return
        if self.path == "/v1/devices":
            devices, error = enumerate_devices()
            self._send(200, {"protocol": PROTOCOL_VERSION, "devices": devices, "error": error})
            return
        if self.path == "/v1/telemetry":
            payload = _telemetry()
            payload["protocol"] = PROTOCOL_VERSION
            self._send(200, payload)
            return
        self._send(404, {"error": f"unknown path {self.path}"})

    def do_POST(self) -> None:
        if not _authorized(self):
            self._send(401, {"error": "unauthorized"})
            return
        if self.path not in ("/v1/ladder", "/v1/sha256d"):
            self._send(404, {"error": f"unknown path {self.path}"})
            return
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("transfer encoding is not supported")
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length is required")
            length = int(raw_length)
            if not 1 <= length <= MAX_REQUEST_BYTES:
                raise ValueError(f"request body must be 1..{MAX_REQUEST_BYTES} bytes")
            self.connection.settimeout(REQUEST_READ_TIMEOUT_S)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("incomplete request body")
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("JSON body must be an object")
        except (ValueError, TypeError, json.JSONDecodeError, socket.timeout) as exc:
            self._send(400, {"error": f"bad request: {exc}"})
            return
        if self.path == "/v1/ladder":
            try:
                raw_scales = body.get("scales", [])
                if not isinstance(raw_scales, list) or any(type(x) is not int for x in raw_scales):
                    raise ValueError("scales must be a list of integers")
                scales = list(raw_scales)
            except (ValueError, TypeError) as exc:
                self._send(400, {"error": f"bad request: {exc}"})
                return
            if not scales:
                self._send(400, {"error": "scales must be a non-empty list"})
                return
            work = _run_ladder
            work_arg = scales
        else:
            work = _run_sha256d
            work_arg = body
        try:
            payload = work(work_arg)
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return
        except Exception as exc:
            # GPUExecutionUnavailable or a device failure — honest 503.
            self._send(503, {"error": f"{type(exc).__name__}: {exc}"})
            return
        payload["protocol"] = PROTOCOL_VERSION
        self._send(200, payload)


class _BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 32

    def __init__(self, address: Tuple[str, int], handler: Any, max_workers: int):
        self._worker_slots = threading.BoundedSemaphore(max_workers)
        super().__init__(address, handler)

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._worker_slots.acquire(blocking=False):
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n"
                    b"Content-Length: 0\r\n\r\n"
                )
            finally:
                self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def build_server(
    host: str, port: int, max_workers: int = DEFAULT_MAX_WORKERS
) -> ThreadingHTTPServer:
    if type(max_workers) is not int or not 1 <= max_workers <= 256:
        raise ValueError("max_workers must be in [1, 256]")
    return _BoundedThreadingHTTPServer((host, port), _Handler, max_workers)


def _external_bind(host: str) -> bool:
    return host not in ("127.0.0.1", "::1", "localhost")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=_SERVICE)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8632)
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--tls-cert")
    parser.add_argument("--tls-key")
    args = parser.parse_args(argv)
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error("--tls-cert and --tls-key must be provided together")
    if _external_bind(args.host):
        if not args.tls_cert:
            parser.error("non-loopback binds require TLS")
        if not os.environ.get("MLA1517_REMOTE_GPU_TOKEN", "").strip():
            parser.error("non-loopback binds require MLA1517_REMOTE_GPU_TOKEN")
        if not _attestation_key():
            parser.error("non-loopback binds require an attestation key")
    server = build_server(args.host, args.port, args.max_workers)
    scheme = "http"
    if args.tls_cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(args.tls_cert, args.tls_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    devices, error = enumerate_devices()
    print(json.dumps({
        "service": _SERVICE, "listen": f"{scheme}://{args.host}:{args.port}",
        "protocol": PROTOCOL_VERSION, "device_count": len(devices), "opencl_error": error,
        "tls": bool(args.tls_cert), "max_workers": args.max_workers,
    }), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
