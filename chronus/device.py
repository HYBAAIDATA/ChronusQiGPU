"""Chronus — HYBA's canonical iGPU offering device/runtime object.

Turing is the computation substrate. Chronus binds that computation to measured
hardware, resident execution, the punch ISA, hashing, state operations and
telemetry. Construction is lazy and does not touch hardware.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from . import spec as _spec
from .detect import DetectionReport, DetectedDevice, detect_all
from .engine import ChronusOpenCLEngine
from .telemetry import IgpuTelemetry, PUNCH_NAMES, attach_to_host, get_telemetry

logger = logging.getLogger("chronus.device")

DEVICE_ID = "chronus"
CLAIM_BOUNDARY = (
    "Chronus is HYBA's iGPU offering over the Turing compute substrate. "
    "The 32-face frame and 11D Poincaré-golden manifold order/compose work; "
    "they do not bypass an operation's verification authority. For mining, "
    "sha256d(header80) <= target is the sole accept authority. Throughput is "
    "reported only from measured dispatches and projections remain labelled."
)


class Chronus:
    """Single product handle for Chronus device, runtime and truth surfaces."""

    def __init__(
        self,
        *,
        telemetry: Optional[IgpuTelemetry] = None,
        attach_telemetry: bool = True,
    ) -> None:
        self._telemetry = telemetry if telemetry is not None else get_telemetry()
        self._attach_telemetry = bool(attach_telemetry)
        self._detection: Optional[DetectionReport] = None
        self._spec: Optional[Dict[str, Any]] = None
        self._engine: Optional[ChronusOpenCLEngine] = None
        self._punch_host: Any = None
        self._hasher: Any = None

    @property
    def spec(self) -> Dict[str, Any]:
        if self._spec is None:
            try:
                self._spec = _spec.load_spec()
            except Exception as exc:
                logger.debug("spec load failed: %s: %s", type(exc).__name__, exc)
                self._spec = {}
        return self._spec

    @property
    def topology(self) -> Dict[str, Any]:
        return _spec.topology(self.spec)

    @property
    def state_model(self) -> Dict[str, Any]:
        return _spec.state_model(self.spec)

    @property
    def dimensions(self) -> int:
        return _spec.dimensions(self.spec)

    @property
    def frame_faces(self) -> int:
        return _spec.frame_faces(self.spec)

    @property
    def face_pairs(self) -> int:
        return _spec.face_pairs(self.spec)

    @property
    def isa(self) -> Dict[str, int]:
        try:
            return dict(self.punch_host.PUNCH_IDS)
        except Exception:
            return {name: pid for pid, name in PUNCH_NAMES.items()}

    def detect(self, *, refresh: bool = False) -> DetectionReport:
        if refresh or self._detection is None:
            self._detection = detect_all()
        return self._detection

    @property
    def census(self) -> DetectionReport:
        return self.detect()

    @property
    def selected(self) -> Optional[DetectedDevice]:
        return self.detect().default()

    @property
    def engine(self) -> ChronusOpenCLEngine:
        if self._engine is None:
            self._engine = ChronusOpenCLEngine.get()
        return self._engine

    def _pinned_opencl_device(self) -> Optional[str]:
        selected = self.selected
        if selected is None or selected.backend != "opencl":
            return None
        return selected.name

    @property
    def punch_host(self) -> Any:
        if self._punch_host is None:
            from Intelligence.unified_punch import UnifiedPunchHost

            self._punch_host = UnifiedPunchHost(device=self._pinned_opencl_device())
            if self._attach_telemetry:
                attach_to_host(self._punch_host, self._telemetry)
        return self._punch_host

    @property
    def hasher(self) -> Any:
        if self._hasher is None:
            from mining.bitcoin_hasher import BitcoinHasher

            self._hasher = BitcoinHasher(device=self._pinned_opencl_device())
        return self._hasher

    @property
    def telemetry(self) -> IgpuTelemetry:
        return self._telemetry

    @property
    def available(self) -> bool:
        try:
            return self.engine.available
        except Exception:
            return False

    @property
    def backend(self) -> str:
        host = self._punch_host
        if host is not None and getattr(host, "use_opencl", False):
            return str(host.backend)
        hasher = self._hasher
        if hasher is not None:
            backend = str(getattr(hasher, "backend", "cpu"))
            if backend.startswith("opencl"):
                return backend
        try:
            if self.engine.available:
                return "opencl:" + ("gpu" if self._engine_is_gpu() else "device")
        except Exception:
            pass
        return "cpu" if host is not None or hasher is not None else "unavailable"

    def _engine_is_gpu(self) -> bool:
        engine = self.engine
        device = getattr(engine, "_device", None)
        cl = getattr(engine, "_cl", None)
        try:
            gpu_bit = int(getattr(cl.device_type, "GPU", 1 << 2))
            return bool(int(getattr(device, "type", 0) or 0) & gpu_bit)
        except Exception:
            return True

    def _punch_id(self, punch: Any) -> int:
        if isinstance(punch, str):
            table = self.isa
            if punch not in table:
                raise ValueError(f"unknown punch name {punch!r}; known: {sorted(table)}")
            return int(table[punch])
        return int(punch)

    def punch(
        self,
        punch: Any,
        *,
        n: Optional[int] = None,
        **channels: Any,
    ) -> Dict[str, np.ndarray]:
        return self.punch_host.run_punch_batch(self._punch_id(punch), n=n, **channels)

    def _vectors(self, values: Any) -> Tuple[np.ndarray, bool]:
        array = np.asarray(values, dtype=np.float32)
        single = array.ndim == 1
        array = array.reshape(1, -1) if single else array
        if array.ndim != 2 or array.shape[1] != self.dimensions:
            raise ValueError(
                f"expected state shape ({self.dimensions},) or (n,{self.dimensions}), "
                f"got {array.shape}"
            )
        return array, single

    def fold(self, x_11d: Any) -> np.ndarray:
        array, single = self._vectors(x_11d)
        out = self.punch("poincare_fold", n=array.shape[0], in_float=array.ravel())
        values = np.asarray(out["float"], dtype=np.float32)[
            : array.shape[0] * self.dimensions
        ].reshape(array.shape[0], self.dimensions)
        return values[0] if single else values

    def unfold(self, folded_11d: Any) -> np.ndarray:
        array, single = self._vectors(folded_11d)
        out = self.punch("poincare_unfold", n=array.shape[0], in_float=array.ravel())
        values = np.asarray(out["float"], dtype=np.float32)[
            : array.shape[0] * self.dimensions
        ].reshape(array.shape[0], self.dimensions)
        return values[0] if single else values

    def norm_sq(self, x_11d: Any) -> np.ndarray:
        array, single = self._vectors(x_11d)
        out = self.punch("manifold_compute", n=array.shape[0], in_float=array.ravel())
        values = np.asarray(out["float"], dtype=np.float32)[:: self.dimensions][
            : array.shape[0]
        ]
        return values[0] if single else values

    def grind(
        self,
        header80: bytes,
        target_be: bytes,
        *,
        base_nonce: int = 0,
        count: int = 1 << 20,
    ) -> Tuple[Optional[int], Optional[bytes], int]:
        return self.hasher.grind_target_range(
            header80,
            target_be,
            base_nonce=base_nonce,
            count=count,
        )

    def report(self, *, census: bool = True) -> Dict[str, Any]:
        try:
            engine_info = self.engine.as_dict()
        except Exception as exc:
            engine_info = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}

        census_info: Optional[Dict[str, Any]] = None
        if census:
            try:
                census_info = self.detect().as_dict()
            except Exception as exc:
                census_info = {"error": f"{type(exc).__name__}: {exc}"}

        host_info = None
        if self._punch_host is not None:
            try:
                host_info = self._punch_host.telemetry_snapshot()
            except Exception:
                host_info = {"backend": getattr(self._punch_host, "backend", "unknown")}

        hasher_info = None
        if self._hasher is not None:
            try:
                hasher_info = self._hasher.telemetry()
            except Exception:
                hasher_info = {"backend": getattr(self._hasher, "backend", "unknown")}

        try:
            telemetry = self._telemetry.snapshot()
        except Exception as exc:
            telemetry = {"error": f"{type(exc).__name__}: {exc}"}

        return {
            "device": DEVICE_ID,
            "product": "Chronus",
            "compute_substrate": "Turing",
            "hardware_contract_product": _spec.product(self.spec),
            "contract_version": self.spec.get("contract_version", ""),
            "ontology": _spec.ontology(self.spec),
            "backend": self.backend,
            "available": self.available,
            "engine": engine_info,
            "census": census_info,
            "state_model": {
                "dimensions": self.dimensions,
                "axes": list(self.state_model.get("axes", [])),
                "hot_transport_descriptor_bytes": self.state_model.get(
                    "hot_transport_descriptor_bytes"
                ),
            },
            "topology": self.topology,
            "frame": {
                "faces": self.frame_faces,
                "icosahedral_execution_nodes": self.topology.get(
                    "icosahedral_execution_nodes"
                ),
                "dodecahedral_memory_nodes": self.topology.get(
                    "dodecahedral_memory_nodes"
                ),
                "face_pairs": self.face_pairs,
                "channels_occupied_measured": self._telemetry.channels_occupied,
            },
            "isa": {"punches": len(self.isa), "by_name": self.isa},
            "execution_pipeline": _spec.execution_pipeline(self.spec),
            "execution_units": _spec.execution_units(self.spec),
            "memory_system": _spec.memory_system(self.spec),
            "punch_host": host_info,
            "hasher": hasher_info,
            "telemetry": telemetry,
            "deployment": _spec.deployment(self.spec),
            "acceptance_contract": _spec.acceptance_contract(self.spec),
            "claim_boundary": CLAIM_BOUNDARY,
            "theorem_proven": False,
        }

    def status_line(self) -> str:
        try:
            device = self.engine.device_name
        except Exception:
            device = ""
        detail = device or (self.engine.unavailable_reason if not self.available else "")
        return (
            f"{DEVICE_ID}: backend={self.backend}"
            + (f" device={device!r}" if device else "")
            + (f" reason={detail!r}" if detail and not device else "")
            + f" isa={len(self.isa)}-punch dim={self.dimensions}D"
            + f" frame={self.frame_faces}-face/{self.face_pairs}-ch"
        )

    def close(self) -> None:
        for surface in (self._punch_host, self._hasher):
            close = getattr(surface, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    logger.debug("surface close failed", exc_info=True)

    def __enter__(self) -> "Chronus":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


def open_device(**kwargs: Any) -> Chronus:
    return Chronus(**kwargs)


__all__ = ["CLAIM_BOUNDARY", "DEVICE_ID", "Chronus", "open_device"]
