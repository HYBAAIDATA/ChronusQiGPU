import tempfile
import unittest
from pathlib import Path
from al_haras.privileged_audit import audit, manifest, verify_manifest
from al_haras.mediation_runtime import privileged_route


class Tests(unittest.TestCase):
    def test_repository_privileged_routes_are_mediated(self):
        routes, violations = audit(Path("."))
        priv = [
            r
            for r in routes
            if r.path.startswith(("/api/v1/security/", "/api/v1/mining/", "/api/v1/toe/"))
        ]
        self.assertTrue(priv)
        self.assertFalse(violations)
        for route in priv:
            self.assertTrue(any(x.endswith("guardian_middleware") for x in route.decorators))
            self.assertTrue(any(x.endswith("evidence_attach") for x in route.decorators))

    def test_missing_decorators_fail_and_tests_are_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "app.py").write_text(
                "from fastapi import FastAPI\napp=FastAPI()\n@app.post('/api/v1/admin/x')\ndef x(): pass\n"
            )
            (root / "tests").mkdir()
            (root / "tests" / "bad.py").write_text(
                "@app.post('/api/v1/admin/test')\ndef x():pass\n"
            )
            routes, violations = audit(root)
            self.assertEqual(len(routes), 1)
            self.assertEqual(
                {v.reason for v in violations},
                {"privileged_route_without_guardian", "privileged_route_without_evidence"},
            )

    def test_new_route_inherits_explicit_markers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "app.py").write_text(
                "from fastapi import APIRouter\nr=APIRouter(prefix='/api/v1/admin')\n@r.post('/x')\n@guardian_middleware\n@evidence_attach\ndef x():pass\n"
            )
            _, violations = audit(root)
            self.assertFalse(violations)

        class Router:
            def post(self, path, **kwargs):
                return lambda fn: fn

        @privileged_route(Router(), "post", "/api/v1/admin/new")
        def endpoint():
            return True

        self.assertTrue(endpoint.__guardian_mediated__)
        self.assertTrue(endpoint.__guardian_evidence__)

    def test_table_driven_requires_installed_hooks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = "from http.server import BaseHTTPRequestHandler\nclass H(BaseHTTPRequestHandler):\n T={'/api/v1/mining/start':1}\n"
            (root / "c.py").write_text(source)
            self.assertTrue(audit(root)[1])
            (root / "c.py").write_text(
                "PRIVILEGED_MEDIATION_INSTALLED = True\n"
                + source
                + "\ndef _guardian_preflight():pass\ndef _guardian_commit_evidence():pass\n"
            )
            self.assertFalse(audit(root)[1])

    def test_signed_manifest_verifies_and_tamper_fails(self):
        routes, violations = audit(Path("."))
        key = b"m" * 32
        value = manifest(routes, violations, key)
        self.assertTrue(verify_manifest(value, key))
        value["violations"] = [{"x": 1}]
        self.assertFalse(verify_manifest(value, key))

    def test_import_failure_is_fatal_contract(self):
        source = Path("al_haras/fastapi.py").read_text()
        self.assertIn('raise RuntimeError("FastAPI is required for the AL HARAS router")', source)


if __name__ == "__main__":
    unittest.main()
