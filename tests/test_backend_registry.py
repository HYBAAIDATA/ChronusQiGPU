import json
import tempfile
import unittest
from pathlib import Path

from chronus.mla1517.mining.backend_registry import BackendKind, BackendRegistry, BackendUnavailable


class FakeHasher:
    def __init__(self, backend, device, healthy=True):
        self.backend, self.device, self.healthy = backend, device, healthy


class BackendRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.evidence = Path(self.tmp.name) / "evidence.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def registry(self):
        value = BackendRegistry(software_revision="test-revision", evidence_path=self.evidence)
        value.register("cpu", BackendKind.CPU, "reference", factory=lambda: FakeHasher("cpu", "host"))
        value.register("gpu", BackendKind.GPU, "opencl", factory=None, unavailable_reason="no OpenCL device")
        value.register("asic", BackendKind.ASIC, "external", factory=None, unavailable_reason="no ASIC transport")
        value.register("super_asic", BackendKind.SUPER_ASIC, "external", factory=None, unavailable_reason="not implemented")
        return value

    def test_auto_uses_declared_policy_and_records_skipped_lanes(self):
        value = self.registry()
        backend = value.select("auto", policy_order=("super_asic", "asic", "gpu", "cpu"), job_id="job-1", epoch="7")
        self.assertEqual(backend.backend, "cpu")
        decision = backend.backend_selection
        self.assertEqual(decision["selected_action"], "cpu")
        self.assertEqual(decision["job_id"], "job-1")
        self.assertEqual(decision["epoch"], "7")
        self.assertEqual(decision["disposition"], "accepted")
        persisted = json.loads(self.evidence.read_text().splitlines()[0])
        self.assertEqual(persisted["execution_target"], "cpu")
        self.assertFalse(persisted["observation"]["capabilities"]["super_asic"]["available"])

    def test_explicit_gpu_never_silently_falls_back(self):
        value = self.registry()
        with self.assertRaisesRegex(BackendUnavailable, "gpu: no OpenCL device"):
            value.select("gpu", policy_order=("gpu", "cpu"))
        self.assertEqual(value.last_selection.selected_action, "Unavailable")
        self.assertEqual(value.last_selection.disposition, "rejected")

    def test_unhealthy_backend_is_not_selectable(self):
        value = BackendRegistry(evidence_path=self.evidence)
        value.register("gpu", BackendKind.GPU, "opencl", factory=lambda: FakeHasher("gpu", "broken", False))
        with self.assertRaisesRegex(BackendUnavailable, "reported unhealthy"):
            value.select("gpu", policy_order=("gpu",))

    def test_backend_kinds_explicit_when_unavailable(self):
        value = self.registry()
        value.probe_all()
        snapshot = value.snapshot()
        self.assertEqual({cap["kind"] for cap in snapshot["capabilities"].values()}, {"CPU", "GPU", "ASIC", "SUPER_ASIC"})
        self.assertFalse(snapshot["capabilities"]["asic"]["available"])
        self.assertEqual(snapshot["capabilities"]["super_asic"]["reason"], "not implemented")


if __name__ == "__main__":
    unittest.main()
