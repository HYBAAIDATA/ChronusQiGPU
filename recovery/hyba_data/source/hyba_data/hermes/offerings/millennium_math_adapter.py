"""Client for the configured Millennium Maths API.

Only mathematical workloads are sent to this API. Mission evidence, identity,
credentials, classified data, and operational topology are never forwarded here.
The API's finite probes are exploratory evidence, not proofs of open conjectures.
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class MillenniumMathsAPI:
    """Small allow-listed client for the repository's Millennium API service."""

    ENDPOINTS = {
        "aggregate": "/millennium/aggregate",
        "hodge_topology": "/millennium/hodge/analyze_topology",
        "yang_mills_gap": "/millennium/yang_mills/gap",
        "riemann_primes": "/millennium/riemann/predict_primes",
        "p_vs_np": "/millennium/p_vs_np/analyze",
        "navier_stokes": "/millennium/navier_stokes/predict_flow",
        "bsd": "/millennium/bsd/rank",
        "poincare": "/millennium/poincare/flow",
    }

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_token: str | None = None,
        timeout_seconds: float = 5.0,
        max_response_bytes: int = 1_000_000,
    ) -> None:
        self.base_url = (base_url or os.environ.get("MILLENNIUM_API_BASE_URL", "")).rstrip("/")
        self.api_token = api_token or os.environ.get("MILLENNIUM_API_TOKEN")
        self.timeout_seconds = max(0.5, min(float(timeout_seconds), 15.0))
        self.max_response_bytes = max(1024, min(int(max_response_bytes), 2_000_000))

    def available(self) -> bool:
        """Configured endpoint only; this does not assert network health."""
        if not self.base_url:
            return False
        parsed = urlparse(self.base_url)
        return parsed.scheme == "https" or (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        )

    def run(self, operation: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run one allow-listed, bounded mathematical API operation."""
        if operation not in self.ENDPOINTS:
            return self._unavailable("unsupported_operation", f"Unsupported operation: {operation}")
        if not self.available():
            return self._unavailable(
                "api_not_configured",
                "Set MILLENNIUM_API_BASE_URL to the trusted Millennium service URL (HTTPS, or local HTTP).",
            )
        body = dict(payload or {})
        if len(json.dumps(body, default=str).encode("utf-8")) > 64_000:
            return self._unavailable("request_too_large", "Mathematical API payload exceeds 64 KB.")
        body.setdefault("scale", "quick")
        raw = json.dumps(body, sort_keys=True).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        request = Request(
            self.base_url + self.ENDPOINTS[operation],
            data=raw,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_raw = response.read(self.max_response_bytes + 1)
                if len(response_raw) > self.max_response_bytes:
                    return self._unavailable("response_too_large", "Millennium API response exceeded configured limit.")
                decoded = json.loads(response_raw.decode("utf-8"))
                if not isinstance(decoded, dict):
                    return self._unavailable("invalid_response", "Millennium API returned a non-object response.")
                # The service's own claim boundary is preserved; absent metadata
                # defaults to not verified, never to a proof claim.
                return {
                    "status": "available",
                    "operation": operation,
                    "evidence": decoded,
                    "proof_claim": bool(decoded.get("proof_claim", False)),
                    "evidence_class": decoded.get("evidence_class", "UNSPECIFIED"),
                    "scope": decoded.get("scope", "UNSPECIFIED"),
                }
        except HTTPError as exc:
            return self._unavailable("http_error", f"Millennium API HTTP status {exc.code}.")
        except (URLError, TimeoutError, OSError) as exc:
            return self._unavailable("connection_error", f"Millennium API request failed: {type(exc).__name__}.")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._unavailable("invalid_response", "Millennium API did not return valid JSON.")

    @staticmethod
    def _unavailable(code: str, reason: str) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "proof_claim": False,
            "error": {"code": code, "reason": reason},
        }
