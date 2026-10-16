"""Unified HYBA manifold hashing device.

This coordinator composes, without duplicating, the 32-face compass, the 11D
Poincare-golden fold, the Cassini shard permutation, the four-layer grind, and
the OpenCL fail-closed boundary. The honest claim boundary is that geometry
only orders and shards probes; consensus double-SHA256 remains the sole
proof-of-work acceptance authority, with no nonce prediction or advantage
asserted.
"""

# LUCAS WIRING: coordinator
# Substrate route: gap

from __future__ import annotations

import hashlib
import os
import struct
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
from hyba.device import describe, is_hyba_name, require_hyba

try:
    from .four_layer_stack import FourLayerMiningStack
    from .poincare_cassini_search import DIM, GOLDEN_WEIGHTS, DodecaIcosahedron32
    from .poincare_golden_11d import (
        compute_poincare_norm_sq,
        compute_zeckendorf_certificate,
        fold_poincare_11d_vector,
        unfold_poincare_11d_vector,
    )
    from .search_crystal import UINT32_SPACE, cassini_permutation, partition_interval
except ImportError:  # pragma: no cover - top-level script use
    from four_layer_stack import FourLayerMiningStack
    from poincare_cassini_search import DIM, GOLDEN_WEIGHTS, DodecaIcosahedron32
    from poincare_golden_11d import (
        compute_poincare_norm_sq,
        compute_zeckendorf_certificate,
        fold_poincare_11d_vector,
        unfold_poincare_11d_vector,
    )
    from search_crystal import UINT32_SPACE, cassini_permutation, partition_interval

_PYTHON_ROOT = Path(__file__).resolve().parents[1] / "mla1517_platform_v3.4" / "python"
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from mla1517.mining.opencl_driver import OpenCLDriver, OpenCLExecutionResult
from mla1517.mining.pow import check_pow, sha256d

DEVICE_ID = "unified_hyba_manifold_device"
CLAIM_BOUNDARY = (
    "The 32-face compass and 11D Poincaré-golden manifold are a probe-ordering / "
    "sharding front-end only. sha256d(header80) <= negotiated target is the sole accept "
    "authority; no nonce prediction, nonce-probability shift, or proof-of-work advantage "
    "is asserted."
)
HARDWARE_NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class ManifoldFoldRecord:
    header_vector_11d: Tuple[float, ...]
    folded_11d: Tuple[float, ...]
    folded_norm_sq: float
    unfolded_11d: Tuple[float, ...]
    roundtrip_max_abs_error: float
    reflections: int
    zeckendorf_token: str
    truth_class: str = "mathematical"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header_vector_11d": list(self.header_vector_11d),
            "folded_11d": list(self.folded_11d),
            "folded_norm_sq": self.folded_norm_sq,
            "unfolded_11d": list(self.unfolded_11d),
            "roundtrip_max_abs_error": self.roundtrip_max_abs_error,
            "reflections": self.reflections,
            "zeckendorf_token": self.zeckendorf_token,
            "truth_class": self.truth_class,
        }


@dataclass(frozen=True)
class ManifoldShardOrder:
    nonce_start: int
    nonce_space: int
    face_order: Tuple[int, ...]
    shards: Tuple[Tuple[int, int], ...]
    strides: Tuple[int, ...]
    origins: Tuple[int, ...]
    faces_pruned: int = 0
    schedule_digest: str = ""
    truth_class: str = "computational"
    _seed: int = field(default=0, repr=False, compare=False)

    def iter_nonces(self) -> Iterator[int]:
        schedules = []
        for face_id in self.face_order:
            start, stop = self.shards[face_id]
            width = stop - start
            if width:
                schedules.append((face_id, start, cassini_permutation(width, face_id, self._seed)))

        positions = [0] * len(schedules)
        active = len(schedules)
        while active:
            next_active = 0
            for index, (_face_id, start, schedule) in enumerate(schedules):
                position = positions[index]
                if position >= len(schedule):
                    continue
                yield start + schedule.offset_at(position)
                positions[index] = position + 1
                if positions[index] < len(schedule):
                    next_active += 1
            active = next_active

    def first(self, n: int) -> List[int]:
        if n <= 0:
            return []
        result: List[int] = []
        for nonce in self.iter_nonces():
            result.append(nonce)
            if len(result) >= n:
                break
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nonce_start": self.nonce_start,
            "nonce_space": self.nonce_space,
            "face_order": list(self.face_order),
            "shards": [list(shard) for shard in self.shards],
            "strides": list(self.strides),
            "origins": list(self.origins),
            "faces_pruned": self.faces_pruned,
            "schedule_digest": self.schedule_digest,
            "truth_class": self.truth_class,
            "coverage_complete": True,
        }


