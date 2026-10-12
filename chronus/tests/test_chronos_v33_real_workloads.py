# test_chronos_v33_real_workloads.py
# Chronos GPU -- v3.2 composite elevation + reproducible benchmark protocol
# (5 Oct 2026). Runs standalone (python chronus/tests/test_chronos_v33_real_workloads.py)
# or under pytest.

import math
import sys
import unittest

import numpy as np

sys.path.insert(0, ".")

from chronus.v33.engine import ChronosEngine
from chronus.v33.qsdl_compiler import QSDLCompiler, ManifoldConfig
from chronus.v33.reconstruction import (
    ReconstructionEngine,
    intersect_object_rays,
    intersect_scene_nearest,
    is_composite_scene,
    numpy_ray_box,
    numpy_ray_plane,
)
from chronus.v33.benchmarks import claims as claim_mod
from chronus.v33.benchmarks import protocol
from chronus.v33.benchmarks import real_workloads as rw

O = np.array([0.0, 0.0, 0.0])


class BoxPlaneIntersectionTests(unittest.TestCase):
    def test_box_hit_front_face(self):
        dirs = np.array([[1.0, 0.0, 0.0]])
        t, hit = numpy_ray_box(O, dirs, np.array([3.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0]))
        self.assertTrue(bool(hit[0]))
        self.assertAlmostEqual(float(t[0]), 2.0, places=12)

    def test_box_miss(self):
        dirs = np.array([[0.0, 1.0, 0.0]])
        t, hit = numpy_ray_box(O, dirs, np.array([3.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0]))
        self.assertFalse(bool(hit[0]))

    def test_box_diagonal_entry(self):
        d = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
        t, hit = numpy_ray_box(O, d[None, :], np.array([3.0, 3.0, 3.0]), np.ones(3))
        self.assertTrue(bool(hit[0]))
        # normalized diagonal ray: entry at x=2 with d_x=1/sqrt(3) -> t=2*sqrt(3)
        self.assertAlmostEqual(float(t[0]), 2.0 * math.sqrt(3.0), places=12)

    def test_box_origin_inside_returns_exit(self):
        dirs = np.array([[1.0, 0.0, 0.0]])
        t, hit = numpy_ray_box(
            np.array([3.0, 0.0, 0.0]), dirs, np.array([3.0, 0.0, 0.0]), np.ones(3)
        )
        self.assertTrue(bool(hit[0]))
        self.assertAlmostEqual(float(t[0]), 1.0, places=12)

    def test_plane_hit_and_distance(self):
        dirs = np.array([[0.0, -1.0, 0.0]])
        t, hit = numpy_ray_plane(np.array([0.0, 5.0, 0.0]), dirs, np.array([0.0, 1.0, 0.0]), 0.0)
        self.assertTrue(bool(hit[0]))
        self.assertAlmostEqual(float(t[0]), 5.0, places=12)

    def test_plane_parallel_miss(self):
        dirs = np.array([[1.0, 0.0, 0.0]])
        _t, hit = numpy_ray_plane(np.array([0.0, 5.0, 0.0]), dirs, np.array([0.0, 1.0, 0.0]), 0.0)
        self.assertFalse(bool(hit[0]))


class CompositionTests(unittest.TestCase):
    def _obj(self, gtype, **geom):
        return {"name": "o", "geometry": {"type": gtype, **geom}, "material": {}}

    def test_nearest_hit_prefers_closer_object(self):
        near = self._obj("sphere", center=(0, 0, 2), radius=0.5)
        far = self._obj("sphere", center=(0, 0, 8), radius=0.5)
        dirs = np.array([[0.0, 0.0, 1.0]])
        t, hit, normals = intersect_scene_nearest(O, dirs, [far, near])
        self.assertTrue(bool(hit[0]))
        self.assertAlmostEqual(float(t[0]), 1.5, places=12)

    def test_nearest_hit_beats_object_order(self):
        near = self._obj("sphere", center=(0, 0, 2), radius=0.5)
        far = self._obj("sphere", center=(0, 0, 8), radius=0.5)
        dirs = np.array([[0.0, 0.0, 1.0]])
        t1, _, _ = intersect_scene_nearest(O, dirs, [far, near])
        t2, _, _ = intersect_scene_nearest(O, dirs, [near, far])
        self.assertAlmostEqual(float(t1[0]), float(t2[0]), places=12)

    def test_box_normal_opposes_ray_on_entry(self):
        box = self._obj("box", center=(3, 0, 0), extents=(1, 1, 1))
        dirs = np.array([[1.0, 0.0, 0.0]])
        _t, hit, normals = intersect_object_rays(O, dirs, box)
        self.assertTrue(bool(hit[0]))
        np.testing.assert_allclose(normals[0], [-1.0, 0.0, 0.0], atol=1e-12)

    def test_mesh_procedural_fail_closed(self):
        mesh = self._obj("mesh")
        dirs = np.array([[0.0, 0.0, 1.0]])
        _t, hit, _n = intersect_object_rays(O, dirs, mesh)
        self.assertFalse(bool(hit[0]))

    def test_single_sphere_is_not_composite(self):
        self.assertFalse(is_composite_scene([self._obj("sphere", center=(0, 0, 0), radius=1)]))
        self.assertTrue(is_composite_scene([self._obj("sphere", center=(0, 0, 0), radius=1)] * 2))
        self.assertTrue(is_composite_scene([self._obj("box", center=(0, 0, 0), extents=(1, 1, 1))]))
        self.assertFalse(is_composite_scene(None))

    def test_composite_frame_nearest_hit(self):
        lib_faces = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        recon = ReconstructionEngine(resolution=(64, 48), face_positions=lib_faces, block_rows=16)
        near = self._obj("sphere", center=(0, 0, -4), radius=0.9)
        far = self._obj("sphere", center=(0, 0, -40), radius=0.9)
        frame = recon.reconstruct(
            {"intensity": 1.0},
            np.array([0.5, 0.3, 0.2]),
            {"resolution": (64, 48), "fov": 60.0, "position": (0, 0, 5)},
            scene_objects=[far, near],
        )
        self.assertGreater(frame.metadata["rendered_pixels_hit"], 0)
        self.assertEqual(frame.metadata["render_backend"]["composition"], "nearest_hit")
        self.assertEqual(frame.metadata["render_backend"]["objects_composited"], 2)
        # every hit is the near sphere: depth well below the far sphere's 39.1
        depth = frame.depth[frame.depth > 0]
        self.assertTrue(bool(np.all(depth < 15.0)))


