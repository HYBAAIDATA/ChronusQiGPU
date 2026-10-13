"""Tests for hardened composite-scoped idempotency in control_api."""
from __future__ import annotations

import sys
import unittest
from http import HTTPStatus
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PY_DIR = REPO_ROOT / "chronus" / "mla1517_platform" / "python"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

import control_api


class ScopedIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        control_api._IDEMPOTENCY_RECORDS.clear()

    def test_identical_request_returns_idempotent_replay(self) -> None:
        key = "idem-test-1"
        tenant = "tenant-a"
        actor = "actor-1"
        method = "POST"
        path = "/api/v1/mining/stop"
        body = {"reason": "maintenance"}

        # Request 1 begins and reserves
        comp_key, replay = control_api._idempotency_reserve(
            key, tenant, actor, method, path, body
        )
        self.assertIsNotNone(comp_key)
        self.assertIsNone(replay)

        # Request 1 completes and stores response
        control_api._idempotency_store(
            key,
            HTTPStatus.OK,
            {"ok": True, "stopped": True},
            composite_key=comp_key,
            body=body,
        )

        # Request 2 with same key, tenant, path, body receives replayed response
        comp_key2, replay2 = control_api._idempotency_reserve(
            key, tenant, actor, method, path, body
        )
        self.assertEqual(comp_key, comp_key2)
        self.assertIsNotNone(replay2)
        status, payload = replay2
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(payload["stopped"], True)

    def test_payload_mismatch_returns_409_conflict(self) -> None:
        key = "idem-test-conflict"
        tenant = "tenant-a"
        actor = "actor-1"
        method = "POST"
        path = "/api/v1/agentic/start"
        body_initial = {"count": 128}
        body_mutated = {"count": 256}

        comp_key, replay = control_api._idempotency_reserve(
            key, tenant, actor, method, path, body_initial
        )
        self.assertIsNone(replay)
        control_api._idempotency_store(
            key,
            HTTPStatus.OK,
            {"ok": True, "started": True},
            composite_key=comp_key,
            body=body_initial,
        )

        # Re-submitting the same key with mutated body produces Conflict
        comp_key2, conflict = control_api._idempotency_reserve(
            key, tenant, actor, method, path, body_mutated
        )
        self.assertEqual(comp_key, comp_key2)
        self.assertIsNotNone(conflict)
        status, payload = conflict
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(payload.get("failure_class"), "IDEMPOTENCY_CONFLICT")

    def test_cross_tenant_isolation(self) -> None:
        key = "shared-key-1"
        method = "POST"
        path = "/api/v1/mining/stop"
        body = {"reason": "test"}

        # Tenant A stores its response
        comp_a, replay_a = control_api._idempotency_reserve(
            key, "tenant-a", "actor-1", method, path, body
        )
        self.assertIsNone(replay_a)
        control_api._idempotency_store(
            key,
            HTTPStatus.OK,
            {"ok": True, "tenant": "A"},
            composite_key=comp_a,
            body=body,
        )

        # Tenant B with the same key must NOT receive Tenant A's cached response
        comp_b, replay_b = control_api._idempotency_reserve(
            key, "tenant-b", "actor-2", method, path, body
        )
        self.assertNotEqual(comp_a, comp_b)
        self.assertIsNone(replay_b)

    def test_cross_route_isolation(self) -> None:
        key = "shared-route-key"
        tenant = "tenant-a"
        actor = "actor-1"
        method = "POST"
        body = {}

        # Route A
        comp_a, _ = control_api._idempotency_reserve(
            key, tenant, actor, method, "/api/v1/agentic/stop", body
        )
        control_api._idempotency_store(
            key, HTTPStatus.OK, {"route": "agentic"}, composite_key=comp_a, body=body
        )

        # Route B with same key does not see Route A's response
        comp_b, replay_b = control_api._idempotency_reserve(
            key, tenant, actor, method, "/api/v1/campaign/stop", body
        )
        self.assertNotEqual(comp_a, comp_b)
        self.assertIsNone(replay_b)

    def test_in_flight_concurrent_reservation_blocks_duplicate(self) -> None:
        key = "in-flight-key"
        tenant = "tenant-a"
        actor = "actor-1"
        method = "POST"
        path = "/api/v1/agentic/start"
        body = {"count": 64}

        # First request reserves
        comp_key, replay1 = control_api._idempotency_reserve(
            key, tenant, actor, method, path, body
        )
        self.assertIsNone(replay1)

        # Concurrent second request while first is still in-flight
        comp_key2, conflict = control_api._idempotency_reserve(
            key, tenant, actor, method, path, body
        )
        self.assertEqual(comp_key, comp_key2)
        self.assertIsNotNone(conflict)
        status, payload = conflict
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(payload.get("failure_class"), "IDEMPOTENCY_IN_FLIGHT")

    def test_release_on_abort_allows_retry(self) -> None:
        key = "abort-key"
        tenant = "tenant-a"
        actor = "actor-1"
        method = "POST"
        path = "/api/v1/agentic/start"
        body = {"count": 64}

        comp_key, _ = control_api._idempotency_reserve(
            key, tenant, actor, method, path, body
        )
        # Abort the in-flight reservation (e.g. handler threw an exception)
        control_api._idempotency_release(comp_key)

        # Retry should now be admitted cleanly
        comp_key2, retry_result = control_api._idempotency_reserve(
            key, tenant, actor, method, path, body
        )
        self.assertIsNone(retry_result)


if __name__ == "__main__":
    unittest.main()
