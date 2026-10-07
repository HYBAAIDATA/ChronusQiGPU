"""Tests for the CIaaS API service layer.

Tests the HTTP adapter, auth, rate limiting, and payload validation
without requiring a live HTTP server (except for one smoke test).
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from typing import Any
from unittest.mock import MagicMock

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from toe.runtime import (
    RuntimeResponse,
    TenantContext,
    TOEIntelligenceRuntime,
    TOEIntelligenceRuntimeConfig,
    RuntimeErrorInfo,
)
from toe.ciaas_api import (
    CIaaSService,
    CIaaSHTTPHandler,
    RateLimiter,
    default_config,
)
from toe.runtime import RuntimeReceipt


class FakeBridge:
    """Minimal stand-in for TOEBridge."""

    def available(self) -> bool:
        return True

    def status(self) -> dict[str, Any]:
        return {"engine": "ok"}

    def predict(self, data: Any) -> dict[str, Any]:
        return {
            "available": True,
            "confidence": 0.9,
            "state_tomography": {"energy": 0.5},
        }

    def explain_causality(self, data: Any) -> dict[str, Any]:
        return {"available": True, "key_factors": [["a", 0.9]]}

    def predict_trajectory(self, data: Any) -> dict[str, Any]:
        return {"available": True, "trend": "rising"}

    def causal_ladder(self, data: Any) -> dict[str, Any]:
        return {"available": True, "rung_1": {}, "rung_2": {}}


def make_runtime() -> TOEIntelligenceRuntime:
    """Create a runtime with fakes for testing."""
    return TOEIntelligenceRuntime(
        bridge=FakeBridge(),
        feedback_core=None,
        evidence_chain=None,
        asi=None,
        platform=None,
        config=TOEIntelligenceRuntimeConfig(
            enable_feedback=False,
            enable_evidence=False,
            enable_asi=False,
            enable_platform=False,
        ),
    )


def make_service(api_key: str | None = None) -> CIaaSService:
    """Create a CIaaS service with optional auth."""
    return CIaaSService(
        runtime=make_runtime(),
        api_key=api_key,
        rate_limiter=RateLimiter(max_requests=10, window_seconds=60),
    )


class TestRateLimiter(unittest.TestCase):
    """Tests for the in-memory rate limiter."""

    def test_allows_within_limit(self) -> None:
        rl = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            self.assertTrue(rl.check("tenant-a"))

    def test_blocks_over_limit(self) -> None:
        rl = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            self.assertTrue(rl.check("tenant-a"))
        self.assertFalse(rl.check("tenant-a"))

    def test_separate_tenants(self) -> None:
        rl = RateLimiter(max_requests=2, window_seconds=60)
        self.assertTrue(rl.check("tenant-a"))
        self.assertTrue(rl.check("tenant-a"))
        self.assertTrue(rl.check("tenant-b"))
        self.assertFalse(rl.check("tenant-a"))

    def test_remaining(self) -> None:
        rl = RateLimiter(max_requests=10, window_seconds=60)
        rl.check("tenant-a")
        rl.check("tenant-a")
        self.assertEqual(rl.remaining("tenant-a"), 8)


class TestCIaaSServiceAuth(unittest.TestCase):
    """Tests for auth and tenant validation."""

    def test_no_key_required_when_auth_disabled(self) -> None:
        """When no API key is configured, auth is disabled (dev mode)."""
        service = make_service()
        response, status = service.handle_request(
            "predict", {"a": [1.0]}, "tenant-a"
        )
        self.assertEqual(status, 200)
        self.assertTrue(response.ok)

    def test_short_key_rejected_at_init(self) -> None:
        """API key shorter than 32 chars should be rejected."""
        with self.assertRaises(ValueError):
            CIaaSService(runtime=make_runtime(), api_key="short")

    def test_valid_key_accepted(self) -> None:
        """Valid API key should pass auth."""
        key = "x" * 32
        service = make_service(key)
        response, status = service.handle_request(
            "predict", {"a": [1.0]}, "tenant-a", api_key=key
        )
        self.assertEqual(status, 200)
        self.assertTrue(response.ok)

    def test_missing_key_when_auth_enabled(self) -> None:
        """Missing key should fail-closed when auth is enabled."""
        key = "x" * 32
        service = make_service(key)
        response, status = service.handle_request(
            "predict", {"a": [1.0]}, "tenant-a", api_key=None
        )
        self.assertEqual(status, 401)
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, "unauthorized")

    def test_wrong_key_rejected(self) -> None:
        """Wrong key should fail-closed."""
        key = "x" * 32
        wrong = "y" * 32
        service = make_service(key)
        response, status = service.handle_request(
            "predict", {"a": [1.0]}, "tenant-a", api_key=wrong
        )
        self.assertEqual(status, 401)


class TestCIaaSServiceOperations(unittest.TestCase):
    """Tests for the CIaaS service operations."""

    def setUp(self) -> None:
        self.service = make_service()

    def test_predict_operation(self) -> None:
        response, status = self.service.handle_request(
            "predict", {"a": [1.0, 2.0]}, "tenant-a"
        )
        self.assertEqual(status, 200)
        self.assertTrue(response.ok)
        self.assertEqual(response.operation, "predict")
        self.assertIsNotNone(response.receipt)

    def test_explain_operation(self) -> None:
        response, status = self.service.handle_request(
            "explain", {"a": [1.0]}, "tenant-a"
        )
        self.assertEqual(status, 200)
        self.assertTrue(response.ok)

    def test_forecast_operation(self) -> None:
        response, status = self.service.handle_request(
            "forecast", {"a": [1.0]}, "tenant-a"
        )
        self.assertEqual(status, 200)
        self.assertTrue(response.ok)

    def test_causal_operation(self) -> None:
        response, status = self.service.handle_request(
            "causal", {"a": [1.0]}, "tenant-a",
            metadata={"intervention_node": "x"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(response.ok)

    def test_feedback_operation(self) -> None:
        """Feedback operation should handle missing decision gracefully."""
        response, status = self.service.handle_request(
            "feedback", True, "tenant-a",
            metadata={"decision_id": "nonexistent"}
        )
        # Should fail gracefully since feedback is disabled
        self.assertEqual(status, 422)
        self.assertFalse(response.ok)

    def test_unknown_operation(self) -> None:
        response, status = self.service.handle_request(
            "unknown", {"a": [1.0]}, "tenant-a"
        )
        self.assertEqual(status, 400)


class TestCIaaSHealth(unittest.TestCase):
    """Tests for health and readiness endpoints."""

    def test_health(self) -> None:
        service = make_service()
        health = service.handle_health()
        self.assertIn("status", health)
        self.assertIn("engine_available", health)

    def test_ready(self) -> None:
        service = make_service()
        ready = service.handle_ready()
        self.assertIn("ready", ready)
        self.assertIn("production_ready", ready)
        self.assertFalse(ready["production_ready"])

    def test_metrics(self) -> None:
        service = make_service()
        service.handle_request("predict", {"a": [1.0]}, "tenant-a")
        metrics = service.handle_metrics()
        self.assertIn("ciaas_requests_total", metrics)
        self.assertIn("ciaas_engine_available", metrics)


class TestCIaaSMetrics(unittest.TestCase):
    """Tests for metrics counting."""

    def test_request_counted(self) -> None:
        service = make_service()
        service.handle_request("predict", {"a": [1.0]}, "tenant-a")
        metrics = service.handle_metrics()
        self.assertIn("1", metrics)

    def test_error_counted(self) -> None:
        service = make_service()
        service.handle_request("unknown_op", {}, "tenant-a")
        metrics = service.handle_metrics()
        self.assertIn("ciaas_errors_total", metrics)


class TestCIaaSTenantManagement(unittest.TestCase):
    """Tests for tenant registration."""

    def test_register_tenant(self) -> None:
        service = make_service()
        ctx = service.register_tenant("acme", mode="mining")
        self.assertEqual(ctx.tenant_id, "acme")
        self.assertEqual(ctx.mode, "mining")

    def test_auto_register_tenant(self) -> None:
        service = make_service()
        ctx = service.get_tenant("new-tenant")
        self.assertEqual(ctx.tenant_id, "new-tenant")
        self.assertEqual(ctx.mode, "standard")


if __name__ == "__main__":
    unittest.main()