class EngineEndToEndTests(unittest.TestCase):
    TINY_STUDIO = rw.STUDIO_COMPOSITE_SOURCE.replace(
        "resolution=(7680,4320)", "resolution=(320,180)"
    )

    def test_studio_scene_renders_all_geometry_types(self):
        engine = ChronosEngine(n_faces=32, layers=4)
        result = engine.render(self.TINY_STUDIO)
        self.assertGreater(result.rendered_pixels_hit, 0)
        self.assertEqual(
            result.render_backend["geometry_types"],
            ["box", "plane", "sphere"],
        )
        self.assertTrue(math.isfinite(result.energy))

    def test_supersampling_on_composite(self):
        source = self.TINY_STUDIO.replace(
            "observables = [intensity, depth, normal]",
            "observables = [intensity, depth, normal] supersampling = 4",
        )
        engine = ChronosEngine(n_faces=32, layers=4)
        result = engine.render(source)
        self.assertEqual(result.samples_per_pixel, 4)
        self.assertGreater(result.rendered_pixels_hit, 0)

    def test_all_registry_workloads_compile(self):
        compiler = QSDLCompiler(ManifoldConfig(n_faces=32))
        for spec in rw.REAL_WORKLOADS:
            tiny = spec.qsdl_source.replace("resolution=(7680,4320)", "resolution=(64,48)")
            scene = compiler.compile(tiny)
            self.assertGreaterEqual(len(scene.objects), 1)
            self.assertGreaterEqual(len(scene.lights), 1)


class ProtocolTests(unittest.TestCase):
    def test_environment_capture_keys(self):
        env = protocol.capture_environment(host_label="elevation-host")
        for key in ("platform", "python", "numpy", "cpu_count", "utc_timestamp"):
            self.assertIn(key, env)
        self.assertEqual(env["host_label"], "elevation-host")
        self.assertEqual(env["protocol_version"], protocol.PROTOCOL_VERSION)

    def test_measure_statistics(self):
        counter = {"n": 0}

        def fn():
            counter["n"] += 1
            return counter["n"]

        stats = protocol.measure(fn, repetitions=4, warmup=1)
        self.assertTrue(stats["measured"])
        self.assertEqual(len(stats["samples_seconds"]), 4)
        self.assertEqual(stats["repetitions"], 4)
        self.assertFalse(stats["single_sample"])
        self.assertLessEqual(stats["min_seconds"], stats["median_seconds"])
        self.assertGreaterEqual(stats["max_seconds"], stats["median_seconds"])
        # warmup ran but is not counted in samples
        self.assertEqual(counter["n"], 5)

    def test_nan_guard(self):
        guarded = protocol.nan_guard(float("nan"), "reason")
        self.assertFalse(guarded["measured"])
        self.assertEqual(guarded["reason"], "reason")
        ok = protocol.nan_guard(3.14, "reason")
        self.assertTrue(ok["measured"])
        self.assertAlmostEqual(ok["value"], 3.14)


class ClaimLedgerTests(unittest.TestCase):
    def test_ledger_covers_all_three_states(self):
        ledger = claim_mod.evaluate()
        statuses = {row["status"] for row in ledger["claims"]}
        self.assertEqual(statuses, {"MEASURED", "GATED", "UNMEASURED"})
        self.assertIn("frame-time-8k", {r["claim_id"] for r in ledger["claims"]})
        # the headline frame-time claim must never read MEASURED from a
        # CPU-only artifact
        for row in ledger["claims"]:
            if row["claim_id"] == "frame-time-8k":
                self.assertEqual(row["status"], "GATED")

    def test_every_claim_names_its_evidence(self):
        for claim in claim_mod.LEDGER:
            self.assertTrue(claim.evidence_path)
            self.assertTrue(claim.current_best)
            if claim.status in ("MEASURED", "GATED"):
                self.assertTrue(claim.evidence_reader)


if __name__ == "__main__":
    unittest.main()
