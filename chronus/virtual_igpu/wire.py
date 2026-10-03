"""stdlib HTTP/JSON daemon exposing virtual_igpu_v1."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from typing import Any
from urllib.parse import urlparse

from .abi import ABI_VERSION, Workload
from .runtime import RuntimeDaemon


def build_server(runtime: RuntimeDaemon, host: str = "127.0.0.1", port: int = 8765):
    token = os.getenv("CHRONUS_VIGPU_TOKEN", "")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): return

        def send_json(self, code: int, value: dict[str, Any]) -> None:
            body = json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self) -> bool:
            return not token or self.headers.get("Authorization") == f"Bearer {token}"

        def do_GET(self):
            if not self.authorized():
                return self.send_json(401, {"ok": False, "error": "unauthorized"})
            path = urlparse(self.path).path
            if path == "/health":
                return self.send_json(200, {"ok": True, "value": {"protocol": ABI_VERSION}})
            if path == "/v1/adapters":
                return self.send_json(200, {"ok": True, "value": runtime.adapter_report()})
            if path == "/v1/capabilities":
                return self.send_json(200, {"ok": True, "value": runtime.capabilities()})
            if path.startswith("/v1/workloads/"):
                wid = path.rsplit("/", 1)[-1]
                result = runtime.results.get(wid)
                return self.send_json(
                    200 if result else 404,
                    {"ok": bool(result), "value": result.as_dict() if result else None,
                     "error": None if result else "not found"},
                )
            if path == "/v1/evidence":
                return self.send_json(
                    200,
                    {
                        "ok": True,
                        "value": [
                            {
                                "workload_id": result.workload_id,
                                "evidence_digest": result.evidence_digest,
                                "object_id": result.object_id,
                            }
                            for result in runtime.results.values()
                        ],
                    },
                )
            if path == "/v1/attestation":
                return self.send_json(
                    200,
                    {
                        "ok": True,
                        "value": {
                            "protocol": ABI_VERSION,
                            "adapters": [
                                row["attestation"] for row in runtime.adapter_report()
                            ],
                            "negotiations": runtime.negotiations,
                        },
                    },
                )
            return self.send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if not self.authorized():
                return self.send_json(401, {"ok": False, "error": "unauthorized"})
            if urlparse(self.path).path != "/v1/workloads":
                return self.send_json(404, {"ok": False, "error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                workload = Workload.from_dict(json.loads(self.rfile.read(length)))
                result = runtime.submit(workload)
            except Exception as exc:
                return self.send_json(
                    422, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                )
            return self.send_json(200, {"ok": True, "value": result.as_dict()})

    return ThreadingHTTPServer((host, port), Handler)