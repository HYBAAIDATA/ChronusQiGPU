"""Actual FastAPI app + real EnterprisePlane/SQLite; labelled identity/runtime peers."""

import unittest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from hyba_turing_service.api import Dependencies, create_app
from hyba_turing_service.control import Denied
from hyba_turing_service.enterprise import EnterprisePlane
import test_activation_status as fixture


class IdentityPeer:
    def verify(self, token):
        if token not in {"alice", "bob"}:
            raise Denied("identity fixture denial")
        return SimpleNamespace(subject=token)


class IssuerPeer:
    issuer = "test-only-issuer"

    def issue(self, claims):
        return "test-only"


class ActivationApiTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ActivationStatusTests()
        self.f.setUp()

        def factory():
            return EnterprisePlane(
                self.f.dbpath,
                customer_authority=fixture.TestAuthority(),
                operator_authority=fixture.TestAuthority(),
                clock=lambda: self.f.now[0],
                capacity_slots=4,
            )

        self.app = create_app(
            Dependencies(
                plane_factory=factory,
                identity_verifier=IdentityPeer(),
                customer_issuer=IssuerPeer(),
                operator_issuer=IssuerPeer(),
                claims_factory=lambda **kwargs: SimpleNamespace(**kwargs),
                key_id="test",
                operator_subjects=frozenset(),
                approver_subjects=frozenset(),
                origin="https://service.example.invalid",
            )
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.f.tearDown()

    def get(self, path="/api/customer/tenant-a/activation-status?project=project-a", actor="alice"):
        return self.client.get(path, headers={"Authorization": "Bearer " + actor})

    def test_route_calls_real_plane(self):
        r = self.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["schema"], "turing.activation-status.v1")
        self.assertEqual(r.json()["state"], "ready_to_submit")
        self.assertEqual(r.headers["cache-control"], "no-store")

    def test_route_missing_project_is_validation_error(self):
        self.assertEqual(self.get("/api/customer/tenant-a/activation-status").status_code, 422)

    def test_route_identity_denial(self):
        self.assertEqual(self.get(actor="invalid").status_code, 403)

    def test_route_cross_tenant_denied(self):
        self.f.configure("tenant-b", "bob", "project-b")
        self.assertEqual(
            self.get("/api/customer/tenant-b/activation-status?project=project-b").status_code, 403
        )

    def test_route_revocation_rechecked(self):
        self.assertEqual(self.get().status_code, 200)
        self.f.plane.set_member(
            "test-only",
            "operator",
            tenant="tenant-a",
            member="alice",
            role="admin",
            active=False,
            operator=True,
        )
        self.assertEqual(self.get().status_code, 403)

    def test_route_reads_completed_fixture_not_computes(self):
        self.f.submit()
        self.f.execute()
        r = self.get("/api/customer/tenant-a/activation-status?project=project-a&job=job-1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["state"], "result_available")
        self.assertEqual(r.json()["business_value"], "not_established")

    def test_route_corruption_returns_conflict(self):
        self.f.submit()
        self.f.execute()
        self.f.plane.db.execute("UPDATE jobs SET report='{}'")
        r = self.get("/api/customer/tenant-a/activation-status?project=project-a&job=job-1")
        self.assertEqual(r.status_code, 409)

    def test_route_never_provisions_or_submits(self):
        self.get()
        self.assertEqual(self.f.plane.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)
        self.assertEqual(self.f.plane.db.execute("SELECT COUNT(*) FROM commands").fetchone()[0], 2)

    def test_openapi_includes_route(self):
        route = self.app.openapi()["paths"]["/api/customer/{tenant}/activation-status"]["get"]
        self.assertIn("project", [p["name"] for p in route["parameters"]])


if __name__ == "__main__":
    unittest.main()
