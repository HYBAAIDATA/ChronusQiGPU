"""stdlib HTTP/JSON daemon exposing virtual_igpu_v1."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import os
from typing import Any
from urllib.parse import urlparse

from .abi import ABI_VERSION, Workload
from .runtime import RuntimeDaemon

MAX_REQUEST_BYTES = 8 * 1024 * 1024


def make_handler(daemon: RuntimeDaemon, auth_token: str | None = None):
    class Handler(BaseHTTPRequestHandler):
        def _read_json(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError as exc:
                raise ValueError("invalid Content-Length") from exc
            if length <= 0:
                return {}
            if length > MAX_REQUEST_BYTES:
                raise ValueError("request body exceeds the configured limit")
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _auth_ok(self) -> bool:
            if not auth_token:
                return True
            header = self.headers.get("Authorization", "")
            return hmac.compare_digest(header, f"Bearer {auth_token}")

        def _send(self, code: int, payload: Any) -> None:
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            return  # quiet tests

        def do_GET(self) -> None:  # noqa: N802
            if not self._auth_ok():
                self._send(401, {"error": "unauthorized"})
                return
            path = urlparse(self.path).path
            try:
                if path in {"/health", "/v1/health"}:
                    self._send(200, daemon.health())
                    return
                if path.startswith("/poll/") or path.startswith("/v1/poll/"):
                    wid = path.rsplit("/", 1)[-1]
                    result = daemon.poll(wid)
                    if result is None:
                        self._send(200, {"status": "pending", "workload_id": wid})
                    else:
                        self._send(200, result.as_dict())
                    return
                self._send(404, {"error": "not_found", "path": path})
            except Exception as exc:
                self._send(500, {"error": type(exc).__name__, "detail": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            if not self._auth_ok():
                self._send(401, {"error": "unauthorized"})
                return
            path = urlparse(self.path).path
            try:
                if path in {"/submit", "/v1/submit"}:
                    data = self._read_json()
                    w = Workload.from_dict(data)
                    result = daemon.submit(w)
                    self._send(200, result.as_dict())
                    return
                if path.startswith("/cancel/") or path.startswith("/v1/cancel/"):
                    wid = path.rsplit("/", 1)[-1]
                    ok = daemon.cancel(wid)
                    self._send(200, {"cancelled": ok, "id": wid})
                    return
                self._send(404, {"error": "not_found", "path": path})
            except Exception as exc:
                self._send(400, {"error": type(exc).__name__, "detail": str(exc)})

    return Handler


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    store: str | None = None,
    auth_token: str | None = None,
) -> ThreadingHTTPServer:
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "localhost"
    if not loopback:
        raise ValueError(
            "the stdlib Virtual iGPU sidecar is loopback-only; "
            "use an authenticated HTTPS service for remote delivery"
        )
    daemon = RuntimeDaemon(root=store)
    daemon.attach()
    token = auth_token or os.getenv("CHRONUS_VIGPU_TOKEN")
    handler = make_handler(daemon, auth_token=token)
    return ThreadingHTTPServer((host, port), handler)


def create_server(host: str, port: int, **kwargs: Any) -> ThreadingHTTPServer:
    return serve(host, port, **kwargs)
