"""CIaaS API — Computational Intelligence as a Service HTTP layer.

Framework-neutral service layer plus a stdlib ``http.server`` adapter.
Wraps :class:`toe.runtime.TOEIntelligenceRuntime` with tenant-scoped
endpoints, auth, rate limiting, and payload validation.

Endpoints
---------
    GET  /healthz                     — liveness
    GET  /readyz                      — readiness (engine available)
    POST /api/v1/ciaas/predict         — full TOE prediction
    POST /api/v1/ciaas/explain         — causal analysis
    POST /api/v1/ciaas/forecast         — trajectory prediction
    POST /api/v1/ciaas/causal           — causal ladder (do-calculus)
    POST /api/v1/ciaas/feedback         — record outcome
    POST /api/v1/ciaas/solve            — domain-neutral problem → reasoning episode
    POST /api/v1/ciaas/learn            — observed outcome → model revision
    GET  /metrics                      — Prometheus-style metrics

Auth
----
Every endpoint except ``/healthz`` requires:
    X-CIAAS-Tenant: <tenant_id>
    X-CIAAS-Key:    <api_key>  (>= 32 chars, timing-safe comparison)

Fail-closed: missing or short key → 401.  Unknown tenant → 403.

Rate Limiting
-------------
In-memory per-tenant token bucket.  Single-process only — document this
and replace with Redis or equivalent for multi-process deployments.

Production readiness: **false**.  This is the wiring layer; acceptance
gates G (tenant/API security) and H (production report) must pass before
production use.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from toe.runtime import (
    RuntimeResponse,
    TenantContext,
    TOEIntelligenceRuntime,
    TOEIntelligenceRuntimeConfig,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CIaaSService",
    "CIaaSHTTPHandler",
    "CIaaSServer",
    "RateLimiter",
    "default_config",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_API_KEY_LEN = 32
_MAX_BODY_BYTES = 1_000_000  # 1 MB
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 60  # per tenant per window


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


@dataclass
class RateLimiter:
    """In-memory per-tenant token-bucket rate limiter.

    Single-process only.  For multi-process deployments, replace with
    Redis or equivalent.
    """

    max_requests: int = _RATE_MAX_REQUESTS
    window_seconds: int = _RATE_WINDOW_SECONDS
    _buckets: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def check(self, tenant_id: str) -> bool:
        """Return True if the request is within the rate limit."""
        now = time.time()
        bucket = self._buckets[tenant_id]
        # Evict expired entries
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False
        bucket.append(now)
        return True

    def remaining(self, tenant_id: str) -> int:
        """Remaining requests in the current window."""
        now = time.time()
        bucket = self._buckets[tenant_id]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        return max(0, self.max_requests - len(bucket))


# ---------------------------------------------------------------------------
# CIaaS Service
# ---------------------------------------------------------------------------


class CIaaSService:
    """Framework-neutral service layer for Computational Intelligence as a Service.

    Wraps :class:`TOEIntelligenceRuntime` with tenant auth, rate limiting,
    and payload validation.  Can be used directly (programmatic) or wrapped
    by an HTTP adapter.
    """

    def __init__(
        self,
        runtime: Optional[TOEIntelligenceRuntime] = None,
        config: Optional[TOEIntelligenceRuntimeConfig] = None,
        api_key: Optional[str] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.runtime = runtime or TOEIntelligenceRuntime(config or TOEIntelligenceRuntimeConfig())
        self._api_key_hash: Optional[str] = None
        key = api_key or os.environ.get("CIAAS_API_KEY")
        if key:
            if len(key) < _MIN_API_KEY_LEN:
                raise ValueError(
                    f"CIAAS_API_KEY must be >= {_MIN_API_KEY_LEN} characters"
                )
            self._api_key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
        self.rate_limiter = rate_limiter or RateLimiter()
        self._tenants: dict[str, TenantContext] = {}

        # Metrics counters
        self._metrics: dict[str, int] = defaultdict(int)
        self._metrics["requests_total"] = 0
        self._metrics["errors_total"] = 0
        self._metrics["auth_failures"] = 0
        self._metrics["rate_limited"] = 0

        logger.info("[CIAAS] service initialised, auth=%s", "enabled" if self._api_key_hash else "disabled")

    # -- tenant management ------------------------------------------------

    def register_tenant(
        self,
        tenant_id: str,
        mode: str = "standard",
        allowed_claims: frozenset[str] | None = None,
    ) -> TenantContext:
        """Register a tenant context."""
        ctx = TenantContext(
            tenant_id=tenant_id,
            mode=mode,
            allowed_claims=allowed_claims or frozenset(),
        )
        self._tenants[tenant_id] = ctx
        return ctx

    def get_tenant(self, tenant_id: str) -> Optional[TenantContext]:
        """Look up a registered tenant, or create a default one."""
        if tenant_id in self._tenants:
            return self._tenants[tenant_id]
        # Auto-register in standard mode (fail-open for dev; production should
        # pre-register tenants)
        return self.register_tenant(tenant_id)

    # -- auth -------------------------------------------------------------

    def verify_key(self, provided_key: str) -> bool:
        """Timing-safe key comparison.  Fail-closed if no key configured."""
        if self._api_key_hash is None:
            return True  # auth disabled (dev/test mode)
        if not provided_key:
            return False
        provided_hash = hashlib.sha256(provided_key.encode("utf-8")).hexdigest()
        return hmac.compare_digest(provided_hash, self._api_key_hash)

    # -- request handling -------------------------------------------------

    def handle_request(
        self,
        operation: str,
        payload: Any,
        tenant_id: str,
        api_key: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> tuple[RuntimeResponse, int]:
        """Handle a CIaaS request: auth → rate limit → validate → execute.

        Returns (RuntimeResponse, http_status_code).
        """
        self._metrics["requests_total"] += 1

        # 1. Auth
        if self._api_key_hash is not None:
            if not api_key or not self.verify_key(api_key):
                self._metrics["auth_failures"] += 1
                return self._error_response(tenant_id, operation, "unauthorized", "Invalid or missing API key", 401), 401

        # 2. Tenant
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            return self._error_response(tenant_id, operation, "unknown_tenant", "Tenant not registered", 403), 403

        # 3. Rate limit
        if not self.rate_limiter.check(tenant_id):
            self._metrics["rate_limited"] += 1
            remaining = self.rate_limiter.remaining(tenant_id)
            return self._error_response(
                tenant_id,
                operation,
                "rate_limited",
                f"Rate limit exceeded. {remaining} requests remaining.",
                429,
            ), 429

        # 4. Execute via runtime
        if operation == "predict":
            response = self.runtime.predict(payload, tenant, metadata=metadata)
        elif operation == "explain":
            response = self.runtime.explain(payload, tenant, metadata=metadata)
        elif operation == "forecast":
            response = self.runtime.forecast(payload, tenant, metadata=metadata)
        elif operation == "causal":
            intervention_node = (metadata or {}).get("intervention_node")
            intervention_value = (metadata or {}).get("intervention_value")
            observed = (metadata or {}).get("observed")
            response = self.runtime.causal(
                payload,
                tenant,
                intervention_node=intervention_node,
                intervention_value=intervention_value,
                observed=observed,
                metadata=metadata,
            )
        elif operation == "feedback":
            decision_id = (metadata or {}).get("decision_id", "")
            outcome = payload
            response = self.runtime.record_outcome(decision_id, outcome, tenant, metadata=metadata)
        elif operation == "solve":
            domain = (metadata or {}).get("domain")
            response = self.runtime.solve(payload, tenant, domain=domain)
        elif operation == "learn":
            episode_sha256 = (metadata or {}).get("episode_sha256", "")
            response = self.runtime.learn(episode_sha256, payload, tenant)
        else:
            return self._error_response(tenant_id, operation, "unknown_operation", f"Unknown operation: {operation}", 400), 400

        if not response.ok:
            self._metrics["errors_total"] += 1

        status = 200 if response.ok else 422
        if response.error:
            code = response.error.code
            if code in ("unauthorized", "invalid_tenant"):
                status = 401
            elif code in ("payload_invalid", "payload_too_large", "unknown_operation"):
                status = 400
            elif code == "unknown_episode":
                status = 404
            elif code == "engine_unavailable":
                status = 503
            elif code == "consensus_boundary_violation":
                status = 403

        return response, status

    def handle_health(self) -> dict[str, Any]:
        """Health check response — mirrors ``TOEIntelligenceRuntime.health()``.

        ``health()`` is invoked (not just ``runtime.degraded`` read) so
        learned-state degradation — underperforming modules discovered by
        the outcome loop — reaches the HTTP surface without waiting for
        ``/metrics`` to compute it first.
        """
        health = self.runtime.health()
        healthy = health["engine_available"] and not health["degraded"]
        return {
            "status": "ok" if healthy else "degraded",
            "engine_available": health["engine_available"],
            "engine_status": health["engine_status"],
            "degraded": health["degraded"],
            "degradation_reasons": health["degradation_reasons"],
            "feedback_available": health["feedback_available"],
            "learned_module_performance": health["learned_module_performance"],
            "underperforming_modules": health["underperforming_modules"],
            "feedback_state": health["feedback_state"],
            "production_ready": health["production_ready"],
            "timestamp": health["timestamp"],
        }

    def handle_ready(self) -> dict[str, Any]:
        """Readiness check response."""
        ready = self.runtime.ready()
        return {
            "ready": ready,
            "engine_available": ready,
            "production_ready": self.runtime.config.production_ready,
            "timestamp": time.time(),
        }

    def handle_metrics(self) -> str:
        """Prometheus-style metrics output."""
        lines = ["# CIAAS metrics"]
        for key, value in sorted(self._metrics.items()):
            lines.append(f"ciaas_{key} {value}")
        # Add runtime health
        health = self.runtime.health()
        lines.append(f"ciaas_engine_available {1 if health['engine_available'] else 0}")
        lines.append(f"ciaas_degraded {1 if health['degraded'] else 0}")
        lines.append(f"ciaas_production_ready {1 if health['production_ready'] else 0}")
        for tenant_id in self._tenants:
            remaining = self.rate_limiter.remaining(tenant_id)
            lines.append(f'ciaas_rate_limit_remaining{{tenant="{tenant_id}"}} {remaining}')
        return "\n".join(lines) + "\n"

    # -- error helper -----------------------------------------------------

    def _error_response(
        self,
        tenant_id: str,
        operation: str,
        code: str,
        message: str,
        http_status: int = 422,
    ) -> RuntimeResponse:
        from toe.runtime import RuntimeErrorInfo

        return RuntimeResponse(
            ok=False,
            tenant_id=tenant_id,
            operation=operation,
            error=RuntimeErrorInfo(code=code, message=message),
            timestamp=time.time(),
        )


# ---------------------------------------------------------------------------
# HTTP adapter (stdlib http.server)
# ---------------------------------------------------------------------------


class CIaaSHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for CIaaS.

    Routes to a :class:`CIaaSService` instance stored on the server.
    """

    # Quieter logging
    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("[CIAAS-HTTP] " + format, *args)

    @property
    def service(self) -> CIaaSService:
        return self.server.ciaas_service  # type: ignore[attr-defined]

    def _read_body(self) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Read and parse the JSON body.  Returns (body, error)."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return None, None
        if content_length > _MAX_BODY_BYTES:
            return None, "Payload exceeds 1MB limit"
        raw = self.rfile.read(content_length)
        if not raw:
            return None, None
        try:
            body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return None, f"Invalid JSON: {exc}"
        if not isinstance(body, dict):
            return None, "Request body must be a JSON object"
        return body, None

    def _get_headers(self) -> dict[str, str]:
        return {k.lower(): v for k, v in self.headers.items()}

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-CIAAS-Version", "1.0")
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, status: int, code: str, message: str) -> None:
        self._send_json(status, {"ok": False, "error": {"code": code, "message": message}})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            self._send_json(200, {"ok": True, **self.service.handle_health()})
        elif path == "/readyz":
            ready = self.service.handle_ready()
            status = 200 if ready["ready"] else 503
            self._send_json(status, {"ok": ready["ready"], **ready})
        elif path == "/metrics":
            body = self.service.handle_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        else:
            self._send_error(404, "not_found", f"Unknown path: {path}")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        headers = self._get_headers()

        # Route mapping
        routes = {
            "/api/v1/ciaas/predict": "predict",
            "/api/v1/ciaas/explain": "explain",
            "/api/v1/ciaas/forecast": "forecast",
            "/api/v1/ciaas/causal": "causal",
            "/api/v1/ciaas/feedback": "feedback",
            "/api/v1/ciaas/solve": "solve",
            "/api/v1/ciaas/learn": "learn",
        }

        if path not in routes:
            self._send_error(404, "not_found", f"Unknown path: {path}")
            return

        operation = routes[path]

        # Auth
        tenant_id = headers.get("x-ciaas-tenant")
        api_key = headers.get("x-ciaas-key")

        if not tenant_id:
            self._send_error(401, "missing_tenant", "X-CIAAS-Tenant header required")
            return

        # Read body
        body, body_error = self._read_body()
        if body_error:
            self._send_error(400, "body_error", body_error)
            return

        # Extract payload and metadata
        payload = body.get("payload") or body.get("data") or body
        metadata = body.get("metadata") or {}

        # Handle operation
        response, status = self.service.handle_request(
            operation=operation,
            payload=payload,
            tenant_id=tenant_id,
            api_key=api_key,
            metadata=metadata,
        )

        self._send_json(status, response.as_dict())


class CIaaSServer(ThreadingHTTPServer):
    """HTTP server for CIaaS."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        service: Optional[CIaaSService] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__((host, port), CIaaSHTTPHandler, **kwargs)
        self.ciaas_service = service or CIaaSService()


def default_config() -> TOEIntelligenceRuntimeConfig:
    """Default runtime configuration for CIaaS."""
    return TOEIntelligenceRuntimeConfig(
        hilbert_dim=32,
        enable_feedback=True,
        enable_evidence=True,
        enable_asi=True,
        enable_platform=False,
        production_ready=False,
    )