class UnifiedManifoldHashingDevice:
    def __init__(
        self,
        nonce_space: int = 1 << 20,
        nonce_start: int = 0,
        *,
        compass: Optional[DodecaIcosahedron32] = None,
        opencl_driver: Optional[OpenCLDriver] = None,
        stack: Optional[FourLayerMiningStack] = None,
        n_qubits: int = 10000,
    ):
        nonce_space = int(nonce_space)
        nonce_start = int(nonce_start)
        if nonce_space < 1:
            raise ValueError("nonce_space must be positive")
        if nonce_start < 0 or nonce_start + nonce_space > UINT32_SPACE:
            raise ValueError("nonce interval must fit inside the uint32 space")
        self.nonce_space = nonce_space
        self.nonce_start = nonce_start
        self.compass = compass or DodecaIcosahedron32()
        self.driver = opencl_driver or OpenCLDriver()
        self.stack = stack or FourLayerMiningStack(n_qubits=n_qubits)
        self.shards = partition_interval(nonce_start, nonce_space, len(self.compass))
        self.hyba_devices = tuple(
            device for device in self.driver.devices if is_hyba_name(device.name)
        )

    @property
    def hardware_available(self) -> bool:
        return self.driver.available and (bool(self.hyba_devices) or not require_hyba())

    def header_vector(self, header80: bytes) -> np.ndarray:
        digest = hashlib.sha256(header80[:76]).digest()
        raw = [(digest[index] - 127.5) / 127.5 for index in range(DIM)]
        return np.asarray(raw, dtype=np.float64)

    def fold_state(self, header80: bytes) -> ManifoldFoldRecord:
        vector = self.header_vector(header80)
        folded, reflections = fold_poincare_11d_vector(vector)
        folded_norm_sq = compute_poincare_norm_sq(folded)
        assert folded_norm_sq < 1.0
        unfolded = unfold_poincare_11d_vector(folded)
        error = float(np.max(np.abs(vector - unfolded)))
        certificate = compute_zeckendorf_certificate(folded, context_id=DEVICE_ID)
        return ManifoldFoldRecord(
            header_vector_11d=tuple(float(value) for value in vector),
            folded_11d=tuple(float(value) for value in folded),
            folded_norm_sq=folded_norm_sq,
            unfolded_11d=tuple(float(value) for value in unfolded),
            roundtrip_max_abs_error=error,
            reflections=reflections,
            zeckendorf_token=certificate.token_hex,
        )

    def shard_order(self, header80: bytes) -> ManifoldShardOrder:
        folded = np.asarray(self.fold_state(header80).folded_11d, dtype=np.float64)
        affinities = self.compass.directions @ (GOLDEN_WEIGHTS * folded)
        face_order = tuple(sorted(range(len(self.compass)), key=lambda i: (-affinities[i], i)))
        seed = int.from_bytes(hashlib.sha256(header80[:76]).digest()[:8], "big")

        strides = [0] * len(self.compass)
        origins = [0] * len(self.compass)
        digest = hashlib.sha256()
        for face_id in face_order:
            interval = self.shards[face_id]
            if interval.size:
                schedule = cassini_permutation(interval.size, face_id, seed)
                strides[face_id] = schedule.stride
                origins[face_id] = schedule.origin
                stride = schedule.stride
            else:
                stride = 0
            digest.update(
                struct.pack(
                    "<BIIII",
                    face_id,
                    interval.start,
                    interval.stop,
                    stride,
                    origins[face_id],
                )
            )

        return ManifoldShardOrder(
            nonce_start=self.nonce_start,
            nonce_space=self.nonce_space,
            face_order=face_order,
            shards=tuple((interval.start, interval.stop) for interval in self.shards),
            strides=tuple(strides),
            origins=tuple(origins),
            faces_pruned=0,
            schedule_digest=digest.hexdigest(),
            _seed=seed,
        )

    def run(
        self,
        header80: bytes,
        target_be: bytes,
        *,
        n_candidates: int = 256,
        max_hashes: Optional[int] = None,
        allow_cpu_reference: bool = False,
    ) -> Dict[str, Any]:
        if len(header80) != 80:
            raise ValueError("header must contain exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must contain exactly 32 bytes")

        fold = self.fold_state(header80)
        order = self.shard_order(header80)
        probe = order.first(n_candidates)
        header_store = self.stack.aethel.store("header", header80)
        selected_device = (
            self.hyba_devices[0]
            if self.hyba_devices
            else self.driver.devices[0] if self.driver.devices else None
        )

        igpu: Optional[Dict[str, Any]]
        if not self.hardware_available and not allow_cpu_reference:
            hardware = OpenCLExecutionResult.unavailable("opencl")
            igpu = None
        else:
            # The CPU reference class is a requested measurement, not an
            # incidental fallback — pin the hasher backend for this call so
            # truth_class stays deterministic regardless of local OpenCL
            # availability.
            saved_backend = (
                os.environ.get("PYTHIA_HASH_BACKEND") if allow_cpu_reference else None
            )
            if allow_cpu_reference:
                os.environ["PYTHIA_HASH_BACKEND"] = "cpu"
            try:
                igpu = self.stack.igpu.mine(
                    header80,
                    target_be,
                    probe,
                    max_hashes=max_hashes,
                )
            finally:
                if allow_cpu_reference:
                    if saved_backend is None:
                        os.environ.pop("PYTHIA_HASH_BACKEND", None)
                    else:
                        os.environ["PYTHIA_HASH_BACKEND"] = saved_backend
            if igpu["hasher_backend"].startswith("opencl"):
                hardware = OpenCLExecutionResult(
                    requested_backend="opencl",
                    selected_backend="opencl",
                    actual_backend=igpu["hasher_backend"],
                    device_name=selected_device.name if selected_device else None,
                    device_available=True,
                    hardware_execution=True,
                    degraded=False,
                    fallback_used=False,
                    hashes_computed=igpu["hashes_computed"],
                    elapsed_seconds=igpu["elapsed_seconds"],
                    measured_hashrate=igpu["measured_hps"],
                    truth_class="measured_hardware",
                )
            else:
                requested = "cpu_reference" if allow_cpu_reference else "opencl"
                hardware = OpenCLExecutionResult(
                    requested_backend=requested,
                    selected_backend="cpu",
                    actual_backend="cpu",
                    device_name=None,
                    device_available=self.driver.available,
                    hardware_execution=False,
                    degraded=(not allow_cpu_reference) or (not self.hardware_available),
                    fallback_used=not allow_cpu_reference,
                    hashes_computed=igpu["hashes_computed"],
                    elapsed_seconds=igpu["elapsed_seconds"],
                    measured_hashrate=igpu["measured_hps"],
                    truth_class=("measured_cpu_reference" if allow_cpu_reference else "rejected"),
                )

        accepted = False
        winning_nonce = igpu["winning_nonce"] if igpu else None
        if hardware.truth_class != "rejected" and winning_nonce is not None:
            full_header = header80[:76] + struct.pack("<I", winning_nonce)
            candidate_digest = sha256d(full_header)
            accepted = bool(
                igpu["recheck_bit_exact"]
                and candidate_digest == bytes.fromhex(igpu["winning_hash"])
                and check_pow(full_header, int.from_bytes(target_be, "big"))
            )
        if not accepted:
            winning_nonce = None

        compass = {
            "faces": len(self.compass),
            "dodecahedron_faces": sum(face.solid == "dodecahedron" for face in self.compass.faces),
            "icosahedron_faces": sum(face.solid == "icosahedron" for face in self.compass.faces),
            "cassini_certified": all(
                face.cassini_determinant in (-1, 1) for face in self.compass.faces
            ),
        }
        return {
            "device": DEVICE_ID,
            "accepted": accepted,
            "winning_nonce": winning_nonce,
            "winning_hash": igpu["winning_hash"] if accepted and igpu else None,
            "compass": compass,
            "manifold_fold": fold.to_dict(),
            "shard_order": order.to_dict(),
            "probe_candidates": len(probe),
            "hardware": {
                **asdict(hardware),
                "status": "RUN" if igpu is not None else HARDWARE_NOT_RUN,
                "hyba_alias": is_hyba_name(selected_device.name) if selected_device else None,
                "require_hyba": require_hyba(),
                "rejected_reason": (
                    "cpu fallback without allow_cpu_reference"
                    if hardware.truth_class == "rejected"
                    else None
                ),
            },
            "truth_class": hardware.truth_class,
            "measured_hashrate": hardware.measured_hashrate,
            "hashes_computed": hardware.hashes_computed,
            "igpu": igpu,
            "header_store": header_store,
            "consensus_rule": (
                "sha256d(header80[:76] + LE(nonce)) <= target " "(mla1517.mining.pow.check_pow)"
            ),
            "claim_boundary": CLAIM_BOUNDARY,
            "theorem_proven": False,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "device": DEVICE_ID,
            "compass": {
                "faces": len(self.compass),
                "dodecahedron_faces": sum(
                    face.solid == "dodecahedron" for face in self.compass.faces
                ),
                "icosahedron_faces": sum(
                    face.solid == "icosahedron" for face in self.compass.faces
                ),
            },
            "driver_available": self.driver.available,
            "devices": [describe(device) for device in self.driver.devices],
            "hyba_devices": [describe(device) for device in self.hyba_devices],
            "nonce_space": self.nonce_space,
            "nonce_start": self.nonce_start,
            "claim_boundary": CLAIM_BOUNDARY,
        }


__all__ = [
    "DEVICE_ID",
    "CLAIM_BOUNDARY",
    "HARDWARE_NOT_RUN",
    "ManifoldFoldRecord",
    "ManifoldShardOrder",
    "UnifiedManifoldHashingDevice",
]
