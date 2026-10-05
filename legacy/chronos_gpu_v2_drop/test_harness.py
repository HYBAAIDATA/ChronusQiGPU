# test_harness.py
# Chronos GPU -- Test harness v2.0 (audit fix, 3 Aug 2026)
#
# Fix vs v1.0: run_all_tests() printed "All tests passed (stub)" and
# unconditionally returned True -- it checked nothing. v2.0 actually runs
# the pipeline and asserts real invariants, and returns False (with a
# printed reason) if any check fails.

from __future__ import annotations

import numpy as np

from .engine import ChronosEngine


class ChronosTestHarness:
    def run_all_tests(self) -> bool:
        checks = []

        engine = ChronosEngine(n_faces=32, layers=4)
        r1 = engine.render("scene sunset { object sphere { material glass } light sun }")
        r2 = engine.render("scene sunset { object sphere { material glass } light sun }")

        checks.append(("energy is finite", np.isfinite(r1.energy)))
        checks.append(("energy is deterministic across repeated renders", r1.energy == r2.energy))
        checks.append(("frame shape matches requested 8K resolution", r1.frame_shape == (4320, 7680, 3)))
        checks.append(("distribution sums to 1", np.isclose(np.sum(r1.distribution), 1.0)))
        checks.append(("at least one pixel was actually rendered (not empty)", r1.rendered_pixels_hit > 0))
        checks.append((
            "rendered image is not a flat fill (background + shaded sphere differ)",
            r1.rendered_pixels_hit < r1.total_pixels,
        ))
        checks.append(("raster_compression_ratio is a real finite number", np.isfinite(r1.raster_compression_ratio)))

        all_passed = True
        for name, passed in checks:
            print(f"[{'PASS' if passed else 'FAIL'}] {name}")
            all_passed = all_passed and bool(passed)

        if all_passed:
            print("All tests passed (real checks, not a stub).")
        else:
            print("One or more tests FAILED -- see above.")
        return all_passed


if __name__ == "__main__":
    ChronosTestHarness().run_all_tests()
