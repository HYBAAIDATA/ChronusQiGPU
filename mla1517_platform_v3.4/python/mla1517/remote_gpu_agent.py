"""Remote GPU agent — runs ON the machine that has the OpenCL device.

Start it on any host with a GPU/iGPU — a local PC, a workstation, or a
cloud VM (AirGPU-class). The platform then binds to it with
``MLA1517_REMOTE_GPU_ENDPOINT=http://<host>:<port>`` and the remote
device counts as real hardware everywhere hardware is required.

    python -m mla1517.remote_gpu_agent --host 0.0.0.0 --port 8632

Endpoints:
    GET  /v1/health   -> liveness + protocol version + device count
    GET  /v1/devices  -> measured OpenCL devices (never fabricated)
    POST /v1/ladder   -> {"scales":[...]} executes the exact Lucas/Pisot
                         ladder on the real device and returns the rows
                         plus measured wall time. The client re-verifies
                         every row against exact integer arithmetic.
    POST /v1/sha256d  -> {"header":hex80, "target":hex32, "order":...}
                         executes one bounded SHA-256d window through the
                         canonical mining hasher (mining.bitcoin_hasher)
                         and returns the winner plus the true execution
                         backend — "opencl:gpu"/"opencl:cpu"/"cpu", never
                         a claimed one. The client re-verifies the winner
                         against hashlib, so a network hop cannot weaken
                         the proof.

Honesty contract: pyopencl is imported lazily so the agent answers
honestly on a host without OpenCL — ``devices: []`` plus the recorded
reason — instead of crashing or pretending. Set
``MLA1517_REMOTE_GPU_TOKEN`` to require a shared bearer token on both
sides; the agent binds to localhost by default and only listens
externally when explicitly told.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .remote_gpu import PROTOCOL_VERSION, SHA256D_MAX_BATCH, SHA256D_MAX_WINDOW

__all__ = ["enumerate_devices", "build_server", "main"]

_SERVICE = "mla1517-remote-gpu-agent"


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
        return "igpu" if (unified or vendor.startswith(("intel", "apple"))) else "gpu"
    if dtype & int(getattr(cl.device_type, "CPU", 0) or 0):
        return "cpu"
    if dtype & int(getattr(cl.device_type, "ACCELERATOR", 0) or 0):
        return "accelerator"
    return "other"


def enumerate_devices() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Measured device records for the agent host.

    Same capability vocabulary as ``hyba.inventory._probe_opencl`` so a
    remote device is interchangeable with a local one downstream.
    Returns ``(devices, error)`` — error set exactly when enumeration
    itself was impossible.
    """
    try:
        import pyopencl as cl
    except ImportError:
        return [], "pyopencl is not installed on the agent host"
    try:
        platforms = cl.get_platforms()
    except Exception as exc:
        return [], f"OpenCL runtime reported no platforms: {exc}"
    out: List[Dict[str, Any]] = []
    for platform in platforms:
        try:
            devices = platform.get_devices()
        except Exception:
            continue
        for dev in devices:
            caps: Dict[str, Any] = {}
            try:
                caps["fp64"] = "cl_khr_fp64" in str(getattr(dev, "extensions", "") or "")
            except Exception:
                pass
            try:
                caps["local_mem_kb"] = int(dev.local_mem_size) // 1024
            except Exception:
                pass
            try:
                caps["max_workgroup"] = int(dev.max_work_group_size)
            except Exception:
                pass
            try:
                caps["host_unified_memory"] = bool(dev.get_info(cl.device_info.HOST_UNIFIED_MEMORY))
            except Exception:
                pass
            caps["m32_lane_kernel"] = True
            caps["lucas_ladder_kernel"] = True
            caps["sha256d_kernel"] = True
            rec: Dict[str, Any] = {
                "name": str(getattr(dev, "name", "") or "").strip(),
                "vendor": str(getattr(dev, "vendor", "") or "").strip(),
                "type": _device_type_name(cl, dev),
                "platform": str(getattr(platform, "name", "") or "").strip(),
                "capabilities": caps,
            }
            try:
                rec["compute_units"] = int(dev.max_compute_units)
            except Exception:
                pass
            try:
                rec["global_mem_mb"] = int(dev.global_mem_size) // (1024 * 1024)
            except Exception:
                pass
            out.append(rec)
    return out, None


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


_SHA256D_HASHER: Any = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256d_hasher() -> Any:
    """The canonical mining hasher bound once per agent process.

    ``mining.bitcoin_hasher`` is imported lazily so the agent module loads
    (and answers /v1/health honestly) on a host where the repo-root
    packages or OpenCL are absent. On a deviceless host the hasher still
    works — it falls back to the CPU backend and the response records the
    true backend plus its fallback reason, never a fabricated GPU label.
    """
    global _SHA256D_HASHER
    if _SHA256D_HASHER is None:
        try:
            from mining.bitcoin_hasher import BitcoinHasher
        except ImportError:
            root = str(_repo_root())
            if root not in sys.path:
                sys.path.append(root)
            from mining.bitcoin_hasher import BitcoinHasher
        _SHA256D_HASHER = BitcoinHasher(backend="auto")
    return _SHA256D_HASHER


