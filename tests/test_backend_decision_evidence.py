import json
import tempfile
import types
import unittest
import sys
from pathlib import Path

from chronus.mla1517.mining.backend_registry import (
    BackendLane,
    BackendRegistry,
    BackendUnavailable,
    LaneProbe,
)


class FakeHasher:
    backend = "cpu"
    device = "fixture"


def probe(lane, available, *, hasher=None, reason="measured fixture"):
    return LaneProbe(lane.value, available, lane.value if available else None, "fixture" if available else None, 1.0, reason, hasher)


class BackendDecisionEvidenceTests(unittest.TestCase):
    _STUB_NAME = "chronus.mla1517.mining.coordinator"
    _MISSING = object()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._prior = sys.modules.get(self._STUB_NAME, self._MISSING)
        module = types.ModuleType(self._STUB_NAME)
        module.CpuReferenceHasher = FakeHasher
        sys.modules[module.__name__] = module
        self.path = Path(self.tmp.name) / "backend.jsonl"

    def tearDown(self):
        # Restore sys.modules: the stub shadows a real package module and
        # leaking it breaks later tests that import the real coordinator.
        if self._prior is self._MISSING:
            sys.modules.pop(self._STUB_NAME, None)
        else:
            sys.modules[self._STUB_NAME] = self._prior
        self.tmp.cleanup()

    def registry(self, *, gpu=False):
        probes = {
            BackendLane.CPU: lambda: probe(BackendLane.CPU, True),
            BackendLane.GPU: lambda: probe(BackendLane.GPU, gpu, hasher=FakeHasher() if gpu else None, reason="GPU probe result"),
            BackendLane.REMOTE_GPU: lambda: probe(BackendLane.REMOTE_GPU, False),
            BackendLane.ASIC: lambda: probe(BackendLane.ASIC, False, reason="no driver"),
            BackendLane.SUPER_ASIC: lambda: probe(BackendLane.SUPER_ASIC, False, reason="no driver"),
        }
        value = BackendRegistry(probes=probes, clock=lambda: 1234.5, software_revision="abc123", evidence_path=self.path)
        return value

    def test_auto_fallback_is_durable_structured_evidence(self):
        value = self.registry()
        selected = value.select("auto", job_id="job-9", epoch="epoch-4")
        self.assertEqual(selected.lane, "cpu")
        self.assertTrue(selected.fallback)
        self.assertEqual(selected.disposition, "accepted")
        self.assertEqual(selected.software_revision, "abc123")
        self.assertEqual(selected.job_id, "job-9")
        self.assertEqual(selected.epoch, "epoch-4")
        event = json.loads(self.path.read_text().strip())
        self.assertEqual(event["execution_target"], "cpu")
        self.assertEqual(event["result"], "backend_bound")
        self.assertNotIn("hasher", event)
        self.assertEqual(value.snapshot()["last_selection"]["decision_id"], selected.decision_id)

    def test_explicit_unavailable_lane_records_rejection_before_raising(self):
        value = self.registry()
        with self.assertRaisesRegex(BackendUnavailable, "no lane available"):
            value.select("asic", job_id="job-10", epoch="epoch-5")
        event = json.loads(self.path.read_text().strip())
        self.assertEqual(event["selected_action"], "Unavailable")
        self.assertEqual(event["disposition"], "rejected")
        self.assertEqual(event["job_id"], "job-10")
        self.assertEqual(event["observation"]["probes"]["asic"]["reason"], "no driver")


if __name__ == "__main__":
    unittest.main()
