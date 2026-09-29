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
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

from .remote_gpu import PROTOCOL_VERSION

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
        if self.path != "/v1/ladder":
            self._send(404, {"error": f"unknown path {self.path}"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            scales = [int(s) for s in body.get("scales", [])]
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"bad request: {exc}"})
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