def _run_sha256d(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one bounded SHA-256d window on the agent's real device.

    The winner (when any) is already re-verified against hashlib inside
    the hasher before it is reported; the ``execution_backend`` field
    records the substrate that actually ran — ``opencl:gpu``, ``opencl:cpu``
    or ``cpu`` — so a remote caller sees the physical truth, not the
    requested backend.
    """
    try:
        header = bytes.fromhex(str(payload.get("header", "")))
        target = bytes.fromhex(str(payload.get("target", "")))
    except ValueError as exc:
        raise ValueError(f"header/target must be hex bytes: {exc}") from exc
    if len(header) != 80:
        raise ValueError("header must be exactly 80 bytes")
    if len(target) != 32:
        raise ValueError("target must be exactly 32 bytes")
    order = str(payload.get("order", "contiguous"))
    if order == "batch":
        nonces = payload.get("nonces")
        if not isinstance(nonces, list) or not nonces:
            raise ValueError("batch order requires a non-empty nonces list")
        if len(nonces) > SHA256D_MAX_BATCH:
            raise ValueError(f"batch exceeds {SHA256D_MAX_BATCH} nonces")
        try:
            nonces = [int(n) & 0xFFFFFFFF for n in nonces]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"nonces must be uint32 integers: {exc}") from exc
    else:
        try:
            base = int(payload.get("base_nonce", 0)) & 0xFFFFFFFF
            count = int(payload.get("count", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"base_nonce/count must be integers: {exc}") from exc
        if not 1 <= count <= SHA256D_MAX_WINDOW:
            raise ValueError(f"count must be in [1, {SHA256D_MAX_WINDOW}]")
        if order not in ("contiguous", "m32"):
            raise ValueError(f"unsupported sha256d order {order!r}")
        if order == "m32":
            lanes = payload.get("lane_order")
            if not isinstance(lanes, list):
                raise ValueError("m32 order requires lane_order")
        span = count
    hasher = _sha256d_hasher()
    start = time.perf_counter_ns()
    if order == "batch":
        nonce, digest, hashes = hasher.grind_target_batch(header, target, nonces)
    elif order == "contiguous":
        nonce, digest, hashes = hasher.grind_target_range_chunked(header, target, base, count)
    else:
        nonce, digest, hashes = hasher.grind_target_m32(header, target, base, lanes, count)
    measured_ns = time.perf_counter_ns() - start
    out: Dict[str, Any] = {
        "device": {"name": str(hasher.device)},
        "execution_backend": hasher.backend,
        "order": order,
        "hashes": int(hashes),
        "window": int(span),
        "measured_ns": measured_ns,
        "winner": ({"nonce": int(nonce), "digest": digest.hex()} if nonce is not None else None),
    }
    if hasher.fallback_reason:
        out["fallback_reason"] = hasher.fallback_reason
    return out


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
                    "endpoints": ["ladder", "sha256d"],
                },
            )
            return
        if self.path == "/v1/devices":
            devices, error = enumerate_devices()
            self._send(200, {"protocol": PROTOCOL_VERSION, "devices": devices, "error": error})
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
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"bad request: {exc}"})
            return
        if self.path == "/v1/ladder":
            try:
                scales = [int(s) for s in body.get("scales", [])]
            except (TypeError, ValueError) as exc:
                self._send(400, {"error": f"bad scales: {exc}"})
                return
            if not scales:
                self._send(400, {"error": "scales must be a non-empty list"})
                return
            try:
                payload = _run_ladder(scales)
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
                return
            except Exception as exc:
                # GPUExecutionUnavailable or a device failure — honest 503.
                self._send(503, {"error": f"{type(exc).__name__}: {exc}"})
                return
        else:
            try:
                payload = _run_sha256d(body)
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
                return
            except Exception as exc:
                # Hasher unavailable or a device failure — honest 503.
                self._send(503, {"error": f"{type(exc).__name__}: {exc}"})
                return
        payload["protocol"] = PROTOCOL_VERSION
        self._send(200, payload)


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _Handler)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=_SERVICE)
    parser.add_argument(
        "--host", default="127.0.0.1", help="bind address; use 0.0.0.0 to serve remote callers"
    )
    parser.add_argument("--port", type=int, default=8632)
    args = parser.parse_args(argv)
    server = build_server(args.host, args.port)
    devices, error = enumerate_devices()
    print(
        json.dumps(
            {
                "service": _SERVICE,
                "listen": f"http://{args.host}:{args.port}",
                "protocol": PROTOCOL_VERSION,
                "device_count": len(devices),
                "opencl_error": error,
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
