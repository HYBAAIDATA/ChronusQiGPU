# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Local status page for HYBA Mine, with the pool switch.

Served by the miner on 127.0.0.1 only (default port 8765). Every value on the
page is computed from the ledger by ``hyba_mine.status``. The pool switch
writes the same control request as ``hyba-mine pool use``; the running miner
applies it between work units and records the outcome. A POST must carry the
per-start token embedded in the page and a loopback Host header, so another
web page cannot drive the switch.
"""

from __future__ import annotations

import hmac
import html
import json
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs

from hyba_mine.control import load_state, request_pool_switch
from hyba_mine.ledger import Ledger
from hyba_mine.paths import Layout, write_private_file
from hyba_mine.pools import POOL_CATALOG
from hyba_mine.status import render_text, summarize

DEFAULT_PORT = 8765

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>HYBA Mine - local status</title>
<style>
body{{font-family:-apple-system,"IBM Plex Sans",Helvetica,Arial,sans-serif;background:#f8f6f1;color:#002147;margin:2rem;max-width:72rem}}
h1{{font-weight:600;font-size:1.4rem;margin:0 0 .25rem}} p.note{{color:#4a6c8c;margin:0 0 1.25rem}}
pre{{background:#fff;border-top:1px solid #002147;border-bottom:1px solid #002147;padding:1rem;overflow:auto;font-family:"IBM Plex Mono",Menlo,monospace;font-size:.9rem}}
form{{margin-top:1rem}} label{{margin-right:.5rem}} select,button{{font-size:1rem;padding:.25rem .5rem}}
</style></head><body>
<h1>HYBA Mine (internal treasury mining; not a product)</h1>
<p class="note">Every value below is read from the local ledger. Shares count as accepted or rejected only when the pool replied.</p>
<pre id="status">{status}</pre>
<form method="post" action="/pool">
<input type="hidden" name="token" value="{token}">
<label for="pool">Switch pool</label>
<select id="pool" name="pool">{options}</select>
<button type="submit">Switch</button>
</form>
<script>
let lastStatus = document.getElementById('status').textContent;
setInterval(async () => {{
  try {{
    const response = await fetch('/status.json');
    if (!response.ok) throw new Error('Status unavailable');
    lastStatus = JSON.stringify(await response.json(), null, 2);
    document.getElementById('status').textContent = lastStatus;
  }} catch (_) {{
    document.getElementById('status').textContent = 'Status unavailable. Last values are stale:\\n' + lastStatus;
  }}
}}, 5000);
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    server_version = "HYBA-Mine-Console"

    def log_message(self, fmt, *args):  # noqa: D401 - silence default stderr logging
        return

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        return host in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - http.server API
        if not self._host_ok():
            self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
            return
        console = self.server.console
        summary = summarize(console.ledger.records())
        if self.path == "/status.json":
            self._send(HTTPStatus.OK, json.dumps(summary, indent=2).encode("utf-8"), "application/json")
            return
        if self.path != "/":
            self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
            return
        active = load_state(console.layout).get("active_pool")
        options = "".join(
            f'<option value="{pid}"{" selected" if pid == active else ""}>{html.escape(p.name)}</option>'
            for pid, p in POOL_CATALOG.items()
        )
        page = _PAGE.format(status=html.escape(render_text(summary)), token=console.token, options=options)
        self._send(HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self):  # noqa: N802 - http.server API
        console = self.server.console
        if not self._host_ok() or self.path != "/pool":
            self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
            return
        length = min(int(self.headers.get("Content-Length", "0") or 0), 4096)
        fields = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
        token = (fields.get("token") or [""])[0]
        pool_id = (fields.get("pool") or [""])[0]
        if not hmac.compare_digest(token, console.token):
            self._send(HTTPStatus.FORBIDDEN, b"invalid token", "text/plain")
            return
        if pool_id not in POOL_CATALOG:
            self._send(HTTPStatus.BAD_REQUEST, b"unknown pool", "text/plain")
            return
        request_pool_switch(console.layout, pool_id)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()


class ConsoleServer:
    def __init__(self, layout: Layout, ledger: Ledger, port: int = DEFAULT_PORT) -> None:
        self.layout = layout
        self.ledger = ledger
        self.token = secrets.token_urlsafe(24)
        self._server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        self._server.console = self
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self) -> "ConsoleServer":
        write_private_file(self.layout.console_token, (self.token + "\n").encode("ascii"))
        self._thread = threading.Thread(target=self._server.serve_forever, name="hyba-mine-console", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self.layout.console_token.exists():
            self.layout.console_token.unlink()
