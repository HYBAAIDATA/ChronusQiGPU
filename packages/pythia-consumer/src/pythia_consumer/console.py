"""Local consumer console — stdlib HTTP server, three tabs:

- Node: census + bundled/installed products
- Verify: receipt structural verification
- Intelligence: CIaaS endpoint status (PYTHIA_CIAAS_URL)

Binds 127.0.0.1 only. No auth surface: this is a local operator console.
"""

from __future__ import annotations

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any, Dict, Optional

from . import census, verify

_MAX_BODY = 1 << 20


def intelligence_status(timeout: float = 3.0) -> Dict[str, Any]:
    url = os.environ.get("PYTHIA_CIAAS_URL", "").strip().rstrip("/")
    if not url:
        return {"available": False, "configured": False,
                "note": "set PYTHIA_CIAAS_URL to enable the intelligence surface"}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            code = resp.status
        return {"available": code < 500, "configured": True, "endpoint": url, "http_status": code}
    except Exception as exc:
        return {"available": False, "configured": True, "endpoint": url,
                "error": f"{type(exc).__name__}: {exc}"}


def make_handler(api_url: Optional[str]):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: Any, code: int = 200, ctype: str = "application/json"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/console", "/index.html"):
                self._send(files("pythia_consumer").joinpath("console.html").read_bytes(),
                           ctype="text/html; charset=utf-8")
            elif self.path == "/api/status":
                self._send(census.node_status(api_url=api_url))
            elif self.path == "/api/intelligence":
                self._send(intelligence_status())
            else:
                self._send({"error": "not found"}, 404)

        def do_POST(self):  # noqa: N802
            if self.path != "/api/verify":
                return self._send({"error": "not found"}, 404)
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if not 0 < length <= _MAX_BODY:
                    return self._send({"error": "body required (max 1 MiB)"}, 400)
                receipt = json.loads(self.rfile.read(length))
            except (ValueError, json.JSONDecodeError):
                return self._send({"error": "invalid JSON receipt"}, 400)
            self._send(verify.verify_receipt(receipt))

        def log_message(self, *_):  # quiet console
            pass

    return Handler


def serve(port: int = 8777, api_url: Optional[str] = None) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(api_url))
    print(f"PYTHIA console → http://127.0.0.1:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
