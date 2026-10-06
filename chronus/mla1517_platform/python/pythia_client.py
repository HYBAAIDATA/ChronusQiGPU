"""Typed client for the PYTHIA production control API (service
constitution §31).

One module, one envelope contract:

* correlation — callers pass a ``correlation_id``/``causation_id`` (or let
  the client mint one); ids propagate as ``X-Request-Id`` /
  ``X-Correlation-Id`` / ``X-Causation-Id`` and the response envelope is
  returned alongside the body.
* failure taxonomy — a non-2xx response whose body declares
  ``failure_class`` raises :class:`PythiaError` carrying that class from
  ``failure_taxonomy``; an undecorated error body raises ``INTERNAL_ERROR``
  rather than pretending the taxonomy didn't apply.
* idempotency — mutating calls take an ``idempotency_key``; the server
  replays the recorded outcome inside its retention window and marks the
  body ``idempotent_replay``.

No third-party dependency: urllib only.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import failure_taxonomy


class PythiaError(RuntimeError):
    """A typed control-API failure — the wire's failure_class, surfaced."""

    def __init__(self, failure_class: str, status: int, body: Any):
        self.failure_class = failure_class
        self.status = status
        self.body = body
        detail = ""
        if isinstance(body, dict):
            detail = body.get("error") or body.get("reason") or ""
        super().__init__(
            f"{failure_class} (HTTP {status}){': ' + detail if detail else ''}"
        )


@dataclass
class PythiaResponse:
    status: int
    body: Any
    request_id: str
    correlation_id: str
    causation_id: str


class PythiaClient:
    """Minimal typed control-API client."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = dict(headers or {})
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        *,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> PythiaResponse:
        rid = request_id or uuid.uuid4().hex
        headers = {
            "Accept": "application/json",
            "X-Request-Id": rid,
            "X-Correlation-Id": correlation_id or rid,
            **self.headers,
        }
        if causation_id:
            headers["X-Causation-Id"] = causation_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            self.base_url + path, data=data, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(
                req, timeout=timeout or self.timeout
            ) as resp:
                status = resp.status
                raw = resp.read()
                response_headers = resp.headers
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()
            response_headers = exc.headers

        parsed: Any = None
        if "application/json" in (response_headers.get("Content-Type") or ""):
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                parsed = None
        if status >= 400:
            failure_class = (
                parsed.get("failure_class")
                if isinstance(parsed, dict)
                else None
            ) or failure_taxonomy.class_for_status(status).value
            raise PythiaError(failure_class, status, parsed)
        return PythiaResponse(
            status=status,
            body=parsed,
            request_id=response_headers.get("X-Request-Id", ""),
            correlation_id=response_headers.get("X-Correlation-Id", ""),
            causation_id=response_headers.get("X-Causation-Id", ""),
        )

    # -- canonical surface -------------------------------------------------

    def health(self) -> PythiaResponse:
        return self.request("GET", "/api/v1/healthz")

    def readiness(self) -> PythiaResponse:
        return self.request("GET", "/api/v1/readyz")

    def status(self) -> PythiaResponse:
        return self.request("GET", "/api/v1/mla1517/status")

    def config(self) -> PythiaResponse:
        return self.request("GET", "/api/v1/config")

    def update_config(
        self, update: dict, *, idempotency_key: Optional[str] = None
    ) -> PythiaResponse:
        return self.request(
            "PUT", "/api/v1/config", update, idempotency_key=idempotency_key
        )

    def stratum_status(self) -> PythiaResponse:
        return self.request("GET", "/api/v1/stratum/status")

    def mining_evidence(self) -> PythiaResponse:
        return self.request("GET", "/api/v1/mining/evidence")

    def ready_to_mine(self) -> PythiaResponse:
        return self.request("GET", "/api/v1/ready-to-mine")

    def audit_tail(self, limit: int = 50) -> PythiaResponse:
        return self.request("GET", f"/api/v1/audit/tail?n={int(limit)}")
