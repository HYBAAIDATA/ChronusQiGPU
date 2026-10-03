"""Capability matrix: stages are earned by executable evidence only."""
from __future__ import annotations

import unittest

from euclid.capability_matrix import STAGES, generate_matrix


class TestCapabilityMatrix(unittest.TestCase):
    def test_matrix_generates_with_executable_stages(self) -> None:
        matrix = generate_matrix()
        self.assertEqual(matrix["schema"], "euclid.capability-matrix/1")
        capabilities = matrix["capabilities"]
        # the wired capabilities must clear the middle of the ladder
        self.assertGreaterEqual(
            STAGES.index(capabilities["cognition-loop"]["stage"]),
            STAGES.index("PERSISTED"),
        )
        self.assertEqual(
            capabilities["cross-problem-transfer"]["stage"], "HELD_OUT_TESTED"
        )
        self.assertEqual(
            capabilities["persistence-replay"]["stage"], "REPLAYED"
        )
        # every claimed stage carries probe evidence
        for name, cap in capabilities.items():
            self.assertTrue(cap["evidence"], name)
            self.assertEqual(cap["stage_index"], STAGES.index(cap["stage"]))


if __name__ == "__main__":
    unittest.main()
