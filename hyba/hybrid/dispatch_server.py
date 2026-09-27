"""HTTP dispatch endpoint for the hybrid coordinator — deployable surface.

Exposes :class:`HybridCoordinator` over plain HTTP with no framework
dependency (stdlib ``http.server`` only). Endpoints:

- ``GET  /health``      — liveness + coordinator mode + device inventory
- ``GET  /capability``  — measured capability record per configured solver
- ``POST /dispatch``    — body ``{job_id, header80_hex, target_hex,
  nonce_space?, strategy?, session_epoch?, job_epoch?}``; responds with the
  full ``JobResult.as_dict()`` (share, coverage certificate, attestations)

Device binding is fail-closed:

- ``HYBRID_DEVICE_INDEX`` selects the Nth enumerated OpenCL GPU device.
  Out-of-range or unenumerable indices abort startup — the server never
  binds a different device than the one requested.
- ``HYBRID_ALLOW_CPU=1`` permits the hasher's honest CPU fallback;
  otherwise the absence of a GPU aborts startup.
- ``HYBRID_ASIC_ENDPOINT`` / ``HYBRID_ASIC_SERIAL`` / ``HYBRID_ASIC_PCIE``
  configure the real ASIC channels; absent channels become attestation
  gaps, never simulated devices.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple

from hyba.hybrid.asic_solver import ASICSolver
from hyba.hybrid.coordinator import HybridCoordinator, StratumJob
from hyba.hybrid.gpu_solver import GPUSolver
from hyba.hybrid.nonce_scheduler import AttestationRegistry


def _enumerate_gpus() -> list:
    try:
        import pyopencl as cl
    except Exception:
        return []
    try:
        return [
            d
            for p in cl.get_platforms()
            for d in p.get_devices()
            if d.type & cl.device_type.GPU
        ]
    except Exception:
        return []


def _bind_device_index() -> Optional[str]:
    """Resolve HYBRID_DEVICE_INDEX to a concrete device identity.

    Returns the bound device name, or None when the variable is unset.
    Raises SystemExit when the requested device is absent — fail closed.
    """
    raw = os.environ.get("HYBRID_DEVICE_INDEX", "").strip()
    if not raw:
        return None
    try:
        index = int(raw)
    except ValueError:
        raise SystemExit(f"HYBRID_DEVICE_INDEX={raw!r} is not an integer")
    gpus = _enumerate_gpus()
    if not (0 <= index < len(gpus)):
        raise SystemExit(
            f"HYBRID_DEVICE_INDEX={index} out of range: "
            f"{len(gpus)} OpenCL GPU device(s) enumerated "
            f"({[str(getattr(d, 'name', '?')) for d in gpus]})"
        )
    name = str(getattr(gpus[index], "name", "")).strip()
    # Bind the hasher's existing identity gate to the enumerated device.
    os.environ["HYBA_DEVICE_NAME"] = name
    os.environ["HYBRID_REQUIRE_HYBA"] = ""
    os.environ["HYBA_REQUIRE_HYBA"] = "1"
    return name


def build_coordinator() -> Tuple[HybridCoordinator, Dict[str, Any]]:
    """Construct solvers and the coordinator; fail closed on bad bindings."""
    bound = _bind_device_index()
    allow_cpu = os.environ.get("HYBRID_ALLOW_CPU", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    gpu = GPUSolver(backend="auto", allow_cpu=allow_cpu)
    asic = ASICSolver()  # probes configured channels; unsupported is honest
    coord = HybridCoordinator(gpu, asic)
    info = {
        "mode": coord.mode,
        "bound_device": bound,
        "gpu_capability": gpu.capability().as_dict(),
        "asic_capability": asic.capability().as_dict(),
    }
    return coord, info


def make_handler(coord: HybridCoordinator, boot: Dict[str, Any]):
    class DispatchHandler(BaseHTTPRequestHandler):
        server_version = "hyba-hybrid/1.0"

        def _json(self, code: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:  # quieter logs
            sys.stderr.write("dispatch_server: " + fmt % args + "\n")

        def do_GET(self) -> None:  # noqa: N802 - stdlib naming
            if self.path == "/health":
                self._json(200, {
                    "ok": True,
                    **boot,
                    "attestations": AttestationRegistry.get().summary(),
                })
            elif self.path == "/capability":
                self._json(200, {
                    "gpu": boot["gpu_capability"],
                    "asic": boot["asic_capability"],
                })
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib naming
            if self.path != "/dispatch":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(length) or b"{}")
                job = StratumJob(
                    job_id=str(req["job_id"]),
                    header80=bytes.fromhex(str(req["header80_hex"])),
                    target=bytes.fromhex(str(req["target_hex"])),
                    session_epoch=int(req.get("session_epoch", 0)),
                    job_epoch=int(req.get("job_epoch", 0)),
                    nonce_space=int(req.get("nonce_space", 1 << 32)),
                )
            except (KeyError, ValueError, TypeError) as exc:
                self._json(400, {"error": f"bad request: {exc}"})
                return
            strategy = str(req.get("strategy", "lucas"))
            try:
                result = coord.run_job(job, strategy=strategy)
            except Exception as exc:
                self._json(500, {
                    "error": f"{type(exc).__name__}: {exc}",
                    "mode": coord.mode,
                })
                return
            self._json(200, result.as_dict())

    return DispatchHandler


def main() -> int:
    host = os.environ.get("HYBRID_BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("HYBRID_PORT", "8080"))
    coord, boot = build_coordinator()
    sys.stderr.write(
        "dispatch_server: mode=%s bound=%s gpu=%s asic=%s\n"
        % (
            boot["mode"],
            boot["bound_device"],
            boot["gpu_capability"]["device_id"],
            boot["asic_capability"]["device_id"],
        )
    )
    server = ThreadingHTTPServer((host, port), make_handler(coord, boot))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
