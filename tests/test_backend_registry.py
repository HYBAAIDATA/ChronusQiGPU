import json
import tempfile
import unittest
from pathlib import Path

from chronus.mla1517.mining.backend_registry import (
    BackendLane,
    BackendRegistry,
    BackendUnavailable,
    LaneProbe,
)


def _probe(lane, available, backend=None, device=None, reason=""):
    def factory():
        return LaneProbe(
            lane=lane.value,
            available=available,
            backend=backend,
            device=device,
            probed_at=0.0,
            reason=reason,
        )

    return factory


class _FakeHasher:
    def __init__(self, backend, device, healthy=True):
        self.backend, self.device, self.healthy = backend, device, healthy


class BackendRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.evidence = Path(self.tmp.name) / "evidence.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def registry(self, **overrides):
        probes = {
            BackendLane.CPU: _probe(BackendLane.CPU, True, "cpu", "host", "cpu reference"),
            BackendLane.GPU: _probe(BackendLane.GPU, False, reason="no OpenCL device"),
            BackendLane.REMOTE_GPU: _probe(
                BackendLane.REMOTE_GPU, False, reason="no remote endpoint"
            ),
            BackendLane.ASIC: _probe(BackendLane.ASIC, False, reason="no ASIC transport"),
            BackendLane.SUPER_ASIC: _probe(
                BackendLane.SUPER_ASIC, False, reason="not implemented"
            ),
        }
        probes.update(overrides)
        return BackendRegistry(
            probes=probes,
            software_revision="test-revision",
            evidence_path=self.evidence,
        )

    def test_auto_falls_back_to_cpu_and_records_evidence(self):
        registry = self.registry()
        selection = registry.select("auto", job_id="job-1", epoch="7")
        self.assertEqual(selection.selected_action, "cpu")
        self.assertEqual(selection.execution_target, "cpu")
        self.assertTrue(selection.fallback)
        self.assertEqual(selection.disposition, "accepted")
        self.assertEqual(selection.job_id, "job-1")
        self.assertEqual(selection.epoch, "7")
        persisted = json.loads(self.evidence.read_text().splitlines()[0])
        self.assertEqual(persisted["execution_target"], "cpu")
        self.assertEqual(persisted["software_revision"], "test-revision")
        self.assertFalse(persisted["probed"]["gpu"]["available"])

    def test_explicit_unavailable_lane_fails_closed(self):
        registry = self.registry()
        with self.assertRaisesRegex(BackendUnavailable, "gpu"):
            registry.select("gpu")
        self.assertEqual(registry.last_selection.disposition, "rejected")
        self.assertEqual(registry.last_selection.selected_action, "Unavailable")

    def test_unknown_policy_is_rejected(self):
        registry = self.registry()
        with self.assertRaisesRegex(BackendUnavailable, "unknown backend policy"):
            registry.select("qpu")

    def test_snapshot_lists_every_lane_and_policy(self):
        registry = self.registry()
        snapshot = registry.snapshot()
        self.assertEqual(
            set(snapshot["lanes"]),
            {"cpu", "gpu", "remote_gpu", "asic", "super_asic"},
        )
        self.assertEqual(snapshot["policy"]["auto"], ["gpu", "remote_gpu", "cpu"])
        self.assertFalse(snapshot["lanes"]["asic"]["available"])
        self.assertTrue(snapshot["lanes"]["cpu"]["available"])

    def test_auto_prefers_gpu_when_available(self):
        hasher = _FakeHasher("gpu", "opencl0")

        def gpu_probe():
            return LaneProbe(
                lane="gpu",
                available=True,
                backend="gpu",
                device="opencl0",
                probed_at=0.0,
                reason="opencl device bound",
                hasher=hasher,
            )

        registry = self.registry(**{BackendLane.GPU: gpu_probe})
        selection = registry.select("auto")
        self.assertEqual(selection.selected_action, "gpu")
        self.assertFalse(selection.fallback)
        self.assertIs(selection.hasher, hasher)


if __name__ == "__main__":
    unittest.main()
