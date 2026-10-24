"""Real EnterprisePlane + SQLite; labelled authorization/runtime test peers only.

This suite does not boot TURING, qualify OIDC, verify a signature provider, or
measure customer value. No fixture result is presented as canonical execution.
"""

import copy
import tempfile
import unittest
from types import SimpleNamespace

from hyba_turing_service.control import Conflict, Denied, Unavailable, digest
from hyba_turing_service.enterprise import EnterprisePlane


class TestAuthority:
    """Explicit signed-authority transport fixture; not production AL HARAS."""

    def verify(self, token, **kwargs):
        if token != "test-only":
            raise PermissionError("fixture denial")
        return SimpleNamespace(max_payload_bytes=65536)


class RuntimeEnvelopePeer:
    """Service-envelope fixture, never an assertion of canonical TURING execution."""

    def run(self, request):
        return dict(
            schema="turing.vqc.pipeline_report.v1",
            verdict="PASS",
            stages=[
                dict(stage="execution", state="PASS"),
                dict(stage="verification", state="PASS"),
            ],
            program_digest=digest(request),
            certificate={"fixture": True},
            witness={"fixture": True},
        )


class ActivationStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = [1000]
        self.dbpath = self.tmp.name + "/service.sqlite"
        self.open_plane()
        self.configure("tenant-a", "alice", "project-a")

    def tearDown(self):
        self.plane.close()
        self.tmp.cleanup()

    def open_plane(self):
        self.plane = EnterprisePlane(
            self.dbpath,
            customer_authority=TestAuthority(),
            operator_authority=TestAuthority(),
            clock=lambda: self.now[0],
            capacity_slots=4,
        )

    def configure(self, tenant, member, project):
        p = self.plane
        terms = dict(
            tenant=tenant,
            billing_account="metadata-only",
            contract=tenant + "-contract",
            starts=900,
            expires=2000,
            contracted=2,
            allowance=10,
        )
        p.register_approval(
            "test-only",
            "approver",
            approval=tenant + "-approval",
            tenant=tenant,
            contract=terms["contract"],
            terms_hash=digest(terms),
            expires=1900,
        )
        p.approve_customer(
            "test-only",
            "operator",
            **terms,
            approval=tenant + "-approval",
            command=tenant + "-approve"
        )
        p.provision("test-only", "operator", tenant=tenant, slots=2, command=tenant + "-reserve")
        p.set_member(
            "test-only", "operator", tenant=tenant, member=member, role="admin", operator=True
        )
        p.set_project(
            "test-only",
            member,
            tenant=tenant,
            project=project,
            slots=1,
            allowance=3,
            members=[member],
        )

    def status(self, **kwargs):
        return self.plane.activation_status(
            "test-only", "alice", tenant="tenant-a", project="project-a", **kwargs
        )

    def submit(self, job="job-1"):
        return self.plane.submit_project(
            "test-only",
            "alice",
            tenant="tenant-a",
            project="project-a",
            job=job,
            request={"qasm": "fixture request, not executable QASM"},
        )

    def execute(self):
        return self.plane.execute(
            "test-only", "worker", tenant="tenant-a", job="job-1", runtime=RuntimeEnvelopePeer()
        )

    def test_ready_does_not_claim_runtime_or_value(self):
        s = self.status()
        self.assertEqual(s["state"], "ready_to_submit")
        self.assertTrue(s["ready_to_submit"])
        self.assertEqual(s["runtime_health"], "not_probed")
        self.assertEqual(s["business_value"], "not_established")
        self.assertEqual(s["customer_acceptance"], "not_recorded")
        self.assertEqual(s["signature_status"], "not_assessed")

    def test_snapshot_digest_is_reproducible(self):
        a, b = self.status(), self.status()
        self.assertEqual(a, b)
        checksum = a.pop("snapshot_digest")
        self.assertEqual(checksum, digest(a))

    def test_snapshot_has_no_business_mutation(self):
        before = list(self.plane.db.iterdump())
        self.status()
        self.assertEqual(before, list(self.plane.db.iterdump()))

    def test_denied_authority(self):
        with self.assertRaises(Denied):
            self.plane.activation_status("bad", "alice", tenant="tenant-a", project="project-a")

    def test_missing_authority(self):
        self.plane.customer_authority = None
        with self.assertRaises(Unavailable):
            self.status()

    def test_revoked_member(self):
        self.plane.set_member(
            "test-only",
            "operator",
            tenant="tenant-a",
            member="alice",
            role="admin",
            active=False,
            operator=True,
        )
        with self.assertRaises(Denied):
            self.status()

    def test_cross_tenant_denied(self):
        self.configure("tenant-b", "bob", "project-b")
        with self.assertRaises(Denied):
            self.plane.activation_status(
                "test-only", "alice", tenant="tenant-b", project="project-b"
            )

    def test_project_membership_enforced(self):
        self.plane.set_member(
            "test-only",
            "operator",
            tenant="tenant-a",
            member="reader",
            role="analyst",
            operator=True,
        )
        with self.assertRaises(Denied):
            self.plane.activation_status(
                "test-only", "reader", tenant="tenant-a", project="project-a"
            )

    def test_viewer_cannot_be_reported_ready_to_submit(self):
        self.plane.set_member(
            "test-only", "operator", tenant="tenant-a", member="alice", role="viewer", operator=True
        )
        with self.assertRaises(Denied):
            self.status()

    def test_suspended_is_blocked(self):
        self.plane.lifecycle(
            "test-only",
            "operator",
            tenant="tenant-a",
            state="suspended",
            reason="test",
            command="suspend",
        )
        self.assertIn("contract_not_active", self.status()["blockers"])

    def test_contract_expiry_boundary(self):
        self.now[0] = 2000
        self.assertIn("outside_contract_window", self.status()["blockers"])

    def test_future_contract_is_blocked(self):
        self.now[0] = 899
        self.assertIn("outside_contract_window", self.status()["blockers"])

    def test_queued_is_not_completed_and_capacity_is_busy(self):
        self.submit()
        s = self.status(job="job-1")
        self.assertEqual(s["state"], "queued")
        self.assertIsNone(s["outcome"]["completion_fact"])
        self.assertIn("project_capacity_exhausted", s["blockers"])

    def test_completed_fixture_envelope_has_bound_fact_not_value(self):
        self.submit()
        self.execute()
        s = self.status(job="job-1")
        fact = s["outcome"]["completion_fact"]
        self.assertEqual(s["state"], "result_available")
        self.assertEqual(fact["evidence_class"], "service_accepted_runtime_envelope")
        self.assertEqual(s["business_value"], "not_established")
        self.assertNotIn("certificate", str(s))

    def test_failed_envelope_is_not_result_available(self):
        class FailedPeer:
            def run(self, request):
                return {"verdict": "FAIL"}

        self.submit()
        self.plane.execute(
            "test-only", "worker", tenant="tenant-a", job="job-1", runtime=FailedPeer()
        )
        self.assertEqual(self.status(job="job-1")["state"], "execution_failed")

    def test_ambiguous_failure_requires_reconciliation(self):
        class CrashedPeer:
            def run(self, request):
                raise RuntimeError("fixture crash")

        self.submit()
        with self.assertRaises(Unavailable):
            self.plane.execute(
                "test-only", "worker", tenant="tenant-a", job="job-1", runtime=CrashedPeer()
            )
        self.assertEqual(self.status(job="job-1")["state"], "reconciliation_required")

    def test_cancelled_is_not_completed(self):
        self.submit()
        self.plane.request_cancel("test-only", "alice", tenant="tenant-a", job="job-1")
        self.assertEqual(self.status(job="job-1")["state"], "cancelled")

    def test_missing_job_denied(self):
        with self.assertRaises(Denied):
            self.status(job="missing")

    def test_wrong_project_job_denied(self):
        self.submit()
        self.plane.set_project(
            "test-only",
            "alice",
            tenant="tenant-a",
            project="other",
            slots=1,
            allowance=3,
            members=["alice"],
        )
        with self.assertRaises(Denied):
            self.plane.activation_status(
                "test-only", "alice", tenant="tenant-a", project="other", job="job-1"
            )

    def test_allowance_exhaustion(self):
        for i in range(3):
            self.submit("job-" + str(i))
            self.plane.execute(
                "test-only",
                "worker",
                tenant="tenant-a",
                job="job-" + str(i),
                runtime=RuntimeEnvelopePeer(),
            )
        self.assertIn("project_allowance_exhausted", self.status()["blockers"])

    def test_corrupt_report_fails_closed(self):
        self.submit()
        self.execute()
        self.plane.db.execute("UPDATE jobs SET report='{}' WHERE tenant='tenant-a' AND job='job-1'")
        with self.assertRaises(Conflict):
            self.status(job="job-1")

    def test_restart_preserves_view(self):
        self.submit()
        self.execute()
        before = copy.deepcopy(self.status(job="job-1"))
        self.plane.close()
        self.open_plane()
        self.assertEqual(before, self.status(job="job-1"))

    def test_old_contract_job_not_promoted_after_renewal(self):
        self.submit()
        self.execute()
        terms = dict(
            tenant="tenant-a",
            billing_account="metadata-only",
            contract="renewal",
            starts=1000,
            expires=3000,
            contracted=2,
            allowance=10,
        )
        self.plane.register_approval(
            "test-only",
            "approver",
            approval="renewal",
            tenant="tenant-a",
            contract="renewal",
            terms_hash=digest(terms),
            expires=1900,
        )
        self.plane.renew(
            "test-only",
            "operator",
            tenant="tenant-a",
            contract="renewal",
            approval="renewal",
            starts=1000,
            expires=3000,
            allowance=10,
            command="renewal",
        )
        with self.assertRaises(Denied):
            self.status(job="job-1")

    def test_financial_authority_not_acquired_by_read(self):
        self.plane.require_spend = True
        self.assertIn("per_job_spend_authorization_required", self.status()["blockers"])


if __name__ == "__main__":
    unittest.main()
