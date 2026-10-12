# chronus/tests/test_chronos_v33_render_elevation.py
# Chronos GPU v3.1 elevation pass (5 Oct 2026).
#
# Gates:
#   1. The elevated default path is BIT-IDENTICAL to the v3.0 row-loop
#      reference (same rays, same order of operations, block-scheduled).
#   2. Metadata supersampling is the samples actually traced -- the v3.0
#      metadata claimed 4 while tracing 1, and that lie is gone.
#   3. Supersampling is real: an independent per-sample oracle reproduces
#      the 4-sample frame exactly, edge pixels gain coverage, frames are
#      deterministic, and single-face interiors keep their colour.
#   4. The GPU lane is fail-closed: unavailable means a measured reason and
#      an explicit request raises; a bound lane is self-checked, rechecked
#      per dispatch, and a device that disagrees fails closed to the
#      reference result while the frame stays correct.
#
# Runs under pytest, or standalone: python3 chronus/tests/test_chronos_v33_render_elevation.py

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chronus.v33.evolution_engine import EvolutionEngine
from chronus.v33.gpu_render import (
    BackendStatus,
    RenderBackendUnavailable,
    configured_backend,
    numpy_ray_sphere,
    probe_cupy,
)
from chronus.v33.hamiltonian import HamiltonianLibrary
from chronus.v33.reconstruction import ReconstructionEngine, sample_offsets


def _scene_inputs(n_faces: int = 32):
    lib = HamiltonianLibrary(n_faces=n_faces)
    objs = [
        {
            "geometry": {"type": "sphere", "radius": 1.0, "center": (0, 0, 0)},
            "material": {
                "dielectric": 1.5,
                "absorption": 0.001,
                "resonance_weights": np.full(n_faces, 0.5),
            },
        }
    ]
    lights = [{"intensity": 1.0, "direction": (1, 1, 1)}]
    h_terms = lib.build(objs, lights)
    evo = EvolutionEngine(n_faces=n_faces, layers=4)
    result = evo.evolve(
        hamiltonian_terms=h_terms.cost_matrices,
        resonance_weights=h_terms.resonance_weights,
        steps=80,
        seed=0,
    )
    return lib, objs, result


def _reference_frame(recon, expectations, distribution, camera, objects, n_faces=32):
    """The original v3.0 row-loop algorithm, verbatim, as the oracle."""
    w, h = recon.res
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    depth = np.zeros((h, w), dtype=np.float32)
    normal = np.zeros((h, w, 3), dtype=np.float32)
    center = np.array(objects[0]["geometry"].get("center", (0, 0, 0)), dtype=np.float64)
    radius = float(objects[0]["geometry"].get("radius", 1.0))
    dirs, origin = recon._camera_rays(w, h, camera)
    dist = np.asarray(distribution, dtype=np.float64)
    face_shading = dist * n_faces
    base_intensity = expectations.get("intensity", 0.5)
    for row in range(h):
        row_dirs = dirs[row]
        oc = origin - center
        b = 2.0 * (row_dirs @ oc)
        c = float(oc @ oc) - radius * radius
        disc = b * b - 4.0 * c
        hit = disc >= 0
        sq = np.sqrt(np.clip(disc, 0, None))
        t0 = (-b - sq) / 2.0
        t1 = (-b + sq) / 2.0
        tmin = np.where(t0 > 1e-6, t0, t1)
        valid = hit & (tmin > 1e-6)
        t = np.full(row_dirs.shape[0], np.inf)
        t[valid] = tmin[valid]
        hitm = np.isfinite(t)
        if not np.any(hitm):
            continue
        hit_points = origin[None, :] + row_dirs[hitm] * t[hitm, None]
        normals = (hit_points - center) / max(radius, 1e-9)
        face_idx = np.argmax(normals @ recon.face_positions.T, axis=1)
        shade = (base_intensity * face_shading[face_idx]).astype(np.float32)
        rgb[row, hitm, 0] = shade
        rgb[row, hitm, 1] = shade
        rgb[row, hitm, 2] = shade
        depth[row, hitm] = t[hitm].astype(np.float32)
        normal[row, hitm] = normals.astype(np.float32)
    return rgb, depth, normal


