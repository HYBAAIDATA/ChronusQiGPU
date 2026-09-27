"""The consolidated iGPU device object.

:class:`IGPU` is the single object that the whole package converges on: one
handle over the census (:mod:`igpu.detect`), the resident OpenCL engine
(:mod:`igpu.engine`), the memory model (:mod:`igpu.runtime`), the hardware
contract (:mod:`igpu.spec`), the punch ISA host, the SHA-256d consensus
grinder, and measured self-telemetry (:mod:`igpu.telemetry`).

The device it describes — the MLA1517-class iGPU — is not a shader array
with a mining loop bolted on. Per its contract
(:data:`igpu.spec.SPEC_NAME`), the native compute memory unit is
*mathematical state*: an 11-axis vector carried on the Poincaré-Golden
manifold, driven by a 32-face icosahedral/dodecahedral execution frame
whose C(32,2) = 496 pairwise channels are the addressable work of the
fabric, executed through a 24-op punch ISA and a consensus-grade SHA-256d
grind with on-device midstates, lane-order traversal, and atomic winner
reduction.

Everything the device reports about itself is measured or explicitly
labelled. ``backend`` names the execution surface that actually ran
(``opencl:gpu`` / ``opencl:cpu`` / ``cpu`` / ``unavailable``), never the
one that was hoped for. Projections carry ``projection_is_measured:
False``. Consensus remains the sole accept authority — the 32-face frame
orders probes; it does not predict winners.

LUCAS WIRING: coordinator module — wires the device surfaces together.
Each surface it composes keeps its own import boundary; this module only
binds them lazily so ``import igpu`` never requires pyopencl and never
touches hardware.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from igpu import spec as _spec
from igpu.detect import DetectionReport, DetectedDevice, detect_all
from igpu.engine import IGPUOpenCLEngine
from igpu.telemetry import IgpuTelemetry, attach_to_host, get_telemetry

logger = logging.getLogger("igpu.device")

DEVICE_ID = "pythia_igpu"

#: The boundary every report restates: geometry orders and shards probes;
#: consensus double-SHA256 is the sole accept authority; measured numbers are
#: labelled measured and projections are labelled projections.
CLAIM_BOUNDARY = (
    "The 32-face frame and the 11D Poincaré-golden manifold are a probe-"
    "ordering / state-composition front-end only. sha256d(header80) <= target "
    "is the sole accept authority; no nonce prediction, nonce-probability "
    "shift, or proof-of-work advantage is asserted. Throughput figures are "
    "measured dispatches; any projected figure is labelled as such."
)


class IGPU:
    """One handle over the consolidated iGPU substrate.

    Construction is cheap and hardware-free: no OpenCL work, no census, no
    spec read happens until the corresponding property is touched.

    - :attr:`spec` / :attr:`topology` — the device contract.
    - :meth:`detect` — the cross-backend census (cached after first call).
    - :attr:`engine` — the process-wide resident OpenCL engine.
    - :attr:`punch_host` — the unified-punch ISA host (lazy).
    - :attr:`hasher` — the SHA-256d consensus grinder (lazy).
    - :meth:`punch` / :meth:`fold` / :meth:`unfold` / :meth:`norm_sq` —
      ISA-level entry points.
    - :meth:`grind` — bounded SHA-256d window grind with hashlib recheck.
    - :meth:`report` — the consolidated, JSON-safe truth surface.
    """

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
        self._engine: Optional[IGPUOpenCLEngine] = None
        self._punch_host: Any = None
        self._hasher: Any = None

    # ------------------------------------------------------------------
    # Identity — the contract the device ships
    # ------------------------------------------------------------------

    @property
    def spec(self) -> Dict[str, Any]:
        """The MLA1517 hardware contract, loaded on first access."""
        if self._spec is None:
            try:
                self._spec = _spec.load_spec()
            except Exception as exc:  # pragma: no cover - missing package data
                logger.debug("spec load failed: %s: %s", type(exc).__name__, exc)
                self._spec = {}
        return self._spec

    @property
    def topology(self) -> Dict[str, Any]:
        """Warp width, node shells, nonce rule, address space."""
        return _spec.topology(self.spec)

    @property
    def state_model(self) -> Dict[str, Any]:
        """The 11-axis state model and its axis names."""
        return _spec.state_model(self.spec)

    @property
    def dimensions(self) -> int:
        """State-space dimension — 11 in the shipping contract."""
        return _spec.dimensions(self.spec)

    @property
    def frame_faces(self) -> int:
        """Execution + memory nodes: 12 icosahedral + 20 dodecahedral = 32."""
        return _spec.frame_faces(self.spec)

    @property
    def face_pairs(self) -> int:
        """Addressable frame channels: C(faces, 2) — 496 at 32 faces."""
        return _spec.face_pairs(self.spec)

    @property
    def isa(self) -> Dict[str, int]:
        """The punch ISA table (name -> opcode) the host dispatches."""
        try:
            return dict(self.punch_host.PUNCH_IDS)
        except Exception:  # pragma: no cover - host missing in stripped envs
            from igpu.telemetry import PUNCH_NAMES

            return {name: pid for pid, name in PUNCH_NAMES.items()}

    # ------------------------------------------------------------------
    # Census — what silicon is actually here
    # ------------------------------------------------------------------

    def detect(self, *, refresh: bool = False) -> DetectionReport:
        """Cross-backend device census (CUDA, Metal, OpenCL), cached."""
        if refresh or self._detection is None:
            self._detection = detect_all()
        return self._detection

    @property
    def census(self) -> DetectionReport:
        return self.detect()

    @property
    def selected(self) -> Optional[DetectedDevice]:
        """The device the census ranks as the substrate's default."""
        return self.detect().default()

    # ------------------------------------------------------------------
    # Execution surfaces — lazy, honest about what actually ran
    # ------------------------------------------------------------------

    @property
    def engine(self) -> IGPUOpenCLEngine:
        """The process-wide resident OpenCL engine."""
        if self._engine is None:
            self._engine = IGPUOpenCLEngine.get()
        return self._engine

    def _pinned_opencl_device(self) -> Optional[str]:
        """Device name the census ranked first — used to pin the execution
        surfaces so the coordinator's schedule runs on the SAME per-device
        selection instead of each component re-selecting (or falling back
        to devices[0]). Returns None when the census has no OpenCL device —
        components then select for themselves under the same gates."""
        selected = self.selected
        if selected is None or selected.backend != "opencl":
            return None
        return selected.name

    @property
    def punch_host(self) -> Any:
        """The unified-punch ISA host, built on first access.

        Telemetry is injected via ``telemetry_hook`` — the host is an
        algorithm module under the LUCAS WIRING purity rule and never
        imports the collector; the coordinator reaches in instead.
        """
        if self._punch_host is None:
            from Intelligence.unified_punch import UnifiedPunchHost

            self._punch_host = UnifiedPunchHost(device=self._pinned_opencl_device())
            if self._attach_telemetry:
                attach_to_host(self._punch_host, self._telemetry)
        return self._punch_host

    @property
    def hasher(self) -> Any:
        """The SHA-256d consensus grinder, built on first access."""
        if self._hasher is None:
            from mining.bitcoin_hasher import BitcoinHasher

            self._hasher = BitcoinHasher(device=self._pinned_opencl_device())
        return self._hasher

    @property
    def telemetry(self) -> IgpuTelemetry:
        """This device's measured-facts collector."""
        return self._telemetry

    @property
    def available(self) -> bool:
        """True only when the engine is bound to a real OpenCL device."""
        try:
            return self.engine.available
        except Exception:  # pragma: no cover - defensive
            return False

    @property
    def backend(self) -> str:
        """Honest execution surface label.

        ``opencl:gpu``/``opencl:cpu`` when a punch host or hasher reports a
        bound OpenCL device, ``opencl-engine`` when only the resident engine
        bound, ``cpu`` when the substrate is executing on the host fallback,
        ``unavailable`` when nothing bound at all.
        """
        host = self._punch_host
        if host is not None and getattr(host, "use_opencl", False):
            return str(host.backend)
        hasher = self._hasher
        if hasher is not None and str(getattr(hasher, "backend", "cpu")).startswith("opencl"):
            return str(hasher.backend)
        try:
            if self.engine.available:
                return "opencl:" + ("gpu" if self._engine_is_gpu() else "device")
        except Exception:  # pragma: no cover - defensive
            pass
        if host is not None or hasher is not None:
            return "cpu"
        return "unavailable"

    def _engine_is_gpu(self) -> bool:
        engine = self.engine
        device = getattr(engine, "_device", None)
        cl = getattr(engine, "_cl", None)
        try:
            gpu_bit = int(getattr(cl.device_type, "GPU", 1 << 2))
            return bool(int(getattr(device, "type", 0) or 0) & gpu_bit)
        except Exception:  # pragma: no cover - defensive
            return True

    # ------------------------------------------------------------------
    # ISA entry points — the work the fabric actually does
    # ------------------------------------------------------------------

    def _punch_id(self, punch: Any) -> int:
        """Resolve a punch name or integer opcode to the opcode."""
        if isinstance(punch, str):
            table = self.isa
            if punch not in table:
                raise ValueError(f"unknown punch name {punch!r}; known: {sorted(table)}")
            return int(table[punch])
        return int(punch)

    def punch(self, punch: Any, *, n: Optional[int] = None, **channels: Any) -> Dict[str, np.ndarray]:
        """Run one ISA punch over ``n`` work-items through the real backend.

        ``punch`` is a name (``"poincare_fold"``) or opcode (``0x08``).
        Channels map to :meth:`UnifiedPunchHost.run_punch_batch`
        (``in_float`` / ``in_ulong`` / ``in_int`` / ``in_double``).
        """
        return self.punch_host.run_punch_batch(self._punch_id(punch), n=n, **channels)

    def fold(self, x_11d: Any) -> np.ndarray:
        """Poincaré fold of ``(n, 11)`` state vectors — punch 0x08."""
        arr = np.asarray(x_11d, dtype=np.float32)
        single = arr.ndim == 1
        arr = arr.reshape(1, -1) if single else arr
        out = self.punch("poincare_fold", n=arr.shape[0], in_float=arr.ravel())
        folded = np.asarray(out["float"], dtype=np.float32)[: arr.shape[0] * self.dimensions]
        folded = folded.reshape(arr.shape[0], self.dimensions)
        return folded[0] if single else folded

    def unfold(self, folded_11d: Any) -> np.ndarray:
        """Inverse Poincaré fold — punch 0x09."""
        arr = np.asarray(folded_11d, dtype=np.float32)
        single = arr.ndim == 1
        arr = arr.reshape(1, -1) if single else arr
        out = self.punch("poincare_unfold", n=arr.shape[0], in_float=arr.ravel())
        unfolded = np.asarray(out["float"], dtype=np.float32)[: arr.shape[0] * self.dimensions]
        unfolded = unfolded.reshape(arr.shape[0], self.dimensions)
        return unfolded[0] if single else unfolded

    def norm_sq(self, x_11d: Any) -> np.ndarray:
        """PHI-weighted squared norm of ``(n, 11)`` vectors — punch 0x15."""
        arr = np.asarray(x_11d, dtype=np.float32)
        single = arr.ndim == 1
        arr = arr.reshape(1, -1) if single else arr
        out = self.punch("manifold_compute", n=arr.shape[0], in_float=arr.ravel())
        values = np.asarray(out["float"], dtype=np.float32)[:: self.dimensions][: arr.shape[0]]
        return values[0] if single else values

    def grind(
        self,
        header80: bytes,
        target_be: bytes,
        *,
        base_nonce: int = 0,
        count: int = 1 << 20,
    ) -> Tuple[Optional[int], Optional[bytes], int]:
        """Bounded SHA-256d window grind on the bound backend.

        Returns ``(winner_nonce | None, winner_digest | None, hashes)``.
        Every digest in the window is physically computed; a device-reported
        hit is re-verified with hashlib before it is returned — consensus is
        the sole accept authority, and this method never fabricates one.
        """
        return self.hasher.grind_target_range(
            header80, target_be, base_nonce=base_nonce, count=count
        )

    # ------------------------------------------------------------------
    # The consolidated truth surface
    # ------------------------------------------------------------------

    def report(self, *, census: bool = True) -> Dict[str, Any]:
        """The device as one JSON-safe document — measured or labelled.

        Every number in this report is either a geometric fact (topology,
        channel count, ISA size), a contract clause (acceptance status), or
        a measured quantity straight out of :mod:`igpu.telemetry`. Nothing
        here is a projection wearing a measured label.
        """
        engine_info: Dict[str, Any] = {}
        try:
            engine_info = self.engine.as_dict()
        except Exception as exc:  # pragma: no cover - defensive
            engine_info = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}

        census_info: Optional[Dict[str, Any]] = None
        if census:
            try:
                census_info = self.detect().as_dict()
            except Exception as exc:  # pragma: no cover - defensive
                census_info = {"error": f"{type(exc).__name__}: {exc}"}

        host_info: Optional[Dict[str, Any]] = None
        if self._punch_host is not None:
            try:
                host_info = self._punch_host.telemetry_snapshot()
            except Exception:  # pragma: no cover - defensive
                host_info = {"backend": self._punch_host.backend}

        hasher_info: Optional[Dict[str, Any]] = None
        if self._hasher is not None:
            try:
                hasher_info = self._hasher.telemetry()
            except Exception:  # pragma: no cover - defensive
                hasher_info = {"backend": getattr(self._hasher, "backend", "unknown")}

        try:
            telemetry = self._telemetry.snapshot()
        except Exception as exc:  # pragma: no cover - defensive
            telemetry = {"error": f"{type(exc).__name__}: {exc}"}

        return {
            "device": DEVICE_ID,
            "product": _spec.product(self.spec),
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
        """One honest line: backend, bound device, ISA width, frame geometry."""
        backend = self.backend
        device = ""
        try:
            device = self.engine.device_name
        except Exception:  # pragma: no cover - defensive
            device = ""
        detail = device or (self.engine.unavailable_reason if not self.available else "")
        return (
            f"{DEVICE_ID}: backend={backend}"
            + (f" device={device!r}" if device else "")
            + (f" reason={detail!r}" if detail and not device else "")
            + f" isa={len(self.isa)}-punch dim={self.dimensions}D"
            + f" frame={self.frame_faces}-face/{self.face_pairs}-ch"
        )

    def close(self) -> None:
        """Finish queues and release host-owned device buffers."""
        for surface in (self._punch_host, self._hasher):
            close = getattr(surface, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # pragma: no cover - defensive
                    logger.debug("surface close failed", exc_info=True)

    def __enter__(self) -> "IGPU":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


def open_device(**kwargs: Any) -> IGPU:
    """Open the consolidated iGPU substrate — one device object."""
    return IGPU(**kwargs)


__all__ = [
    "CLAIM_BOUNDARY",
    "DEVICE_ID",
    "IGPU",
    "open_device",
]
