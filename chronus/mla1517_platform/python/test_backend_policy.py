"""Canonical runtime backend-policy tests.

These tests exercise the production selector, not BackendRegistry internals:
``auto`` may follow an operator-declared order, every lane is still probed by
BackendRegistry, and CPU is never appended behind the operator's back.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mining_runtime
from chronus.mla1517.mining.backend_registry import BackendUnavailable


class _Registry:
    def __init__(self, available: set[str]):
        self.available = set(available)
        self.calls: list[tuple[str, bool, str, str]] = []

    def select(
        self,
        requested: str,
        *,
        reprobe: bool = False,
        job_id: str = "Unavailable",
        epoch: str = "Unavailable",
    ):
        self.calls.append((requested, reprobe, job_id, epoch))
        if requested not in self.available:
            raise BackendUnavailable(f"{requested} unavailable")
        return SimpleNamespace(
            requested=requested,
            lane=requested,
            hasher=SimpleNamespace(backend=requested),
            fallback=False,
            reason=f"{requested} available",
        )


class BackendPolicyTests(unittest.TestCase):
    def test_unset_order_delegates_to_registry_auto(self):
        registry = _Registry({"auto"})
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PYTHIA_BACKEND_ORDER", None)
            selection = mining_runtime.select_execution_backend(registry, "auto")
        self.assertEqual(selection.lane, "auto")
        self.assertEqual(registry.calls, [("auto", False, "Unavailable", "Unavailable")])

    def test_declared_order_selects_first_capability_proven_lane(self):
        registry = _Registry({"gpu", "cpu"})
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "asic,gpu,cpu"}):
            selection = mining_runtime.select_execution_backend(
                registry,
                "auto",
                job_id="job-9",
                epoch="4",
            )
        self.assertEqual(selection.lane, "gpu")
        self.assertEqual(
            registry.calls,
            [
                ("asic", False, "job-9", "4"),
                ("gpu", False, "job-9", "4"),
            ],
        )

    def test_declared_order_never_injects_cpu_fallback(self):
        registry = _Registry({"cpu"})
        with patch.dict(os.environ, {"PYTHIA_BACKEND_ORDER": "asic,gpu"}):
            with self.assertRaisesRegex(BackendUnavailable, "declared PYTHIA_BACKEND_ORDER"):
                mining_runtime.select_execution_backend(registry, "auto")
        self.assertEqual([call[0] for call in registry.calls], ["asic", "gpu"])
        self.assertNotIn("cpu", [call[0] for call in registry.calls])

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