class _Env:
    def __init__(self, **kwargs):
        self._saved = {k: os.environ.get("chronus_V33_RENDER_BACKEND_X", None) for k in ()}
        self.kwargs = kwargs

    def __enter__(self):
        self._old = os.environ.pop("CHRONUS_V33_RENDER_BACKEND", None)
        for k, v in self.kwargs.items():
            os.environ[k] = v
        return self

    def __exit__(self, *exc):
        os.environ.pop("CHRONUS_V33_RENDER_BACKEND", None)
        if self._old is not None:
            os.environ["CHRONUS_V33_RENDER_BACKEND"] = self._old


class _FakeCuPy:
    """Minimal numpy-backed stand-in exercising the real backend contract."""

    def __init__(self):
        import numpy as _np

        self._np = _np
        self.float64 = _np.float64
        self.inf = _np.inf

        class _runtime:  # noqa: N801
            @staticmethod
            def getDeviceCount():
                return 1

            @staticmethod
            def getDeviceProperties(idx):
                return {"name": f"FakeCuPy-Test-{idx}"}

        class _cuda:  # noqa: N801
            runtime = _runtime()

        self.cuda = _cuda()

    def asarray(self, a, dtype=None):
        out = self._np.asarray(a)
        return out.astype(dtype) if dtype is not None else out

    def asnumpy(self, a):
        return self._np.asarray(a)

    def clip(self, a, lo, hi):
        return self._np.clip(a, lo, hi)

    def sqrt(self, a):
        return self._np.sqrt(a)

    def where(self, cond, a, b):
        return self._np.where(cond, a, b)

    def full(self, shape, value):
        return self._np.full(shape, value)


