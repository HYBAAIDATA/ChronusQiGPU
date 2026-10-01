# test_harness.py
# Chronos GPU -- Test harness v3.0 (elevated, 4 Aug 2026)
#
# History:
#   v1.0 printed "All tests passed (stub)" and always returned True.
#   v2.0 ran the real pipeline at hardcoded 8K and asserted real invariants.
#   v3.0 (this pass): configurable resolution (default 320x180 for CI/sandbox
#   so the suite finishes in seconds and does not OOM), plus separate
#   optional high-resolution path. Same invariants, no silent stubs.

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .engine import ChronosEngine


_DEFAULT_SMOKE_RESOLUTION = (320, 180)


def _scene_source(resolution: Tuple[int, int]) -> str:
    w, h = resolution
    return (
        "scene sunset { "
        f"object sphere {{ geometry sphere(radius=1.0, center=(0,0,0)) "
        "material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } } "
        "light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() } "
        f"camera {{ resolution=({w},{h}) fov=60.0 position=(0,0,5) }} "
        "}"
    )


class ChronosTestHarness:
    """Real end-to-end invariant checks against ChronosEngine.render().

    Parameters
    ----------
    resolution:
        Camera resolution (width, height). Defaults to a small smoke
        resolution so the harness is safe for CI and constrained sandboxes.
        Pass (7680, 4320) for the historical full-8K check.
    n_faces / layers:
        Manifold size and variational-layer count forwarded to ChronosEngine.
    """

    def __init__(
        self,
        resolution: Optional[Tuple[int, int]] = None,
        n_faces: int = 32,
        layers: int = 4,
    ):
        self.resolution = resolution or _DEFAULT_SMOKE_RESOLUTION
        self.n_faces = n_faces
        self.layers = layers

    def run_all_tests(self) -> bool:
        checks = []
        engine = ChronosEngine(n_faces=self.n_faces, layers=self.layers)
        scene_source = _scene_source(self.resolution)
        r1 = engine.render(scene_source)
        r2 = engine.render(scene_source)

        w, h = self.resolution
        checks.append(("energy is finite", np.isfinite(r1.energy)))
        checks.append(("energy is deterministic across repeated renders", r1.energy == r2.energy))
        checks.append(
            (
                f"frame shape matches requested resolution ({h},{w},3)",
                r1.frame_shape == (h, w, 3),
            )
        )
        checks.append(("distribution sums to 1", np.isclose(np.sum(r1.distribution), 1.0)))
        checks.append(("at least one pixel was actually rendered (not empty)", r1.rendered_pixels_hit > 0))
        checks.append(
            (
                "rendered image is not a flat fill (background + shaded sphere differ)",
                r1.rendered_pixels_hit < r1.total_pixels,
            )
        )
        checks.append(
            ("raster_compression_ratio is a real finite number", np.isfinite(r1.raster_compression_ratio))
        )

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
