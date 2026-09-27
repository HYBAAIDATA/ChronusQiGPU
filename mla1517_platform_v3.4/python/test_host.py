import unittest
from mla1517.host import HostGPUPlan, execute_reference


class HostGPUTests(unittest.TestCase):
    def test_overlay_plan_is_complete_and_deterministic(self):
        plan = HostGPUPlan(101, 8, mode="host_gpu_overlay")
        plan.validate()
        self.assertEqual(plan.tiles()[0].start, 0)
        self.assertEqual(plan.tiles()[-1].end, 101)
        self.assertEqual(sum(t.end - t.start for t in plan.tiles()), 101)
        self.assertEqual(plan.manifest(), plan.manifest())

    def test_cpu_fallback_matches_kernel(self):
        plan = HostGPUPlan(32, 5)
        self.assertEqual(
            execute_reference(range(32), plan, lambda x: x * x), [x * x for x in range(32)]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
