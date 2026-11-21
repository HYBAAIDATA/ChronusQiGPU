# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Authenticated HTTP transport between coordinator, workers and clients.

Standard library only (http.server, http.client, ssl), so a worker needs no
web framework. Every request and response is MACed (``chronus.fleet.auth``);
TLS wraps the connection when the coordinator is given a certificate.
"""

from __future__ import annotations

import http.client
import ipaddress
import os
import threading
import json
import logging
import socket
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from chronus.fleet.auth import DEFAULT_REPLAY_CAPACITY, FleetAuth, ReplayCache, tls_client_context, H_NODE
from chronus.fleet.canonical import canonical_json
from chronus.fleet.errors import AuthenticationError, TransportError
from chronus.fleet.native_transport import NATIVE_TRANSPORT_ENV, load_native_transport

logger = logging.getLogger(__name__)
DEFAULT_PORT = 8740
MAX_BODY_BYTES = 64 * 1024 * 1024

Handler = Callable[[str, str, str, Mapping[str, Any]], tuple[int, Mapping[str, Any]]]


def _loopback(host):
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class FleetHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64

    def __init__(
        self,
        address: tuple[str, int],
        handler: Handler,
        auth: FleetAuth,
        tls_context: ssl.SSLContext | None = None,
        max_body: int = MAX_BODY_BYTES,
        auth_resolver=None,
        connection_timeout: int = 15,
        max_connections: int = 64,
        replay_capacity: int = DEFAULT_REPLAY_CAPACITY,
    ) -> None:
        if tls_context is None and not _loopback(address[0]):
            raise TransportError("non-loopback fleet listeners require TLS")
        if type(connection_timeout) is not int or connection_timeout < 1 or type(max_connections) is not int or max_connections < 1:
            raise ValueError("connection budgets must be positive integers")
        self.auth_resolver = auth_resolver
        self.connection_timeout = connection_timeout
        self._connection_slots = threading.BoundedSemaphore(max_connections)
        self.fleet_handler = handler
        self.fleet_auth = auth
        self.replay = ReplayCache(replay_capacity)
        self.tls_context = tls_context
        self.max_body = max_body
        super().__init__(address, _RequestHandler)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(self.connection_timeout)
        return request, address

    def process_request(self, request, client_address):
        if not self._connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        # TLS wrapping detaches request's fd. A duplicate still refers to the
        # same TCP connection, so shutdown interrupts TLS handshake and reads.
        deadline_socket = None
        deadline = None
        try:
            deadline_socket = request.dup()
            def expire():
                try:
                    deadline_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            deadline = threading.Timer(self.connection_timeout, expire)
            deadline.daemon = True
            deadline.start()
            super().process_request_thread(request, client_address)
        finally:
            if deadline is not None:
                deadline.cancel()
            if deadline_socket is not None:
                deadline_socket.close()
            try:
                self.shutdown_request(request)
            finally:
                self._connection_slots.release()

    def finish_request(self, request: Any, client_address: Any) -> None:
        if self.tls_context is None:
            super().finish_request(request, client_address)
            return
        try:
            wrapped = self.tls_context.wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError) as exc:
            logger.info("TLS handshake from %s failed: %s", client_address, exc)
            return
        try:
            super().finish_request(wrapped, client_address)
        finally:
            try:
                wrapped.close()
            except OSError:
                pass


class _RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ChronusFleet/1"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature from base class
        logger.debug("%s %s", self.address_string(), format % args)

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        self._handle("POST")

    def _plain(self, status: int, message: str) -> None:
        self.close_connection = True
        body = canonical_json({"error": message})
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, method: str) -> None:
        server: FleetHTTPServer = self.server  # type: ignore[assignment]
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._plain(400, "bad Content-Length")
            return
        if length < 0 or length > server.max_body:
            self._plain(413, f"request body over {server.max_body} bytes")
            return
        body = self.rfile.read(length) if length else b""
        try:
            request_auth = (server.auth_resolver(self.path, self.headers.get(H_NODE))
                            if server.auth_resolver is not None else server.fleet_auth)
            if request_auth is None:
                raise AuthenticationError("unknown worker credential")
            node_id, nonce = request_auth.verify_request(method, self.path, self.headers, body, server.replay)
        except AuthenticationError as exc:
            logger.warning("rejected request from %s: %s", self.address_string(), exc)
            self._plain(401, "unauthenticated")
            return
        try:
            payload = json.loads(body) if body else {}
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            status, response = server.fleet_handler(method, self.path, node_id, payload)
        except (ValueError, KeyError, TypeError) as exc:
            status, response = 400, {"error": f"{type(exc).__name__}: {exc}"}
        except Exception:
            # Keep internals (exception text, paths) in the server log only.
            logger.exception("handler failed for %s %r", method, self.path.replace("\r", "").replace("\n", ""))
            status, response = 500, {"error": "internal error"}
        out = canonical_json(response)
        self.send_response(status)
        for name, value in request_auth.sign_response(nonce, status, out).items():
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class FleetClient:
    """Signs requests and refuses any response not MACed for that request."""

    def __init__(
        self,
        base_url: str,
        auth: FleetAuth,
        node_id: str,
        tls_ca: str | None = None,
        timeout: float = 60.0,
        max_response_bytes: int = MAX_BODY_BYTES,
    ) -> None:
        parts = urlsplit(base_url if "://" in base_url else "http://" + base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise TransportError(f"coordinator URL must be http(s)://host:port, not {base_url!r}")
        if parts.path not in ("", "/") or parts.query or parts.fragment or parts.username is not None:
            raise TransportError("coordinator URL must not contain a path, query, fragment or userinfo")
        if parts.scheme == 'http' and not _loopback(parts.hostname):
            raise TransportError("non-loopback fleet clients require HTTPS")
        if type(max_response_bytes) is not int or max_response_bytes < 1:
            raise ValueError("max_response_bytes must be a positive integer")
        self.max_response_bytes = max_response_bytes
        self.scheme = parts.scheme
        self.host = parts.hostname
        self.port = parts.port or DEFAULT_PORT
        authority = f"[{self.host}]" if ":" in self.host else self.host
        self.base_url = f"{self.scheme}://{authority}:{self.port}"
        self.auth = auth
        self.node_id = node_id
        self.timeout = timeout
        self._tls = tls_client_context(tls_ca) if self.scheme == "https" else None
        if tls_ca and self.scheme != "https":
            raise TransportError("a TLS CA was given but the coordinator URL is not https://")
        self._tls_ca = tls_ca
        native_library = os.environ.get(NATIVE_TRANSPORT_ENV)
        self._native = load_native_transport(native_library) if native_library else None

    def request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        body = canonical_json(dict(payload)) if payload is not None else b""
        headers = self.auth.sign_request(method, path, self.node_id, body)
        headers["Content-Type"] = "application/json"
        if self._native is not None:
            status, response_headers, data = self._native.request(
                self.base_url, method, path, headers, body, self._tls_ca, self.timeout, self.max_response_bytes)
        else:
            if self._tls is not None:
                conn: http.client.HTTPConnection = http.client.HTTPSConnection(
                    self.host, self.port, timeout=self.timeout, context=self._tls
                )
            else:
                conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
            try:
                conn.request(method, path, body=body, headers=headers)
                response = conn.getresponse()
                data = response.read(self.max_response_bytes + 1)
                if len(data) > self.max_response_bytes:
                    raise TransportError("coordinator response exceeds configured byte limit")
                status = response.status
                response_headers = response.headers
            except (OSError, http.client.HTTPException, socket.timeout) as exc:
                raise TransportError(f"cannot reach coordinator at {self.base_url}: {exc}") from exc
            finally:
                conn.close()
        if status == 401 and "X-Chronus-Fleet-MAC" not in response_headers:
            raise AuthenticationError("the coordinator rejected this fleet token")
        self.auth.verify_response(headers["X-Chronus-Fleet-Nonce"], status, response_headers, data)
        try:
            obj = json.loads(data) if data else {}
        except json.JSONDecodeError as exc:
            raise TransportError("coordinator sent a non-JSON response", status) from exc
        if status >= 400:
            raise TransportError(str(obj.get("error", f"HTTP {status}")), status)
        return obj

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, payload)
