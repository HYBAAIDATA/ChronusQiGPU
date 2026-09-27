import json
import unittest
from pathlib import Path


class HardwareContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (Path(__file__).parents[1] / "hardware" / "mla1517_igpu_v1.json").read_text()
        )

    def test_topology(self):
        topology = self.contract["topology"]
        self.assertEqual(topology["warp_width"], 32)
        self.assertEqual(topology["logical_partitions"], 32)
        self.assertEqual(topology["icosahedral_execution_nodes"], 12)
        self.assertEqual(topology["dodecahedral_memory_nodes"], 20)

    def test_eleven_d_state(self):
        state = self.contract["state_model"]
        self.assertEqual(state["dimensions"], 11)
        self.assertEqual(len(state["axes"]), 11)
        self.assertEqual(state["hot_transport_descriptor_bytes"], 64)

    def test_progressive_pipeline(self):
        pipeline = self.contract["execution_pipeline"]
        self.assertLess(pipeline.index("D5_zeckendorf_void_test"), pipeline.index("D3_pisot_fold"))
        self.assertLess(pipeline.index("D3_pisot_fold"), pipeline.index("D10_cassini_verify"))
        self.assertLess(pipeline.index("D10_cassini_verify"), pipeline.index("D8_route_to_aethel"))

    def test_all_native_workloads_are_declared(self):
        self.assertEqual(
            set(self.contract["deployment"]["native_container_workloads"]),
            {"mathematical", "structured_mining", "simt_warp"},
        )

    def test_difficulty_and_units(self):
        difficulty = self.contract["difficulty"]
        self.assertIn("MLA1517_DIFFICULTY_BITS", difficulty["runtime_controls"])
        units = self.contract["execution_units"]
        self.assertEqual(units["warp_ballot"], "32-bit acceptance mask")
        self.assertEqual(units["integrity_unit"], "cassini_determinant_seal")


if __name__ == "__main__":
    unittest.main(verbosity=2)
