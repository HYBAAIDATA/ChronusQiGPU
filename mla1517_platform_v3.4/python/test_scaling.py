import unittest
from mla1517.scaling import (
    LUCAS_PISOT_LADDER,
    exact_ladder,
    GPUExecutionUnavailable,
    OpenCLLadderExecutor,
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


if __name__ == "__main__":
    unittest.main()
