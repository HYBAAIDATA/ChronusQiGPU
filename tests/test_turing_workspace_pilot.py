"""Pilot adapter/HTTP routing unit tests. Fake engine is explicit; not engine qualification."""
import ast
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from http import HTTPStatus
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "chronus/mla1517_platform/python"
sys.path.insert(0, str(PLATFORM))
import turing_workspace as workspace

BELL = {"n_qubits": 2, "operations": [{"gate": "h", "qubits": [0]}, {"gate": "cx", "qubits": [0, 1]}]}


class State(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FakeJob:
    def __init__(self, number):
        self.job_id = f"fixture-job-{number}"
        self.state = State.QUEUED
    def status(self):
        return self.state
    def cancel(self):
        if self.state == State.QUEUED:
            self.state = State.CANCELLED
            return True
        return False
    def result(self, timeout):
        assert timeout == 0
        return self
    def report(self):
        return {"fixture": True, "pipeline_report": {"verdict": "PASS"}}


class FakePipeline:
    def __init__(self):
        self.jobs = []
    def submit(self, program, *, idempotency_key):
        assert program == BELL
        assert len(idempotency_key) == 64
        job = FakeJob(len(self.jobs))
        self.jobs.append(job)
        return job
    def close(self):
        pass


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.engine = FakePipeline()
        self.w = workspace.Workspace(lambda: self.engine, lambda p: p)
    def call(self, body, tenant="tenant-a", actor="analyst"):
        return self.w.dispatch(tenant, actor, body)
    def submit(self, key="request-1", **kw):
        return self.call({"action": "submit", "program": BELL, "idempotency_key": key}, **kw)
    def test_capabilities_do_not_construct_engine(self):
        w = workspace.Workspace(lambda: self.fail("engine constructed for capabilities"))
        code, result = w.dispatch("a", "b", {"action": "capabilities"})
        self.assertEqual(code, 200)
        self.assertEqual(result["billing"], "not_integrated")
    def test_submission_and_success_return_unmodified_report(self):
        code, j = self.submit()
        self.assertEqual(code, 202)
        self.assertEqual(j["status"], "queued")
        self.engine.jobs[0].state = State.SUCCEEDED
        _, snapshot = self.call({"action": "status", "job_id": j["job_id"]})
        self.assertEqual(snapshot["report"], self.engine.jobs[0].report())
    def test_same_key_returns_same_job(self):
        _, first = self.submit()
        code, second = self.submit()
        self.assertEqual(code, 200)
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(len(self.engine.jobs), 1)
    def test_key_conflict_is_refused(self):
        self.submit()
        with self.assertRaises(workspace.WorkspaceError) as raised:
            self.call({"action": "submit", "program": {"n_qubits": 1, "operations": []}, "idempotency_key": "request-1"})
        self.assertEqual(raised.exception.status, 409)
    def test_concurrent_same_key_submits_once(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(lambda _: self.submit()[1]["job_id"], range(20)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(len(self.engine.jobs), 1)
    def test_cross_tenant_job_is_not_found(self):
        _, j = self.submit()
        for action in ("status", "cancel"):
            with self.assertRaises(workspace.WorkspaceError) as e:
                self.call({"action": action, "job_id": j["job_id"]}, tenant="tenant-b")
            self.assertEqual(e.exception.status, 404)
    def test_cross_actor_job_is_not_found(self):
        _, j = self.submit()
        with self.assertRaises(workspace.WorkspaceError) as e:
            self.call({"action": "status", "job_id": j["job_id"]}, actor="other")
        self.assertEqual(e.exception.status, 404)
    def test_keys_are_identity_scoped(self):
        self.submit(); self.submit(tenant="tenant-b"); self.submit(actor="other")
        self.assertEqual(len(self.engine.jobs), 3)
    def test_queued_cancel(self):
        _, j = self.submit()
        _, result = self.call({"action": "cancel", "job_id": j["job_id"]})
        self.assertTrue(result["cancellation_accepted"])
        self.assertEqual(result["status"], "cancelled")
    def test_running_cancel_does_not_claim_stopped(self):
        _, j = self.submit(); self.engine.jobs[0].state = State.RUNNING
        _, result = self.call({"action": "cancel", "job_id": j["job_id"]})
        self.assertFalse(result["cancellation_accepted"])
        self.assertEqual(result["status"], "running")
    def test_failed_job_never_returns_report(self):
        _, j = self.submit(); self.engine.jobs[0].state = State.FAILED
        _, result = self.call({"action": "status", "job_id": j["job_id"]})
        self.assertNotIn("report", result)
        self.assertEqual(result["error"], "native_execution_failed")
    def test_owner_limit_retains_idempotent_replay(self):
        self.w.per_owner = 1
        self.submit(); self.submit()
        with self.assertRaises(workspace.WorkspaceError) as e:
            self.submit(key="new")
        self.assertEqual(e.exception.status, 429)
    def test_global_limit(self):
        self.w.max_jobs = 1; self.submit()
        with self.assertRaises(workspace.WorkspaceError) as e:
            self.submit(tenant="tenant-b")
        self.assertEqual(e.exception.status, 429)
    def test_restart_does_not_claim_job_recovery(self):
        _, j = self.submit()
        with self.assertRaises(workspace.WorkspaceError) as e:
            workspace.Workspace().dispatch("tenant-a", "analyst", {"action": "status", "job_id": j["job_id"]})
        self.assertEqual(e.exception.status, 404)
    def test_history_empty_does_not_construct_native_pipeline(self):
        w = workspace.Workspace(lambda: self.fail("history constructed native engine"))
        _, page = w.dispatch("a", "b", {"action": "list"})
        self.assertEqual(page["jobs"], [])
        self.assertEqual(page["total_retained"], 0)
        self.assertIsNone(page["next_offset"])
    def test_history_isolated_by_tenant_and_actor(self):
        self.submit(); self.submit(key="other-tenant", tenant="tenant-b")
        self.submit(key="other-actor", actor="other")
        _, page = self.call({"action": "list"})
        self.assertEqual(len(page["jobs"]), 1)
        self.assertEqual(page["total_matching"], 1)
        self.assertEqual(page["total_retained"], 1)
        _, foreign = self.call({"action": "list"}, tenant="tenant-c")
        self.assertEqual(foreign["total_retained"], 0)
    def test_history_summaries_never_expose_report_program_or_keys(self):
        self.submit(); self.engine.jobs[0].state = State.SUCCEEDED
        _, page = self.call({"action": "list"})
        self.assertEqual(set(page["jobs"][0]), {"job_id", "status", "submitted_at", "n_qubits", "operation_count"})
        self.assertEqual(page["jobs"][0]["n_qubits"], 2)
        self.assertEqual(page["jobs"][0]["operation_count"], 2)
    def test_history_pagination_and_descending_order(self):
        for i in range(13): self.submit(key=f"job-{i}")
        _, first = self.call({"action": "list", "limit": 10})
        _, second = self.call({"action": "list", "limit": 10, "offset": first["next_offset"]})
        ids = [r["job_id"] for r in first["jobs"] + second["jobs"]]
        self.assertEqual(len(set(ids)), 13)
        self.assertEqual(ids[0], "fixture-job-12")
        self.assertEqual(len(second["jobs"]), 3)
        self.assertIsNone(second["next_offset"])
    def test_history_filters_native_status_and_identifier(self):
        self.submit(); self.submit(key="second")
        self.engine.jobs[0].state = State.FAILED
        _, page = self.call({"action": "list", "status": "failed", "query": "FIXTURE"})
        self.assertEqual(page["total_matching"], 1)
        self.assertEqual(page["total_retained"], 2)
        self.assertEqual(page["jobs"][0]["status"], "failed")
        _, page = self.call({"action": "list", "query": "no-match"})
        self.assertEqual(page["jobs"], [])
    def test_history_rejects_invalid_pagination_filters_and_fields(self):
        for fields in [{"offset": True}, {"offset": -1}, {"offset": 257},
                       {"limit": 0}, {"limit": 21}, {"limit": 2.0},
                       {"status": "completed"}, {"status": []}, {"query": 0},
                       {"query": "x" * 129}, {"actor": "other"}]:
            with self.subTest(fields=fields), self.assertRaises(workspace.WorkspaceError):
                self.call({"action": "list", **fields})
    def test_history_reports_current_native_state_not_previous_snapshot(self):
        self.submit()
        self.engine.jobs[0].state = State.RUNNING
        _, page = self.call({"action": "list"})
        self.assertEqual(page["jobs"][0]["status"], "running")
        self.engine.jobs[0].state = State.CANCELLED
        _, page = self.call({"action": "list"})
        self.assertEqual(page["jobs"][0]["status"], "cancelled")
    def test_new_process_history_does_not_claim_lifetime_zero_use(self):
        self.submit()
        _, page = workspace.Workspace().dispatch("tenant-a", "analyst", {"action": "list"})
        self.assertEqual(page["persistence"], "in_memory_process_local")
        self.assertEqual(page["service_mode"], "technical_evaluation_only")
        self.assertNotIn("billable_usage", page)
        self.assertNotIn("charges", page)
    def test_invalid_programs(self):
        bad = [None, {}, {"n_qubits": True, "operations": []}, {"n_qubits": "2", "operations": []},
            {"n_qubits": 13, "operations": []}, {"n_qubits": 2, "operations": [BELL["operations"][0]] * 257},
            {"n_qubits": 2, "operations": [{"gate": "h", "qubits": [True]}]},
            {"n_qubits": 2, "operations": [{"gate": "cx", "qubits": [0, 0]}]},
            {"n_qubits": 2, "operations": [{"gate": "h", "qubits": [2]}]},
            {"n_qubits": 2, "operations": [{"gate": "rx", "qubits": [0]}]},
            {"n_qubits": 2, "operations": [], "custody_dir": "/private"}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(workspace.WorkspaceError):
                workspace.validate_program(value)
    def test_unknown_actions_and_extra_fields(self):
        for body in [{"action": []}, {"action": "bill"}, {"action": "capabilities", "tenant": "other"}]:
            with self.subTest(body=body), self.assertRaises(workspace.WorkspaceError): self.call(body)
    def test_invalid_identity(self):
        for v in ["", "x\ny", "/other", "a" * 129]:
            with self.subTest(v=v), self.assertRaises(workspace.WorkspaceError): self.call({"action": "capabilities"}, tenant=v)
    def test_invalid_request_key(self):
        for value in [None, "", "a\nb", "a" * 129]:
            with self.subTest(value=value), self.assertRaises(workspace.WorkspaceError): self.submit(key=value)
    def test_disabled_and_unverified_receipt_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(workspace.handle_workspace({}, {}, {})[0], 503)
        with patch.dict(os.environ, {"TURING_WORKSPACE_PILOT_ENABLED": "1"}):
            for receipt in [None, {"allowed": False}, {"allowed": True, "tenant_id": "other", "operation": "quantum.workspace"}]:
                self.assertEqual(workspace.handle_workspace({"X-HYBA-Tenant": "a", "X-HYBA-Actor": "b"}, {}, receipt)[0], 403)
    def test_admitted_handler(self):
        headers = {"X-HYBA-Tenant": "tenant-a", "X-HYBA-Actor": "analyst"}
        receipt = {"allowed": True, "tenant_id": "tenant-a", "operation": "quantum.workspace"}
        with patch.dict(os.environ, {"TURING_WORKSPACE_PILOT_ENABLED": "1"}), patch.object(workspace, "_WORKSPACE", self.w):
            self.assertEqual(workspace.handle_workspace(headers, {"action": "capabilities"}, receipt)[0], 200)
    def test_missing_facade_is_unavailable_not_fixture(self):
        w = workspace.Workspace(lambda: (_ for _ in ()).throw(ImportError("missing")), lambda p: p)
        headers = {"X-HYBA-Tenant": "tenant-a", "X-HYBA-Actor": "analyst"}
        receipt = {"allowed": True, "tenant_id": "tenant-a", "operation": "quantum.workspace"}
        with patch.dict(os.environ, {"TURING_WORKSPACE_PILOT_ENABLED": "1"}), patch.object(workspace, "_WORKSPACE", w):
            code, result = workspace.handle_workspace(headers, {"action": "submit", "program": BELL, "idempotency_key": "test"}, receipt)
        self.assertEqual(code, 503); self.assertNotIn("report", result)


class RoutingTests(unittest.TestCase):
    """Execute the actual method AST, isolating the heavy host composition root.

    These are route-order regression tests, not a live authenticated HTTP test.
    """
    def test_workspace_guardian_dependency_error_does_not_leak_exception(self):
        tree = ast.parse((PLATFORM / "control_api.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_Handler")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_guardian_preflight")
        def unavailable(): raise RuntimeError("fixture-secret-and-private-path")
        scope = {"HTTPStatus": HTTPStatus, "pythia_guardian_api": unavailable, "Any": object}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), "control_api.py", "exec"), scope)
        class Handler:
            def _guardian_headers(self): return {}
            def _json(self, code, body): self.response = code, body
        h = Handler()
        self.assertFalse(scope["_guardian_preflight"](h, "/api/v1/quantum/workspace", {"observation": {}}))
        self.assertEqual(h.response[0], 503)
        self.assertEqual(h.response[1]["reason"], "guardian_dependency_failure")
        self.assertNotIn("fixture-secret", str(h.response))
    def test_preflight_denial_never_dispatches(self):
        tree = ast.parse((PLATFORM / "control_api.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_Handler")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_route_post")
        scope = {"urlparse": urlparse, "HTTPStatus": HTTPStatus}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), "control_api.py", "exec"), scope)
        class Handler:
            path = "/api/v1/quantum/workspace"
            headers = {}
            def _read_json_body(self): return {"action": "capabilities"}, None
            def _guardian_preflight(self, path, body): return False
            def _json(self, *args): raise AssertionError("route continued after guardian denial")
        with patch.object(workspace, "handle_workspace", side_effect=AssertionError("unauthorized dispatch")):
            scope["_route_post"](Handler())
    def test_allowed_route_passes_receipt_and_uses_existing_json_boundary(self):
        tree = ast.parse((PLATFORM / "control_api.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_Handler")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_route_post")
        scope = {"urlparse": urlparse, "HTTPStatus": HTTPStatus}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), "control_api.py", "exec"), scope)
        class Handler:
            path = "/api/v1/quantum/workspace"
            headers = {"X-HYBA-Tenant": "tenant-a", "X-HYBA-Actor": "analyst"}
            def _read_json_body(self): return {"action": "capabilities"}, None
            def _guardian_preflight(self, path, body):
                self._guardian_receipt = {"allowed": True, "tenant_id": "tenant-a", "operation": "quantum.workspace"}
                return True
            def _json(self, code, body): self.response = code, body
        h = Handler()
        with patch.dict(os.environ, {"TURING_WORKSPACE_PILOT_ENABLED": "1"}): scope["_route_post"](h)
        self.assertEqual(h.response[0], 200)


@unittest.skipUnless(os.environ.get("TURING_RUN_ENGINE_SMOKE") == "1", "opt-in real-engine smoke; unit fixtures are not engine evidence")
class NativeSmoke(unittest.TestCase):
    def test_real_native_bell_report(self):
        sys.path.insert(0, str(ROOT / "turing_universal_quantum_computer"))
        w = workspace.Workspace()
        try:
            _, j = w.dispatch("pilot", "reviewer", {"action": "submit", "program": BELL, "idempotency_key": "real-smoke"})
            w._jobs[j["job_id"]].job.result(timeout=60)
            _, result = w.dispatch("pilot", "reviewer", {"action": "status", "job_id": j["job_id"]})
            self.assertEqual(result["status"], "succeeded")
            report = result["report"]["pipeline_report"]
            self.assertEqual(report["verdict"], "PASS")
            self.assertEqual(report["result"]["truth_class"], "exact")
            self.assertTrue(report["certificate"])
            self.assertTrue(report["witness"])
        finally: w.close()


if __name__ == "__main__": unittest.main()
