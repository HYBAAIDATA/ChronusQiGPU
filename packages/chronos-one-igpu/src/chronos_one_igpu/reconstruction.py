# reconstruction.py
# Chronos GPU -- Reconstruction + PRISMA Integration v2.0 (audit fix, 3 Aug 2026)
#
# Fixes vs v1.0:
#   - The original top-level reconstruction_prisma.py broadcast a single
#     scalar to the entire frame buffer (a flat color swatch); src/chronos's
#     own stub just returned abs(state)**2 with no image at all. Neither
#     used the geometry, manifold faces, or per-face distribution to produce
#     spatially varying pixels.
#   - v2.0 ray-traces a simple pinhole camera against the scene's sphere and
#     shades each hit point using the manifold face nearest the surface
#     normal at that point, weighted by that face's amplitude from the
#     evolution engine's real per-face `distribution`. This produces a
#     genuine, spatially varying image driven by the computed state.
#   - `fold_ratio` (a hardcoded literal 11.5 in v1.0) is replaced by an
#     honestly computed `raster_compression_ratio`: parametric-state bytes
#     vs. rendered dense-frame bytes. This is ordinary procedural-vs-raster
#     compression, not a claim about quantum/tensor compression -- see
#     AUDIT_NOTES.md for why the original "PULVINI phi-fold (11.5x)" framing
#     does not apply to this system at all (there is no exponential qubit
#     Hilbert space here to compress; n is already the full dimension).

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Frame8K:
    rgb: np.ndarray
    depth: np.ndarray
    normal: np.ndarray
    metadata: Dict


class ReconstructionEngine:
    def __init__(self, resolution: Tuple[int, int] = (7680, 4320), face_positions: Optional[np.ndarray] = None):
        self.res = resolution  # (width, height)
        self.supersample_factor = 4
        self.face_positions = face_positions

    def _camera_rays(self, w: int, h: int, camera: Dict):
        position = np.array(camera.get("position", (0, 0, 5)), dtype=np.float64)
        fov = float(camera.get("fov", 60.0))
        forward = -position / (np.linalg.norm(position) + 1e-12)
        world_up = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, world_up)
        right = right / (np.linalg.norm(right) + 1e-12)
        up = np.cross(right, forward)
        half_h = np.tan(np.radians(fov) / 2.0)
        half_w = half_h * (w / h)
        xs = ((np.arange(w) + 0.5) / w * 2.0 - 1.0) * half_w
        ys = (1.0 - (np.arange(h) + 0.5) / h * 2.0) * half_h
        dirs = (
            forward[None, None, :]
            + xs[None, :, None] * right[None, None, :]
            + ys[:, None, None] * up[None, None, :]
        )
        dirs = dirs / np.linalg.norm(dirs, axis=-1, keepdims=True)
        return dirs, position

    @staticmethod
    def _ray_sphere(origin: np.ndarray, dirs_row: np.ndarray, center: np.ndarray, radius: float) -> np.ndarray:
        oc = origin - center
        b = 2.0 * (dirs_row @ oc)
        c = float(oc @ oc) - radius * radius
        disc = b * b - 4.0 * c
        hit = disc >= 0
        sq = np.sqrt(np.clip(disc, 0, None))
        t0 = (-b - sq) / 2.0
        t1 = (-b + sq) / 2.0
        tmin = np.where(t0 > 1e-6, t0, t1)
        valid = hit & (tmin > 1e-6)
        t = np.full(dirs_row.shape[0], np.inf)
        t[valid] = tmin[valid]
        return t

    def reconstruct(
        self,
        expectation_values: Dict[str, float],
        distribution: Optional[np.ndarray],
        camera_params: Dict,
        scene_objects: Optional[List[Dict]] = None,
    ) -> Frame8K:
        w, h = self.res
        rgb = np.zeros((h, w, 3), dtype=np.float32)
        depth = np.zeros((h, w), dtype=np.float32)
        normal = np.zeros((h, w, 3), dtype=np.float32)

        n_faces = 0 if self.face_positions is None else self.face_positions.shape[0]
        obj = (scene_objects or [None])[0]

        if n_faces > 0 and obj is not None:
            geom = obj.get("geometry", {})
            center = np.array(geom.get("center", (0, 0, 0)), dtype=np.float64)
            radius = float(geom.get("radius", 1.0))
            dirs, origin = self._camera_rays(w, h, camera_params)
            base_intensity = expectation_values.get("intensity", 0.5)
            if distribution is not None and len(distribution) == n_faces:
                dist = np.asarray(distribution, dtype=np.float64)
            else:
                dist = np.full(n_faces, 1.0 / n_faces)
            face_shading = dist * n_faces  # normalize so mean shading ~= 1.0

            for row in range(h):
                row_dirs = dirs[row]
                t = self._ray_sphere(origin, row_dirs, center, radius)
                hit = np.isfinite(t)
                if not np.any(hit):
                    continue
                # Only compute hit points/normals for rays that actually hit
                # the sphere -- t is +inf for misses, and propagating that
                # through the normal/matmul below produced spurious NaN
                # warnings (harmless, since results were masked out anyway,
                # but worth avoiding).
                hit_points = origin[None, :] + row_dirs[hit] * t[hit, None]
                normals = (hit_points - center) / max(radius, 1e-9)
                face_idx = np.argmax(normals @ self.face_positions.T, axis=1)
                shade = (base_intensity * face_shading[face_idx]).astype(np.float32)
                rgb[row, hit, 0] = shade
                rgb[row, hit, 1] = shade
                rgb[row, hit, 2] = shade
                depth[row, hit] = t[hit].astype(np.float32)
                normal[row, hit] = normals.astype(np.float32)
        else:
            # No scene geometry / manifold available: honestly report a flat
            # frame instead of fabricating detail we have no data for.
            intensity = expectation_values.get("intensity", 0.5)
            rgb[...] = intensity
            depth[...] = expectation_values.get("depth", 0.5)
            normal[...] = expectation_values.get("normal", 0.1)

        state_bytes = int(np.asarray(distribution).nbytes) if distribution is not None else 0
        dense_bytes = int(rgb.nbytes + depth.nbytes + normal.nbytes)
        raster_ratio = (dense_bytes / state_bytes) if state_bytes else float("nan")

        return Frame8K(
            rgb=rgb,
            depth=depth,
            normal=normal,
            metadata={
                "resolution": self.res,
                "supersampling": self.supersample_factor,
                "raster_compression_ratio": raster_ratio,
                "state_bytes": state_bytes,
                "dense_frame_bytes": dense_bytes,
                "energy": expectation_values.get("intensity", 0.0),
                "rendered_pixels_hit": int(np.count_nonzero(depth)),
            },
        )

    def tone_map(self, frame: Frame8K) -> np.ndarray:
        rgb = np.clip(frame.rgb, 0, None)
        rgb = rgb / (1 + rgb)
        rgb = np.clip(rgb ** (1 / 2.2), 0, 1)
        return rgb
