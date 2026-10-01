import unittest
from types import SimpleNamespace
from unittest.mock import patch

from chronus.mla1517.scaling import (
    LUCAS_PISOT_LADDER,
    exact_ladder,
    GPUExecutionUnavailable,
    OpenCLLadderExecutor,
    _select_device,
)


class ScalingTests(unittest.TestCase):
    def test_exact_declared_ladder(self):
        values = exact_ladder()
        self.assertEqual(tuple(v.scale for v in values), LUCAS_PISOT_LADDER)
        self.assertTrue(all(v.fibonacci > 0 and v.lucas > 0 and v.padovan > 0 for v in values))

    def test_opencl_never_falls_back(self):
        try:
            OpenCLLadderExecutor()
        except GPUExecutionUnavailable:
            return
        self.skipTest("OpenCL device available; strict CI executes the device ladder")

    def test_device_selection_accepts_cpu_opencl(self):
        cl = SimpleNamespace(device_type=SimpleNamespace(CPU=1, GPU=2))
        cpu = SimpleNamespace(name="PoCL CPU", vendor="PoCL", type=1)
        with patch.dict("os.environ", {"HYBA_REQUIRE_HYBA": ""}):
            self.assertIs(_select_device(cl, [cpu]), cpu)

    def test_device_selection_prefers_gpu_over_cpu_opencl(self):
        cl = SimpleNamespace(device_type=SimpleNamespace(CPU=1, GPU=2))
        cpu = SimpleNamespace(name="PoCL CPU", vendor="PoCL", type=1)
        gpu = SimpleNamespace(name="Discrete GPU", vendor="Vendor", type=2)
        with patch.dict("os.environ", {"HYBA_REQUIRE_HYBA": ""}):
            self.assertIs(_select_device(cl, [cpu, gpu]), gpu)


if __name__ == "__main__":
    unittest.main()
