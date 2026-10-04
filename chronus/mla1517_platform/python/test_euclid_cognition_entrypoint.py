"""Production entry-point contract for EUCLID cognition in the control plane.

These run inside ``unittest discover -s chronus/mla1517_platform/python``, so
the control plane's own suite fails if the intelligence entry point regresses.

The loop is exercised through ``system_fabric`` against the canonical
composition root (``EuclidRuntime.production``) — never a simulation.  The
executor seam is replaced only to keep the suite fast and deterministic; the
world model, memory, learning, planner and reachability are all the real ones.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from typing import Any, Mapping

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _path in (_REPO, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import system_fabric  # noqa: E402
from euclid.runtime import EuclidRuntime  # noqa: E402


class _DeterministicExecutor:
    """Deterministic governed executor: pure function of the action."""

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "observation": f"observed:{action}",
            "goal_met": False,
            "cycle": payload.get("cycle"),
            "reward_authority": "none",
        }


class TestEuclidCognitionEntryPoint(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._previous = os.environ.get("PYTHIA_EUCLID_STATE_DIR")
        os.environ["PYTHIA_EUCLID_STATE_DIR"] = self._tmp.name
        self.addCleanup(self._restore_env)
        system_fabric.euclid_cognition_close()
        self.addCleanup(system_fabric.euclid_cognition_close)

    def _restore_env(self) -> None:
        if self._previous is None:
            os.environ.pop("PYTHIA_EUCLID_STATE_DIR", None)
        else:
            os.environ["PYTHIA_EUCLID_STATE_DIR"] = self._previous

    @staticmethod
    def _problem() -> dict[str, Any]:
        return {
            "problem_class": "repository-wiring",
            "structure": ["rel:dependency-chain", "rel:action-outcome"],
            "observations": ["an import boundary is under review"],
        }

    def test_status_before_and_after_an_episode(self) -> None:
        runtime = system_fabric.euclid_cognition()
        self.assertIsNotNone(runtime)
        self.assertIsInstance(runtime, EuclidRuntime)
        runtime.cognition.executor = _DeterministicExecutor()

        fresh = system_fabric.euclid_cognition_status()
        self.assertTrue(fresh["available"])
        self.assertEqual(fresh["state_dir"], self._tmp.name)
        # Nothing is claimed before there is evidence for it.
        self.assertIn("transfer_not_verified", fresh["open_gates"])
        self.assertIn("restart_not_verified", fresh["open_gates"])
        self.assertIn("production_certification_absent", fresh["open_gates"])

        system_fabric.euclid_cognition_solve(
            "platform-1", "diagnose the wiring",
            strategy="primitive-compose", **self._problem(),
        )
        warm = system_fabric.euclid_cognition_status()
        self.assertTrue(warm["memory"]["integrity"]["valid"])
        self.assertTrue(warm["replay_journal"]["verified"])
        self.assertTrue(warm["evidence_head"])

    def test_solve_runs_the_loop_and_reports_real_evidence(self) -> None:
        runtime = system_fabric.euclid_cognition()
        runtime.cognition.executor = _DeterministicExecutor()
        result = system_fabric.euclid_cognition_solve(
            "platform-2", "diagnose the wiring",
            strategy="primitive-compose", **self._problem(),
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["authority"], "euclid.cognition")
        phases = {t["phase"] for t in result["transitions"]}
        for phase in ("represent", "retrieve", "abduce", "deduce", "strategy",
                      "plan", "compose", "execute", "compare", "learn"):
            self.assertIn(phase, phases)
        self.assertTrue(result["hypotheses"])
        self.assertTrue(result["learning_updates"])
        self.assertTrue(result["state_digest"])

    def test_unavailable_strategy_and_invalid_request_fail_closed(self) -> None:
        system_fabric.euclid_cognition()
        unknown = system_fabric.euclid_cognition_solve(
            "platform-3", "diagnose the wiring", strategy="imaginary-strategy",
            **self._problem(),
        )
        self.assertFalse(unknown["available"])
        self.assertEqual(unknown["failure"], "strategy_unavailable")

        invalid = system_fabric.euclid_cognition_solve("", "")
        self.assertFalse(invalid["available"])
        self.assertEqual(invalid["failure"], "invalid_request")

    def test_close_is_idempotent_and_releases_the_directory(self) -> None:
        runtime = system_fabric.euclid_cognition()
        runtime.cognition.executor = _DeterministicExecutor()
        system_fabric.euclid_cognition_solve(
            "platform-4", "diagnose the wiring",
            strategy="primitive-compose", **self._problem(),
        )
        self.assertTrue(system_fabric.euclid_cognition_close()["closed"])
        self.assertFalse(system_fabric.euclid_cognition_close()["closed"])
        shutil.rmtree(self._tmp.name, ignore_errors=True)
        self.assertFalse(os.path.exists(self._tmp.name))


if __name__ == "__main__":
    unittest.main()
