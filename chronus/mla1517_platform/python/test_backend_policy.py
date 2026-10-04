"""Canonical runtime backend-policy tests.

These tests exercise the production selector: ``auto`` may follow an
operator-declared order, every lane is still probed by BackendRegistry, CPU is
never appended behind the operator's back, and the final decision preserves the
original request plus refused-lane/fallback provenance.
"""

from __future__ import annotations

import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mining_runtime
from chronus.mla1517.mining.backend_registry import (
    BackendSelection,
    BackendUnavailable,
    LaneProbe,
)


class _Registry:
    def __init__(self, available: set[str]):
        self.available = set(available)
        self.calls: list[tuple[str, bool, str, str]] = []
        self.last_selection: BackendSelection | None = None
        self.recorded: list[BackendSelection] = []

    def _record(self, selection: BackendSelection) -> None:
        self.last_selection = selection
        self.recorded.append(selection)

    def select(
        self,
        requested: str,
        *,
        reprobe: bool = False,
        job_id: str = "Unavailable",
        epoch: str = "Unavailable",
    ) -> BackendSelection:
        self.calls.append((requested, reprobe, job_id, epoch))
        available = requested in self.available
        probe = LaneProbe(
            lane=requested,
            available=available,
            backend=requested if available else None,
            device=f"{requested}-device" if available else None,
            probed_at=time.time(),
            reason=f"{requested} {'available' if available else 'unavailable'}",
        )
        if not available:
            selection = BackendSelection(
                requested=requested,
                lane="Unavailable",
                hasher=None,
                fallback=False,
                reason=f"{requested} unavailable",
                probed={requested: probe},
                job_id=job_id,
                epoch=epoch,
                observation={"requested": requested},
                selected_action="Unavailable",
                execution_target="Unavailable",
                result="no_backend_bound",
                disposition="rejected",
                timestamp=time.time(),
            )
            self._record(selection)
            raise BackendUnavailable(selection.reason)
        selection = BackendSelection(
            requested=requested,
            lane=requested,
            hasher=SimpleNamespace(backend=requested, fallback_reason=None),
            fallback=False,
            reason=f"{requested} available",
            probed={requested: probe},
            job_id=job_id,
            epoch=epoch,
            observation={"requested": requested},
            available_actions=(requested,),
            selected_action=requested,
            execution_target=requested,
            result="backend_bound",
            disposition="accepted",
            timestamp=time.time(),
        )
        self._record(selection)
        return selection


class BackendPolicyTests(unittest.TestCase):
    def test_unset_order_delegates_to_registry_auto(self):
        registry = _Registry({"auto"})
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PYTHIA_BACKEND_ORDER", None)
            selection = mining_runtime.select_execution_backend(registry, "auto")
        self.assertEqual(selection.lane, "auto")
        self.assertEqual(registry.calls, [("auto", False, "Unavailable", "Unavailable")])

    def test_declared_order_preserves_refusal_and_fallback_provenance(self):
        registry = _Registry({"gpu", "cpu"})
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "asic,gpu,cpu"}):
            selection = mining_runtime.select_execution_backend(
                registry,
                "auto",
                job_id="job-9",
                epoch="4",
            )
        self.assertEqual(selection.requested, "auto")
        self.assertEqual(selection.lane, "gpu")
        self.assertTrue(selection.fallback)
        self.assertIn("asic: asic unavailable", selection.reason)
        self.assertEqual(selection.observation["policy_source"], "PYTHIA_BACKEND_ORDER")
        self.assertEqual(selection.observation["policy_order"], ["asic", "gpu", "cpu"])
        self.assertEqual(
            [attempt["outcome"] for attempt in selection.observation["attempts"]],
            ["refused", "selected"],
        )
        self.assertEqual(set(selection.probed), {"asic", "gpu"})
        self.assertIs(registry.last_selection, selection)
        self.assertEqual(
            registry.calls,
            [
                ("asic", False, "job-9", "4"),
                ("gpu", False, "job-9", "4"),
            ],
        )

    def test_declared_cpu_fallback_is_explicit_in_selection_and_hasher(self):
        registry = _Registry({"cpu"})
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "gpu,cpu"}):
            selection = mining_runtime.select_execution_backend(registry, "auto")
        self.assertEqual(selection.requested, "auto")
        self.assertEqual(selection.lane, "cpu")
        self.assertTrue(selection.fallback)
        self.assertIn("gpu: gpu unavailable", selection.reason)
        self.assertEqual(selection.hasher.fallback_reason, selection.reason)

    def test_first_declared_lane_is_not_reported_as_fallback(self):
        registry = _Registry({"asic"})
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "asic,cpu"}):
            selection = mining_runtime.select_execution_backend(registry, "auto")
        self.assertEqual(selection.requested, "auto")
        self.assertEqual(selection.lane, "asic")
        self.assertFalse(selection.fallback)
        self.assertEqual(selection.observation["attempts"][0]["outcome"], "selected")

    def test_declared_order_never_injects_cpu_fallback(self):
        registry = _Registry({"cpu"})
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "asic,gpu"}):
            with self.assertRaisesRegex(BackendUnavailable, "declared PYTHIA_BACKEND_ORDER"):
                mining_runtime.select_execution_backend(registry, "auto")
        self.assertEqual([call[0] for call in registry.calls], ["asic", "gpu"])
        self.assertNotIn("cpu", [call[0] for call in registry.calls])
        self.assertEqual(registry.last_selection.requested, "auto")
        self.assertEqual(registry.last_selection.disposition, "rejected")
        self.assertEqual(
            [attempt["outcome"] for attempt in registry.last_selection.observation["attempts"]],
            ["refused", "refused"],
        )

    def test_explicit_backend_ignores_auto_order_and_fails_closed(self):
        registry = _Registry({"cpu"})
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "cpu"}):
            with self.assertRaisesRegex(BackendUnavailable, "gpu unavailable"):
                mining_runtime.select_execution_backend(registry, "gpu")
        self.assertEqual([call[0] for call in registry.calls], ["gpu"])

    def test_remote_gpu_alias_is_normalized_and_duplicates_are_removed(self):
        with patch.dict(
            os.environ,
            {"PYTHIA_BACKEND_ORDER": "remote_gpu,remote,opencl,gpu,cpu"},
        ):
            self.assertEqual(mining_runtime.backend_order(), ("remote", "opencl", "cpu"))

    def test_invalid_or_recursive_order_is_rejected_at_startup(self):
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "auto,cpu"}):
            with self.assertRaisesRegex(SystemExit, "concrete backends"):
                mining_runtime.backend_order()
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "fpga"}):
            with self.assertRaisesRegex(SystemExit, "unknown backend"):
                mining_runtime.backend_order()

    def test_reprobe_flag_propagates_through_declared_order(self):
        registry = _Registry({"asic"})
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "asic,cpu"}):
            mining_runtime.select_execution_backend(registry, "auto", reprobe=True)
        self.assertEqual(registry.calls[0][0:2], ("asic", True))


if __name__ == "__main__":
    unittest.main()