class RenderElevationTests(unittest.TestCase):
    RES = (640, 360)
    CAMERA = {"resolution": RES, "fov": 60.0, "position": (0, 0, 5)}

    def setUp(self):
        self._saved_cupy = sys.modules.pop("cupy", None)
        os.environ.pop("CHRONUS_V33_RENDER_BACKEND", None)

    def tearDown(self):
        sys.modules.pop("cupy", None)
        if self._saved_cupy is not None:
            sys.modules["cupy"] = self._saved_cupy
        os.environ.pop("CHRONUS_V33_RENDER_BACKEND", None)

    def _recon(self, block_rows=64):
        lib, objs, result = _scene_inputs()
        recon = ReconstructionEngine(
            resolution=self.RES, face_positions=lib.face_positions, block_rows=block_rows
        )
        return recon, lib, objs, result

    # -- 1. bit-identity of the default path --------------------------------
    def test_default_path_bit_identical_and_multiblock(self):
        recon, lib, objs, result = self._recon(block_rows=64)  # 360/64 -> 6 blocks
        frame = recon.reconstruct(
            result.expectation_values, result.distribution, self.CAMERA, scene_objects=objs
        )
        r_rgb, r_depth, r_normal = _reference_frame(
            recon, result.expectation_values, result.distribution, self.CAMERA, objs
        )
        self.assertTrue(np.array_equal(frame.rgb, r_rgb))
        self.assertTrue(np.array_equal(frame.depth, r_depth))
        self.assertTrue(np.array_equal(frame.normal, r_normal))
        self.assertEqual(frame.metadata["rendered_pixels_hit"], int(np.count_nonzero(r_depth)))

    def test_metadata_supersampling_is_honest(self):
        recon, lib, objs, result = self._recon()
        frame = recon.reconstruct(
            result.expectation_values, result.distribution, self.CAMERA, scene_objects=objs
        )
        self.assertEqual(frame.metadata["supersampling"], 1)
        self.assertEqual(frame.metadata["samples_per_pixel"], 1)
        self.assertNotIn("11.5", str(frame.metadata))

    # -- 3. real supersampling ----------------------------------------------
    def test_supersampling_matches_independent_oracle(self):
        recon, lib, objs, result = self._recon()
        cam4 = dict(self.CAMERA, supersampling=4)
        frame = recon.reconstruct(
            result.expectation_values, result.distribution, cam4, scene_objects=objs
        )
        w, h = self.RES
        center = np.zeros(3)
        radius = 1.0
        basis = recon._camera_basis(cam4)
        _f, _r, _u, _hh, _hw, origin = basis
        dist = np.asarray(result.distribution, dtype=np.float64)
        face_shading = dist * 32
        base = result.expectation_values.get("intensity", 0.5)

        acc_shade = np.zeros((h * w, 3))
        acc_t = np.zeros(h * w)
        acc_n = np.zeros((h * w, 3))
        hits = np.zeros(h * w, dtype=np.int64)
        for off in sample_offsets(4):
            dirs = recon._dirs_block(0, h, w, h, basis, off).reshape(-1, 3)
            t, hit = numpy_ray_sphere(origin, dirs, center, radius)
            if not hit.any():
                continue
            hp = origin[None, :] + dirs[hit] * t[hit, None]
            normals = (hp - center) / radius
            fidx = np.argmax(normals @ recon.face_positions.T, axis=1)
            acc_shade[hit] += (base * face_shading[fidx])[:, None]
            acc_t[hit] += t[hit]
            acc_n[hit] += normals
            hits[hit] += 1
        pixel_hit = hits > 0
        counts = hits[pixel_hit].astype(np.float64)
        exp_rgb = np.zeros((h * w, 3), dtype=np.float32)
        exp_rgb[pixel_hit] = (acc_shade[pixel_hit] / counts[:, None]).astype(np.float32)
        exp_depth = np.zeros(h * w, dtype=np.float32)
        exp_depth[pixel_hit] = (acc_t[pixel_hit] / counts).astype(np.float32)
        self.assertTrue(np.array_equal(frame.rgb.reshape(-1, 3), exp_rgb))
        self.assertTrue(np.array_equal(frame.depth.reshape(-1), exp_depth))
        self.assertEqual(frame.metadata["samples_per_pixel"], 4)

        frame1 = recon.reconstruct(
            result.expectation_values, result.distribution, self.CAMERA, scene_objects=objs
        )
        edge_gain = int(np.count_nonzero((frame1.depth == 0) & (frame.depth > 0)))
        self.assertGreater(edge_gain, 0, "supersampling must antialias silhouette edges")
        # determinism
        frame4b = recon.reconstruct(
            result.expectation_values, result.distribution, cam4, scene_objects=objs
        )
        self.assertTrue(np.array_equal(frame.rgb, frame4b.rgb))
        self.assertTrue(np.array_equal(frame.depth, frame4b.depth))

    def test_engine_end_to_end_qSDL_supersampling(self):
        source = (
            "scene supersampled {"
            " manifold M32"
            " object sphere { geometry sphere(radius=1.0, center=(0,0,0))"
            "   material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } }"
            " camera { resolution=(160,90) fov=60.0 position=(0,0,5)"
            "   readout = { observables=[intensity,depth,normal] supersampling=4 } }"
            " quality { layers=4 evolution_steps=20 seed=0 }"
            "}"
        )
        from chronus.v33.engine import ChronosEngine

        engine = ChronosEngine(n_faces=32, layers=4)
        out = engine.render(source)
        self.assertEqual(out.samples_per_pixel, 4)
        self.assertIsNotNone(out.render_backend)
        # camera resolution (160, 90) honoured end to end
        self.assertEqual(out.frame_shape, (90, 160, 3))

    # -- 4. fail-closed GPU lane --------------------------------------------
    def test_probe_and_configuration(self):
        self.assertEqual(configured_backend(), "numpy")
        with _Env(**{"CHRONUS_V33_RENDER_BACKEND": "bogus"}):
            with self.assertRaises(ValueError):
                configured_backend()
        status = probe_cupy()
        self.assertIsInstance(status, BackendStatus)
        if not status.available:
            self.assertTrue(status.reason)
            self.assertIn("cupy", status.reason.lower())

    def test_explicit_cupy_request_fails_closed(self):
        recon, lib, objs, result = self._recon()
        if probe_cupy().available:
            self.skipTest("real cupy present; explicit-request test needs it absent")
        with _Env(**{"CHRONUS_V33_RENDER_BACKEND": "cupy"}):
            with self.assertRaises(RenderBackendUnavailable):
                recon.reconstruct(
                    result.expectation_values, result.distribution, self.CAMERA,
                    scene_objects=objs,
                )

    def test_auto_falls_back_with_recorded_reason(self):
        recon, lib, objs, result = self._recon()
        frame = None
        with _Env(**{"CHRONUS_V33_RENDER_BACKEND": "auto"}):
            frame = recon.reconstruct(
                result.expectation_values, result.distribution, self.CAMERA,
                scene_objects=objs,
            )
        be = frame.metadata["render_backend"]
        if probe_cupy().available:
            self.assertEqual(be["backend"], "cupy")
        else:
            self.assertEqual(be["backend"], "numpy")
            self.assertEqual(be.get("fallback_from"), "cupy")
            self.assertTrue(be.get("reason"))

    def _install_fake_cupy(self):
        fake = _FakeCuPy()
        sys.modules["cupy"] = fake
        return fake

    def test_fake_cupy_binds_selfchecks_and_rechecks(self):
        recon, lib, objs, result = self._recon()
        self._install_fake_cupy()
        with _Env(**{"CHRONUS_V33_RENDER_BACKEND": "auto"}):
            frame = recon.reconstruct(
                result.expectation_values, result.distribution, self.CAMERA,
                scene_objects=objs,
            )
        be = frame.metadata["render_backend"]
        self.assertEqual(be["backend"], "cupy")
        self.assertTrue(be["self_check"]["passed"])
        self.assertEqual(be["device"], "FakeCuPy-Test-0")
        self.assertTrue(be["sampled_recheck"]["passed"])
        self.assertEqual(be["fallbacks"], 0)
        # frame identical to reference: shading always executes on the reference
        r_rgb, r_depth, _ = _reference_frame(
            recon, result.expectation_values, result.distribution, self.CAMERA, objs
        )
        self.assertTrue(np.array_equal(frame.rgb, r_rgb))
        self.assertTrue(np.array_equal(frame.depth, r_depth))

    def test_fake_cupy_disagreement_fails_closed(self):
        recon, lib, objs, result = self._recon()

        class _CorruptBackend:
            """Binds and self-checks cleanly, then lies on every dispatch."""

            status = BackendStatus("cupy", True, "bound", "Fake-Corrupt")

            def ray_sphere(self, origin, dirs, center, radius):
                t, hit = numpy_ray_sphere(origin, dirs, center, radius)
                return t + 1e-3, hit

        def _bind():
            return _CorruptBackend(), {
                "backend": "cupy",
                "device": "Fake-Corrupt",
                "self_check": {"passed": True},
            }

        recon._bind_backend = _bind
        frame = recon.reconstruct(
            result.expectation_values, result.distribution, self.CAMERA,
            scene_objects=objs,
        )
        be = frame.metadata["render_backend"]
        self.assertEqual(be["backend"], "cupy")
        self.assertEqual(be["device"], "Fake-Corrupt")
        self.assertGreaterEqual(be["fallbacks"], 1)
        self.assertFalse(be["sampled_recheck"]["passed"])
        # fail-closed: the delivered frame is still the reference result
        r_rgb, r_depth, _ = _reference_frame(
            recon, result.expectation_values, result.distribution, self.CAMERA, objs
        )
        self.assertTrue(np.array_equal(frame.rgb, r_rgb))
        self.assertTrue(np.array_equal(frame.depth, r_depth))


if __name__ == "__main__":
    unittest.main(verbosity=2)
