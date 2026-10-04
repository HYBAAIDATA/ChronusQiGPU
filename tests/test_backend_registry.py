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


def _probe(lane, available, reason, hasher=None, device=None):
    return lambda: LaneProbe(
        lane=lane.value,
        available=available,
        backend=lane.value,
        device=device,
        probed_at=0.0,
        reason=reason,
        hasher=hasher,
    )


class FakeHasher:
    def __init__(self, backend, device):
        self.backend, self.device = backend, device


class BackendRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.evidence = Path(self.tmp.name) / "evidence.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def registry(self, gpu=False, gpu_hasher=None):
        return BackendRegistry(
            software_revision="test-revision",
            evidence_path=self.evidence,
            probes={
                BackendLane.CPU: _probe(BackendLane.CPU, True, "reference always bound"),
                BackendLane.GPU: _probe(
                    BackendLane.GPU,
                    gpu,
                    "opencl device bound" if gpu else "no OpenCL device",
                    hasher=gpu_hasher,
                    device="opencl" if gpu else None,
                ),
                BackendLane.REMOTE_GPU: _probe(
                    BackendLane.REMOTE_GPU, False, "endpoint unreachable"
                ),
                BackendLane.ASIC: _probe(BackendLane.ASIC, False, "no ASIC transport"),
                BackendLane.SUPER_ASIC: _probe(BackendLane.SUPER_ASIC, False, "not implemented"),
            },
        )

    def test_auto_falls_back_to_cpu_and_records_probed_lanes(self):
        value = self.registry()
        selection = value.select("auto", job_id="job-1", epoch="7")
        self.assertEqual(selection.lane, "cpu")
        self.assertTrue(selection.fallback)
        self.assertEqual(selection.selected_action, "cpu")
        self.assertEqual(selection.job_id, "job-1")
        self.assertEqual(selection.epoch, "7")
        self.assertEqual(selection.disposition, "accepted")
        persisted = json.loads(self.evidence.read_text().splitlines()[0])
        self.assertEqual(persisted["execution_target"], "cpu")
        self.assertFalse(persisted["observation"]["probes"]["gpu"]["available"])
        self.assertFalse(persisted["observation"]["probes"]["remote_gpu"]["available"])

    def test_explicit_gpu_never_silently_falls_back(self):
        value = self.registry()
        with self.assertRaisesRegex(BackendUnavailable, "gpu: no OpenCL device"):
            value.select("gpu")
        self.assertEqual(value.last_selection.selected_action, "Unavailable")
        self.assertEqual(value.last_selection.disposition, "rejected")

    def test_unavailable_lane_is_not_selectable_even_with_a_hasher(self):
        value = self.registry(gpu_hasher=FakeHasher("gpu", "broken"))
        with self.assertRaisesRegex(BackendUnavailable, "no OpenCL device"):
            value.select("gpu")
        self.assertEqual(value.last_selection.disposition, "rejected")

    def test_snapshot_keeps_unavailable_lanes_visible_with_reasons(self):
        value = self.registry()
        snapshot = value.snapshot()
        self.assertEqual(snapshot["schema"], "pythia.backend_registry/1")
        lanes = snapshot["lanes"]
        self.assertEqual(set(lanes), {"cpu", "gpu", "remote_gpu", "asic", "super_asic"})
        self.assertTrue(lanes["cpu"]["available"])
        self.assertFalse(lanes["asic"]["available"])
        self.assertEqual(lanes["super_asic"]["reason"], "not implemented")


if __name__ == "__main__":
    unittest.main()
