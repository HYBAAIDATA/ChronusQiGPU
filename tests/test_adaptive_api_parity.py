"""Parity and governed execution tests for EUCLID v17 adaptive task path via API and system_fabric."""
from __future__ import annotations

import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path

from chronus.mla1517_platform.python import control_api, system_fabric
from euclid.cognition.software_tasks import SoftwareTaskWorld, create_software_task
from euclid.runtime import EuclidRuntime


class AdaptiveApiParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        # Ensure fresh cognition instance
        system_fabric.euclid_cognition_close()
        self.addCleanup(system_fabric.euclid_cognition_close)

    def test_direct_adaptive_family_solve(self) -> None:
        result = system_fabric.euclid_cognition_solve(
            mode="adaptive",
            family="symbolic-rewriting",
            seed=7,
        )
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("mode"), "adaptive")
        self.assertEqual(result.get("schema"), "pythia.euclid.cognition.solve/1")
        self.assertIn("reachability", result)
        self.assertIsInstance(result.get("transitions"), list)
        self.assertGreater(len(result["transitions"]), 0)

    def test_direct_software_task_solve(self) -> None:
        code = "def double(x):\n    return x * 2\n"
        test = "assert double(3) == 6\n"
        result = system_fabric.euclid_cognition_solve(
            mode="adaptive",
            problem_id="soft-task-1",
            initial_code=code,
            test_code=test,
            seed=1,
        )
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("mode"), "adaptive")
        self.assertTrue(result.get("solved"))
        self.assertEqual(result.get("outcome"), "solved")

    def test_control_api_adaptive_solve_endpoint(self) -> None:
        body = {
            "mode": "adaptive",
            "family": "program-transformation",
            "seed": 12,
        }
        status, payload = control_api._euclid_cognition_solve(body)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "adaptive")
        self.assertIn("reachability", payload)
        self.assertIn("cost", payload)
        self.assertIn("probes", payload)

    def test_control_api_software_task_endpoint(self) -> None:
        body = {
            "mode": "adaptive",
            "problem_id": "api-soft-task",
            "initial_code": "def inc(x):\n    return x + 1\n",
            "test_code": "assert inc(5) == 6\n",
            "seed": 42,
        }
        status, payload = control_api._euclid_cognition_solve(body)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "adaptive")
        self.assertTrue(payload.get("solved"))

    def test_legacy_inspect_mode_preserved(self) -> None:
        body = {
            "problem_id": "prob-legacy-1",
            "goal": "audit repository wiring and imports",
            "problem_class": "repository-wiring",
        }
        status, payload = control_api._euclid_cognition_solve(body)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("problem_id"), "prob-legacy-1")
        self.assertNotEqual(payload.get("mode"), "adaptive")
        self.assertEqual(payload.get("authority"), "euclid.cognition")

    def test_software_task_world_ast_safety_and_diff(self) -> None:
        spec, world = create_software_task(
            "test-sec-diff",
            code="def add(a, b):\n    return a + b\n",
            test_code="assert add(1, 2) == 3\n",
        )
        # Probe
        probe_res = world.probe([])
        self.assertEqual(probe_res["kind"], "intervention")
        self.assertTrue(probe_res["safe"])
        self.assertIn("diff", probe_res)

        # Submit clean code
        sub_res = world.submit([])
        self.assertEqual(sub_res["kind"], "plan")
        self.assertTrue(sub_res["goal_met"])
        self.assertEqual(sub_res["reward"], 1.0)
        self.assertTrue(world.solved)


if __name__ == "__main__":
    unittest.main()
