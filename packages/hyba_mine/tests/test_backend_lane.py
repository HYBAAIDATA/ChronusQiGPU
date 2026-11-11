# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""The backend chosen for this run (HYBA_MINE_BACKEND, HYBA_MINE_PREFER) runs, or fails closed.

CI sets both from the workflow_dispatch inputs (defaults: auto, ours). Locally they
default the same way, so this test always exercises the operator's option.
"""

import os
import unittest

import _support  # noqa: F401  (import paths)

from hyba_mine.bist import select_lane
from hyba_mine.igpu import ROUTE_METAL, ROUTE_MODE_A

LOCAL_LANES = ("auto", "igpu", "metal")


class TestChosenBackend(unittest.TestCase):
    def test_the_chosen_backend_runs_its_known_answers_or_fails_closed(self):
        backend = os.environ.get("HYBA_MINE_BACKEND", "auto")
        prefer = os.environ.get("HYBA_MINE_PREFER", "ours")
        full = os.environ.get("HYBA_MINE_FULL_WINDOW") == "1"
        route, lane, checks = select_lane(backend, prefer=prefer, mode_a_workers=1, full_window=full)
        try:
            failed = [f"{c.name}: {c.detail}" for c in checks if not c.passed]
            print(f"backend={backend} prefer={prefer} -> {route.to_dict() if route else None}")
            if backend in LOCAL_LANES:
                self.assertIsNotNone(route, failed)
                self.assertEqual(failed, [])
                self.assertIn(route.executed, (ROUTE_MODE_A, ROUTE_METAL))
                self.assertEqual(route.requested_backend, backend)
                self.assertEqual(route.preference, prefer)
                if backend == "auto" and prefer == "ours":
                    self.assertEqual(route.executed_backend, "igpu")
                if backend != "auto":
                    self.assertEqual(route.executed_backend, backend)
            else:
                self.assertIsNone(route)
                self.assertIn(f"{backend} lane present", [c.name for c in checks if not c.passed])
        finally:
            if lane is not None:
                lane.close()


if __name__ == "__main__":
    unittest.main()
