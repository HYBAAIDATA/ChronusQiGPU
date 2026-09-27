"""Unified punch layer — classical GPU/OpenCL compute substrate.

Runs the 24 classical "punch" kernels on whatever OpenCL device is
available (iGPU, dGPU, or OpenCL CPU device), with a bit-faithful numpy
fallback when no OpenCL platform exists. Telemetry is honest: it reports
the real device name/type and never claims a GPU when running on CPU.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

try:
    import pyopencl as cl

    HAS_OPENCL = True
except ImportError:  # pragma: no cover - depends on host environment
    cl = None  # type: ignore[assignment]
    HAS_OPENCL = False

logger = logging.getLogger("Intelligence.unified_punch")

PHI = (1 + np.sqrt(5)) / 2
PSI = 1 - PHI
SQRT5 = np.sqrt(5)
DIM = 11
PRIME_COUNT = 25
SLOTS_PER_PRIME = 1024
TOTAL_SLOTS = PRIME_COUNT * SLOTS_PER_PRIME

# Punches that operate on the 11-dimensional manifold specifically. Duplicated
# from the telemetry label set on purpose: importing a sibling would breach the
# LUCAS WIRING purity rule for this algorithm module.
_MANIFOLD_PUNCH_NAMES = frozenset(
    {
        "poincare_fold",
        "poincare_unfold",
        "geodesic_distance",
        "mint_certificate",
        "manifold_compute",
    }
)
PRIMES = [
    2,
    3,
    5,
    7,
    11,
    13,
    17,
    19,
    23,
    29,
    31,
    37,
    41,
    43,
    47,
    53,
    59,
    61,
    67,
    71,
    73,
    79,
    83,
    89,
    97,
]
MASK64 = (1 << 64) - 1

# Output-channel write map, kept in kernel parity. Every punch addresses its
# output channels at gid * <channel width>, so a caller whose batch never
# writes a channel may pass a small scratch array — dispatch then skips the
# device allocation and the readback for that channel entirely (the
# DIM*DIM-wide ulong block is ~968 B per work-item and dominates the
# phi_filter score path). An unmapped punch conservatively requires every
# channel at full width.
_CHANNEL_WIDTH = {
    "float": DIM,
    "ulong": DIM * DIM,
    "int": 1,
    "long": 1,
    "double": 1,
}
_ALL_CHANNELS = frozenset(_CHANNEL_WIDTH)
_PUNCH_WRITES = {
    0x01: frozenset({"ulong"}),  # cassini_power
    0x02: frozenset({"ulong"}),  # zeckendorf_encode
    0x03: frozenset({"int", "double"}),  # pisot_schedule
    0x04: frozenset({"int"}),  # diophantine_check
    0x05: frozenset({"float"}),  # golden_angle
    0x06: frozenset({"float"}),  # fold_topology
    0x07: frozenset({"float"}),  # spectral_gap
    0x08: frozenset({"float"}),  # poincare_fold
    0x09: frozenset({"float"}),  # poincare_unfold
    0x0A: frozenset({"float"}),  # geodesic_distance
    0x0B: frozenset({"ulong", "int"}),  # mint_certificate
    0x0C: frozenset({"int"}),  # salamander_alloc
    0x0D: frozenset({"int"}),  # beatty_partition
    0x0E: frozenset({"long"}),  # cassini_det
    0x0F: frozenset({"int"}),  # decoupling_mask
    0x10: frozenset({"int", "float"}),  # millennium_verify
    0x11: frozenset({"float", "int"}),  # schema_split
    0x15: frozenset({"float"}),  # manifold_compute
    0x16: frozenset({"float"}),  # millennium_all
    0x17: frozenset({"int"}),  # hard_gate
    0x18: frozenset({"float", "int"}),  # schema_enforce
    0x19: frozenset({"int"}),  # immutable_proof
    0x1B: frozenset({"ulong", "int"}),  # sha256d_grind_mark
    0x1C: frozenset({"ulong"}),  # zeckendorf_decode
}

# Input-channel read map, taken verbatim from the kernel dispatch switch.
# Channels a batch never reads are not uploaded — the kernel receives a
# scratch buffer instead (it cannot dereference them). An unmapped punch
# conservatively uploads every channel. punch_ids is always uploaded.
_ALL_INPUT_CHANNELS = frozenset({"float", "ulong", "int", "double"})
_PUNCH_READS = {
    0x01: frozenset({"ulong"}),  # cassini_power
    0x02: frozenset({"ulong"}),  # zeckendorf_encode
    0x03: frozenset({"double"}),  # pisot_schedule
    0x04: frozenset({"ulong"}),  # diophantine_check
    0x05: frozenset(),  # golden_angle_distribute — inputs unused
    0x06: frozenset({"float"}),  # fold_topology
    0x07: frozenset({"ulong"}),  # spectral_gap
    0x08: frozenset({"float"}),  # poincare_fold
    0x09: frozenset({"float"}),  # poincare_unfold
    0x0A: frozenset({"float"}),  # geodesic_distance
    0x0B: frozenset({"float"}),  # mint_certificate
    0x0C: frozenset({"ulong", "int"}),  # salamander_alloc
    0x0D: frozenset(),  # beatty_partition — only n_per_punch
    0x0E: frozenset({"ulong"}),  # cassini_det
    0x0F: frozenset({"int"}),  # decoupling_mask
    0x10: frozenset({"int"}),  # millennium_verify
    0x11: frozenset({"float"}),  # schema_split
    0x15: frozenset({"float"}),  # manifold_compute
    0x16: frozenset(),  # millennium_all — inputs unused
    0x17: frozenset({"int"}),  # hard_gate
    0x18: frozenset({"float"}),  # schema_enforce
    0x19: frozenset(),  # immutable_proof — inputs unused
    0x1B: frozenset({"ulong"}),  # sha256d_grind_mark
    0x1C: frozenset({"ulong"}),  # zeckendorf_decode
}

# The OpenCL kernel is shipped in the JV kernel package. Resolve across the
# known layouts instead of hard-coding one path: a wrong path silently degraded
# the whole iGPU path to the numpy fallback.
_KERNEL_FILENAME = "unified_punch_kernel.cl"


def _resolve_kernel_path() -> Path:
    """First existing candidate for the punch kernel, else the canonical path."""
    root = Path(__file__).resolve().parent.parent
    candidates = (
        root / "kernels" / _KERNEL_FILENAME,
        root / "iGPU_Accelerator_JV" / "kernels" / _KERNEL_FILENAME,
        Path(__file__).resolve().parent / "kernels" / _KERNEL_FILENAME,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


_DEFAULT_KERNEL_PATH = _resolve_kernel_path()


class UnifiedPunchHost:
    """Host driver for the unified punch kernel.

    Selects the best OpenCL device non-interactively (GPU devices first),
    builds the kernel, and executes all punches over N work-items per
    punch. Falls back to an equivalent numpy implementation when OpenCL
    is unavailable or the kernel fails to build — ``device_info`` and
    ``gpu_error`` always report the truth either way.
    """

    PUNCH_IDS = {
        "cassini_power": 0x01,
        "zeckendorf_encode": 0x02,
        "pisot_schedule": 0x03,
        "diophantine_check": 0x04,
        "golden_angle": 0x05,
        "fold_topology": 0x06,
        "spectral_gap": 0x07,
        "poincare_fold": 0x08,
        "poincare_unfold": 0x09,
        "geodesic_distance": 0x0A,
        "mint_certificate": 0x0B,
        "salamander_alloc": 0x0C,
        "beatty_partition": 0x0D,
        "cassini_det": 0x0E,
        "decoupling_mask": 0x0F,
        "millennium_verify": 0x10,
        "schema_split": 0x11,
        "manifold_compute": 0x15,
        "millennium_all": 0x16,
        "hard_gate": 0x17,
        "schema_enforce": 0x18,
        "immutable_proof": 0x19,
        "sha256d_grind_mark": 0x1B,
        "zeckendorf_decode": 0x1C,
    }
    # Reverse index for telemetry labelling (no sibling import — purity).
    PUNCH_NAMES = {pid: name for name, pid in PUNCH_IDS.items()}
    SUPPORTED_PUNCH_IDS = frozenset(PUNCH_IDS.values())

    # Metal kernel-name map (B4): Metal dispatch names for the hash-pipeline
    # punches. Off-macOS AppleMetal raises honestly; OpenCL/CPU use the .cl above.
    METAL_KERNEL_MAP = {
        "phi_filter_score": "phi_filter_score",
        "sha256d_grind_mark": "sha256d_grind",
    }
    SHA256_GRIND_KERNEL = "sha256d_grind"

    def __init__(self, kernel_path: Optional[str] = None):
        self.kernel_path = str(kernel_path) if kernel_path else str(_DEFAULT_KERNEL_PATH)
        self.use_opencl = False
        self.device_info: Dict[str, Any] = {"type": "none", "name": "cpu", "hyba_alias": None}
        self.gpu_error: Optional[str] = None
        self.last_kernel_ms: Optional[float] = None
        # Provenance of the most recent execution: the backend that
        # actually ran, not the backend that was available.
        self.last_dispatch_backend: str = "none"
        self.kernel = None
        # Grow-only device buffer pool: name -> (cl.Buffer, capacity bytes).
        self._buf_pool: Dict[str, tuple] = {}
        if HAS_OPENCL:
            try:
                self._init_opencl()
            except Exception as exc:  # build failures, missing platforms, etc.
                self.gpu_error = str(exc)
                logger.warning("OpenCL init failed, using CPU fallback: %s", exc)
                # A device may have been enumerated even though the kernel
                # failed to build (e.g. no fp64 support). Report it
                # truthfully instead of dropping device_info entirely.
                try:
                    dev = self._select_device()
                    name = str(getattr(dev, "name", "")).strip()
                    name_lower = name.lower()
                    aliases = self._hyba_aliases()
                    self.device_info = {
                        "type": "cpu_fallback",
                        "name": name,
                        "hyba_alias": next((a for a in aliases if a and a in name_lower), None),
                        "opencl_error": str(exc),
                    }
                except Exception:
                    pass
        else:
            self.gpu_error = "pyopencl not installed"

    # ------------------------------------------------------------------
    # OpenCL setup
    # ------------------------------------------------------------------

    # HYBA iGPU identity. Duplicated from scripts/igpu_diag.py on purpose:
    # importing a sibling would breach the LUCAS WIRING purity rule for this
    # algorithm module. Overridable via HYBA_DEVICE_ALIAS (comma-separated).
    DEFAULT_HYBA_ALIASES = ("hyba-mla1517", "hyba_mla1517", "mla1517", "hyba")

    @staticmethod
    def _hyba_aliases() -> tuple:
        """Alias list for the HYBA iGPU; HYBA_DEVICE_ALIAS overrides."""
        raw = os.environ.get("HYBA_DEVICE_ALIAS", "").strip()
        if raw:
            return tuple(a.strip().lower() for a in raw.split(",") if a.strip())
        return UnifiedPunchHost.DEFAULT_HYBA_ALIASES

    @staticmethod
    def _device_rank(name_lower: str, is_gpu: bool, aliases: tuple) -> tuple:
        """Pure preference key: HYBA-alias device first, then GPU, then name."""
        alias_hit = next((a for a in aliases if a and a in name_lower), "")
        return (0 if alias_hit else 1, 0 if is_gpu else 1, name_lower)

    @staticmethod
    def _select_device():
        """Prefer the HYBA iGPU (alias match), else first GPU, else first device.

        ``HYBA_REQUIRE_HYBA`` fails explicitly when no alias-matching device
        is enumerated — it never silently substitutes a different device.
        """
        aliases = UnifiedPunchHost._hyba_aliases()
        require_hyba = os.environ.get("HYBA_REQUIRE_HYBA", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if cl is None or not [d for p in cl.get_platforms() for d in p.get_devices()]:
            if require_hyba:
                raise RuntimeError(
                    "HYBA_REQUIRE_HYBA set but no OpenCL devices can be "
                    "enumerated (pyopencl unavailable or zero devices)"
                )
            raise RuntimeError("no OpenCL devices found")
        devices = [d for p in cl.get_platforms() for d in p.get_devices()]
        if require_hyba:
            for dev in devices:
                name = str(getattr(dev, "name", "")).strip().lower()
                if any(a and a in name for a in aliases):
                    return dev
            names = [str(getattr(d, "name", "")).strip() for d in devices]
            raise RuntimeError(
                "HYBA_REQUIRE_HYBA set but no HYBA-alias OpenCL device "
                f"enumerated (aliases={list(aliases)}); found: {names}"
            )
        return min(
            devices,
            key=lambda d: UnifiedPunchHost._device_rank(
                str(getattr(d, "name", "")).strip().lower(),
                bool(d.type & cl.device_type.GPU),
                aliases,
            ),
        )

    def _init_opencl(self) -> None:
        device = self._select_device()
        self.ctx = cl.Context([device])
        # Profiling enabled so benchmarks can report true kernel time.
        self.queue = cl.CommandQueue(
            self.ctx, properties=cl.command_queue_properties.PROFILING_ENABLE
        )
        source = Path(self.kernel_path).read_text(encoding="utf-8")
        self.program = cl.Program(self.ctx, source).build()
        self.kernel = self.program.unified_punch_kernel
        self.use_opencl = True
        if device.type & cl.device_type.GPU:
            dtype = "gpu"
        elif device.type & cl.device_type.CPU:
            dtype = "cpu"
        else:
            dtype = "other"
        self.device_info = {
            "name": device.name.strip(),
            "vendor": device.vendor.strip(),
            "platform": device.platform.name.strip(),
            "type": dtype,
            "compute_units": int(device.max_compute_units),
            "max_work_group_size": int(device.max_work_group_size),
            "global_mem_mb": int(device.global_mem_size // (1024 * 1024)),
        }
        name_lower = str(self.device_info["name"]).lower()
        self.device_info["hyba_alias"] = next(
            (a for a in self._hyba_aliases() if a and a in name_lower), None
        )
        logger.info(
            "OpenCL device: %s (%s, %d CUs)",
            self.device_info["name"],
            dtype,
            self.device_info["compute_units"],
        )

    @property
    def use_gpu(self) -> bool:
        """True when the OpenCL path executes (any device type)."""
        return self.use_opencl

    @property
    def backend(self) -> str:
        """Honest backend label: 'opencl:gpu', 'opencl:cpu', or 'cpu'."""
        if self.use_opencl:
            return f"opencl:{self.device_info.get('type', 'other')}"
        return "cpu"

    # ------------------------------------------------------------------
    # Telemetry (host-native; no sibling imports — LUCAS WIRING purity)
    # ------------------------------------------------------------------

    def _emit_telemetry(self, punch_ids, total: int, n_per_punch: int) -> None:
        """Report one completed dispatch to an injected telemetry hook.

        The hook is a plain callable installed by a *coordinator* module
        (see ``Intelligence/igpu_telemetry.py``); it is never imported here
        because this module is an algorithm module under the LUCAS WIRING
        purity rule. When no hook is installed this is a no-op, so behaviour
        without telemetry is bit-identical to before.

        Telemetry must never break mining: every failure is swallowed.
        """
        self.punch_mix = getattr(self, "punch_mix", {})
        # Per-dispatch delta. ``self.punch_mix`` stays cumulative for this
        # host's own snapshot, but the emitted hook payload must be the delta:
        # emitting the cumulative dict would make any downstream collector
        # double-count on every dispatch after the first.
        batch_mix: Dict[int, int] = {}
        try:
            ids = np.asarray(punch_ids)
            for pid in np.unique(ids):
                pid_int = int(pid)
                count = int(np.count_nonzero(ids == pid_int))
                batch_mix[pid_int] = batch_mix.get(pid_int, 0) + count
                self.punch_mix[pid_int] = self.punch_mix.get(pid_int, 0) + count
            # Derived from the cumulative mix rather than incremented, so
            # repeated dispatches cannot inflate the manifold total.
            self.manifold_punch_count = sum(
                count
                for pid_int, count in self.punch_mix.items()
                if self.PUNCH_NAMES.get(pid_int) in _MANIFOLD_PUNCH_NAMES
            )
        except Exception:  # pragma: no cover - defensive
            logger.debug("telemetry punch-mix accounting failed", exc_info=True)

        hook = getattr(self, "telemetry_hook", None)
        if hook is None:
            return
        try:
            hook(
                {
                    "kind": "dispatch",
                    "backend": self.backend,
                    "gpu": bool(self.use_opencl),
                    "work_items": int(total),
                    "kernel_ms": self.last_kernel_ms,
                    "n_per_punch": int(n_per_punch),
                    "punch_mix": dict(batch_mix),
                }
            )
        except Exception:  # pragma: no cover - telemetry must never break mining
            logger.debug("telemetry hook failed", exc_info=True)

    def telemetry_snapshot(self) -> Dict[str, Any]:
        """Host-native telemetry. Works with or without an injected hook."""
        dispatch_count = int(getattr(self, "dispatch_count", 0))
        kernel_ms_total = float(getattr(self, "kernel_ms_total", 0.0))
        mix = dict(getattr(self, "punch_mix", {}))
        named = {
            self.PUNCH_NAMES.get(pid, f"punch_0x{pid:02X}"): count
            for pid, count in sorted(mix.items())
        }
        return {
            "backend": self.backend,
            "backend_available": bool(self.use_opencl),
            "device": dict(self.device_info),
            "gpu_error": self.gpu_error,
            "dispatch_count": dispatch_count,
            "kernel_ms_total": kernel_ms_total,
            "kernel_ms_last": self.last_kernel_ms,
            "kernel_ms_mean": (kernel_ms_total / dispatch_count) if dispatch_count else 0.0,
            "last_dispatch_backend": self.last_dispatch_backend,
            "manifold_punch_total": int(getattr(self, "manifold_punch_count", 0)),
            "punch_mix": named,
            "telemetry_hook_attached": getattr(self, "telemetry_hook", None) is not None,
            "dim": DIM,
            "theorem_proven": False,
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_all_punches(
        self,
        N: int = 1024,
        seed: Optional[int] = None,
        backend: str = "auto",
    ) -> Dict[str, np.ndarray]:
        """Run all 25 punches over N work-items each.

        ``backend`` is 'auto' (OpenCL if usable, else CPU), 'gpu' (OpenCL
        required — raises if unavailable), or 'cpu' (force the numpy path;
        used by the GPU/CPU parity test).
        """
        total = N * len(self.PUNCH_IDS)
        rng = np.random.default_rng(seed)

        punch_ids = np.zeros(total, dtype=np.uint32)
        idx = 0
        for pid in self.PUNCH_IDS.values():
            punch_ids[idx : idx + N] = pid
            idx += N

        in_float = rng.standard_normal(total * DIM).astype(np.float32)
        in_ulong = rng.integers(1, 1000, total).astype(np.uint64)
        in_int = rng.integers(0, 1024, total).astype(np.uint32)
        in_double = rng.random(total).astype(np.float64)

        out_float = np.zeros(total * DIM, dtype=np.float32)
        out_ulong = np.zeros(total * DIM * DIM, dtype=np.uint64)
        out_int = np.zeros(total, dtype=np.int32)
        out_long = np.zeros(total, dtype=np.int64)
        out_double = np.zeros(total, dtype=np.float64)

        if backend == "gpu" and not self.use_opencl:
            raise RuntimeError(f"OpenCL backend requested but unavailable: {self.gpu_error}")
        if backend == "cpu" or not self.use_opencl:
            return self._execute_cpu(
                punch_ids,
                in_float,
                in_ulong,
                in_int,
                in_double,
                out_float,
                out_ulong,
                out_int,
                out_long,
                out_double,
                total,
                N,
            )
        return self._execute_gpu(
            punch_ids,
            in_float,
            in_ulong,
            in_int,
            in_double,
            out_float,
            out_ulong,
            out_int,
            out_long,
            out_double,
            total,
            N,
        )

    def dispatch(
        self,
        punch_ids,
        in_float,
        in_ulong,
        in_int,
        in_double,
        out_float,
        out_ulong,
        out_int,
        out_long,
        out_double,
        total,
        n_per_punch,
    ) -> Dict[str, np.ndarray]:
        """Route one caller-supplied batch through the real backend.

        Same contract as :meth:`_execute_gpu`/:meth:`_execute_cpu`, but
        selects OpenCL when usable and records ``last_dispatch_backend``
        so callers can report the backend that actually executed.
        """
        if self.use_opencl:
            return self._execute_gpu(
                punch_ids,
                in_float,
                in_ulong,
                in_int,
                in_double,
                out_float,
                out_ulong,
                out_int,
                out_long,
                out_double,
                total,
                n_per_punch,
            )
        return self._execute_cpu(
            punch_ids,
            in_float,
            in_ulong,
            in_int,
            in_double,
            out_float,
            out_ulong,
            out_int,
            out_long,
            out_double,
            total,
            n_per_punch,
        )

    def run_punch_batch(
        self,
        punch_id: int,
        *,
        in_float=None,
        in_ulong=None,
        in_int=None,
        in_double=None,
        n_per_punch: Optional[int] = None,
        n: Optional[int] = None,
    ) -> Dict[str, np.ndarray]:
        """Dispatch one punch over N caller-supplied work-items.

        Any subset of the four input channels may be provided; the rest are
        zero-filled. ``last_dispatch_backend`` records the backend that
        actually executed ("opencl:gpu"/"opencl:cpu"/"cpu").
        """
        if n is None:
            per_item = [a for a in (in_ulong, in_int, in_double) if a is not None and len(a)]
            if per_item:
                n = max(len(a) for a in per_item)
            elif in_float is not None and len(in_float):
                n = max(1, len(in_float) // DIM)
            else:
                raise ValueError("run_punch_batch requires at least one input channel")
        if punch_id not in self.SUPPORTED_PUNCH_IDS:
            raise ValueError(f"unsupported punch id 0x{int(punch_id):02X}")
        in_float = (
            np.zeros(n * DIM, dtype=np.float32)
            if in_float is None
            else np.asarray(in_float, dtype=np.float32)
        )
        in_ulong = (
            np.zeros(n, dtype=np.uint64)
            if in_ulong is None
            else np.asarray(in_ulong, dtype=np.uint64)
        )
        in_int = (
            np.zeros(n, dtype=np.int32) if in_int is None else np.asarray(in_int, dtype=np.int32)
        )
        in_double = (
            np.zeros(n, dtype=np.float64)
            if in_double is None
            else np.asarray(in_double, dtype=np.float64)
        )
        punch_ids = np.full(n, punch_id, dtype=np.uint32)
        writes = _PUNCH_WRITES.get(punch_id, _ALL_CHANNELS)
        out_float = np.zeros(n * DIM if "float" in writes else 1, dtype=np.float32)
        out_ulong = np.zeros(n * DIM * DIM if "ulong" in writes else 1, dtype=np.uint64)
        out_int = np.zeros(n if "int" in writes else 1, dtype=np.int32)
        out_long = np.zeros(n if "long" in writes else 1, dtype=np.int64)
        out_double = np.zeros(n if "double" in writes else 1, dtype=np.float64)
        return self.dispatch(
            punch_ids,
            in_float,
            in_ulong,
            in_int,
            in_double,
            out_float,
            out_ulong,
            out_int,
            out_long,
            out_double,
            n,
            n_per_punch or n,
        )

    # ------------------------------------------------------------------
    # Device buffer pool / output contract
    # ------------------------------------------------------------------

    def _release_device_buffers(self) -> None:
        """Drop every pooled device buffer (GC reclaims the cl objects)."""
        pool = getattr(self, "_buf_pool", None)
        if pool:
            pool.clear()

    def _pooled_buffer(self, name: str, nbytes: int):
        """Grow-only device buffer reused across dispatches.

        Per-dispatch ``cl.Buffer`` churn on shared-memory devices (iGPU,
        WSL2) is not reclaimed promptly by the driver — repeated ~200 MB
        score-window allocations exhaust host memory mid-session
        (OUT_OF_HOST_MEMORY). Pooling allocates each channel once at its
        largest requested size; sub-region views keep copies size-exact.
        """
        nbytes = max(int(nbytes), 8)
        entry = self._buf_pool.get(name)
        if entry is None or entry[1] < nbytes:
            entry = (cl.Buffer(self.ctx, cl.mem_flags.READ_WRITE, nbytes), nbytes)
            self._buf_pool[name] = entry
        return entry[0]

    def _resolve_output_writes(self, punch_ids, total, outs) -> frozenset:
        """Channels the batch actually writes + caller buffer validation.

        Returns the union of written channels for the dispatched punch set.
        A written channel whose caller array is smaller than
        ``total * channel width`` would overflow the kernel's own-block
        addressing — rejected here instead of corrupting device memory.
        """
        writes = set()
        if total:
            ids = np.asarray(punch_ids)[:total]
            for pid in np.unique(ids):
                writes |= _PUNCH_WRITES.get(int(pid), _ALL_CHANNELS)
        for name in writes:
            need = int(total) * _CHANNEL_WIDTH[name]
            have = int(np.asarray(outs[name]).size)
            if have < need:
                raise ValueError(
                    f"out_{name} has {have} elements but the dispatched "
                    f"punch set writes {need} (total={total})"
                )
        return frozenset(writes)

    def _resolve_input_reads(self, punch_ids, total) -> frozenset:
        """Channels the batch actually reads, per the kernel switch.

        Only used to skip uploading untouched input channels; caller input
        arrays keep their existing contract either way.
        """
        reads = set()
        if total:
            ids = np.asarray(punch_ids)[:total]
            for pid in np.unique(ids):
                reads |= _PUNCH_READS.get(int(pid), _ALL_INPUT_CHANNELS)
        return frozenset(reads)

    def close(self) -> None:
        """Finish the command queue and release pooled device buffers."""
        queue = getattr(self, "queue", None)
        if queue is not None:
            try:
                queue.finish()
            except Exception:
                pass
        self._release_device_buffers()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_gpu(
        self,
        punch_ids,
        in_float,
        in_ulong,
        in_int,
        in_double,
        out_float,
        out_ulong,
        out_int,
        out_long,
        out_double,
        total,
        n_per_punch,
    ) -> Dict[str, np.ndarray]:
        outs = {
            "float": out_float,
            "ulong": out_ulong,
            "int": out_int,
            "long": out_long,
            "double": out_double,
        }
        writes = self._resolve_output_writes(punch_ids, total, outs)
        reads = self._resolve_input_reads(punch_ids, total)
        if total <= 0:
            self._emit_telemetry(punch_ids, 0, n_per_punch)
            return dict(outs)
        unsupported = sorted({int(pid) for pid in np.unique(np.asarray(punch_ids)[:total]) if int(pid) not in self.SUPPORTED_PUNCH_IDS})
        if unsupported:
            bad = ", ".join(f"0x{pid:02X}" for pid in unsupported)
            raise ValueError(f"unsupported punch ids: {bad}")
        last_exc = None
        for attempt in (0, 1):
            try:
                return self._dispatch_opencl(
                    punch_ids,
                    in_float,
                    in_ulong,
                    in_int,
                    in_double,
                    outs,
                    total,
                    n_per_punch,
                    writes,
                    reads,
                )
            except cl.Error as exc:
                last_exc = exc
                self._release_device_buffers()
                if attempt == 0:
                    logger.warning("OpenCL dispatch failed; retrying once: %s", exc)
        # The device path is dead for this session — degrade honestly instead
        # of killing the mining loop. ``backend``, ``device_info`` and
        # ``gpu_error`` report the truth, and ``dispatch`` routes straight
        # to CPU from here on.
        degraded_from = self.device_info.get("name", "unknown")
        self.gpu_error = f"dispatch failed twice, degraded to CPU: {last_exc}"
        self.use_opencl = False
        self.device_info = {
            "type": "cpu_fallback",
            "name": "cpu",
            "hyba_alias": None,
            "degraded_from": degraded_from,
            "opencl_error": str(last_exc),
        }
        logger.error(
            "OpenCL dispatch failed twice; falling back to CPU: %s", last_exc
        )
        return self._execute_cpu(
            punch_ids,
            in_float,
            in_ulong,
            in_int,
            in_double,
            out_float,
            out_ulong,
            out_int,
            out_long,
            out_double,
            total,
            n_per_punch,
        )

    def _dispatch_opencl(
        self,
        punch_ids,
        in_float,
        in_ulong,
        in_int,
        in_double,
        outs,
        total,
        n_per_punch,
        writes,
        reads,
    ) -> Dict[str, np.ndarray]:
        """One kernel launch over pooled buffers; reads back written channels."""
        scratch = self._pooled_buffer("_scratch", 8)
        in_bufs = {}
        for name, arr in (
            ("punch", punch_ids),
            ("in_float", in_float),
            ("in_ulong", in_ulong),
            ("in_int", in_int),
            ("in_double", in_double),
        ):
            # punch_ids is always consumed; the other channels only when the
            # batch's punches actually read them (kernel-switch parity).
            if name != "punch" and name[3:] not in reads:
                in_bufs[name] = scratch
                continue
            arr = np.ascontiguousarray(arr)
            buf = self._pooled_buffer(name, arr.nbytes)
            cl.enqueue_copy(self.queue, buf.get_sub_region(0, arr.nbytes), arr)
            in_bufs[name] = buf
        out_bufs = {
            name: (
                self._pooled_buffer("out_" + name, arr.nbytes)
                if name in writes
                else scratch
            )
            for name, arr in outs.items()
        }

        evt = self.kernel(
            self.queue,
            (total,),
            None,
            in_bufs["in_float"],
            in_bufs["in_ulong"],
            in_bufs["in_int"],
            in_bufs["in_double"],
            in_bufs["punch"],
            out_bufs["float"],
            out_bufs["ulong"],
            out_bufs["int"],
            out_bufs["long"],
            out_bufs["double"],
            np.uint32(total),
            np.uint32(n_per_punch),
        )
        evt.wait()
        self.last_kernel_ms = (evt.profile.end - evt.profile.start) / 1e6
        self.last_dispatch_backend = self.backend
        self.dispatch_count = getattr(self, "dispatch_count", 0) + 1
        self.kernel_ms_total = getattr(self, "kernel_ms_total", 0.0) + self.last_kernel_ms

        for name in writes:
            arr = outs[name]
            cl.enqueue_copy(
                self.queue, arr, out_bufs[name].get_sub_region(0, arr.nbytes)
            )
        self.queue.finish()
        self._emit_telemetry(punch_ids, total, n_per_punch)
        return dict(outs)

    def _execute_cpu(
        self,
        punch_ids,
        in_float,
        in_ulong,
        in_int,
        in_double,
        out_float,
        out_ulong,
        out_int,
        out_long,
        out_double,
        total,
        N,
    ) -> Dict[str, np.ndarray]:
        """numpy fallback — mirrors the kernel semantics exactly."""
        self._resolve_output_writes(
            punch_ids,
            total,
            {
                "float": out_float,
                "ulong": out_ulong,
                "int": out_int,
                "long": out_long,
                "double": out_double,
            },
        )
        self.last_dispatch_backend = "cpu"
        self.dispatch_count = getattr(self, "dispatch_count", 0) + 1
        # float32 weights to mirror the kernel's pown((float)PHI, -(j+1)).
        w32 = np.array(
            [np.float32(PHI) ** np.float32(-(j + 1)) for j in range(DIM)],
            dtype=np.float32,
        )

        def _norm_sq_f32(vec):
            """Serial float32 accumulation — same order as the kernel."""
            s = np.float32(0)
            for j in range(DIM):
                c = np.float32(vec[j])
                s = np.float32(s + np.float32(w32[j] * c * c))
            return s

        for i in range(total):
            punch = punch_ids[i]
            gid = i
            if punch == 0x01:  # cassini_power (mod 2^64 like the kernel)
                n = int(in_ulong[gid])
                a, b = 0, 1
                for bit in range(63, -1, -1):
                    d = (a * (2 * b - a)) & MASK64
                    e = (a * a + b * b) & MASK64
                    if (n >> bit) & 1:
                        a, b = e, (d + e) & MASK64
                    else:
                        a, b = d, e
                base = gid * DIM * DIM
                for r in range(DIM):
                    for c in range(DIM):
                        val = 0
                        if r == c:
                            val = a
                        elif c == r + 1:
                            val = b
                        elif r == c + 1:
                            val = (b - a) & MASK64
                        out_ulong[base + r * DIM + c] = val
            elif punch == 0x02:  # zeckendorf_encode (own-block write)
                n = int(in_ulong[gid])
                fib = [1, 2]
                while fib[-1] <= n:
                    fib.append(fib[-1] + fib[-2])
                mask = 0
                for j, f in enumerate(reversed(fib[:-1])):
                    if f <= n:
                        mask |= 1 << (len(fib) - 2 - j)
                        n -= f
                out_ulong[gid * DIM * DIM] = mask & MASK64
                out_ulong[gid * DIM * DIM + 1] = (mask >> 64) & MASK64
            elif punch == 0x1C:  # zeckendorf_decode (2-slot input)
                i = gid % N if N else gid
                lo = int(in_ulong[i * 2])
                hi = int(in_ulong[i * 2 + 1])
                mask = lo | (hi << 64)
                n = 0
                a, b = 1, 2
                while mask:
                    if mask & 1:
                        n += a
                    mask >>= 1
                    a, b = b, a + b
                out_ulong[gid * DIM * DIM] = n & MASK64
            elif punch == 0x03:  # pisot_schedule
                eps = max(float(in_double[gid]), 1e-300)
                phi = (np.sqrt(5) - 1) / 2
                n = int(min(np.ceil(np.log(eps) / np.log(phi)), 1024))
                out_int[gid] = n
                out_double[gid] = phi**n
            elif punch == 0x04:  # diophantine_check (wrapped neighbour q)
                p = int(in_ulong[gid])
                q = int(in_ulong[(gid + 1) % total])
                if q == 0:
                    out_int[gid] = 0
                else:
                    phi = (np.sqrt(5) - 1) / 2
                    approx = p / q
                    bound = 1 / (np.sqrt(5) * q * q)
                    out_int[gid] = 1 if abs(phi - approx) >= bound - 1e-15 else 0
            elif punch == 0x05:  # golden_angle (own-slice write)
                theta = np.float32(gid) * np.float32(2.39996322972865332)
                out_float[gid * DIM + 0] = np.cos(theta)
                out_float[gid * DIM + 1] = np.sin(theta)
            elif punch == 0x06:  # fold_topology (k=4 passthrough)
                side = 1 << 2
                if gid < side * side:
                    out_float[gid * DIM] = in_float[gid]
            elif punch == 0x07:  # spectral_gap (own-slice writes)
                n = int(in_ulong[gid])
                with np.errstate(over="ignore", invalid="ignore"):
                    phi_n = np.power(np.float64(PHI), np.float64(n))
                    psi_n = np.power(np.float64(PSI), np.float64(n))
                    out_float[gid * DIM + 0] = np.float32(phi_n)
                    out_float[gid * DIM + 1] = np.float32(SQRT5)
                    out_float[gid * DIM + 2] = np.float32(phi_n + psi_n)
            elif punch == 0x08:  # poincare_fold
                x = in_float[gid * DIM : (gid + 1) * DIM]
                norm_sq = _norm_sq_f32(x)
                denom = np.sqrt(np.float32(1.0) + norm_sq)
                for j in range(DIM):
                    out_float[gid * DIM + j] = np.float32(x[j] / denom)
            elif punch == 0x09:  # poincare_unfold
                x = in_float[gid * DIM : (gid + 1) * DIM]
                norm_sq = _norm_sq_f32(x)
                clamped = np.float32(min(norm_sq, np.float32(1 - 1e-6)))
                denom = np.sqrt(np.float32(max(np.float32(1e-6), np.float32(1 - clamped))))
                for j in range(DIM):
                    out_float[gid * DIM + j] = np.float32(x[j] / denom)
            elif punch == 0x0A:  # geodesic_distance
                v_idx = (gid + DIM * N) % total
                u = in_float[gid * DIM : (gid + 1) * DIM]
                v = in_float[v_idx * DIM : (v_idx + 1) * DIM]
                norm_u = _norm_sq_f32(u)
                norm_v = _norm_sq_f32(v)
                diff_sq = _norm_sq_f32(u - v)
                denom = (np.float32(1) - norm_u) * (np.float32(1) - norm_v)
                arg = np.float32(1) + np.float32(2) * diff_sq / np.float32(
                    max(denom, np.float32(1e-15))
                )
                out_float[gid * DIM] = np.arccosh(max(arg, np.float32(1.0)))
            elif punch == 0x0B:  # mint_certificate (own-block token write)
                token = 0
                mask = 0
                for j in range(DIM):
                    # float32 ops to match the kernel bit-for-bit.
                    coord = np.float32(in_float[gid * DIM + j])
                    quantized = int(np.float32(abs(coord)) * np.float32(1364)) & 0xFFFF
                    token = (token << 4) | (quantized & 0xF)
                    if abs(coord) > 0.5:
                        mask |= 1 << j
                out_ulong[gid * DIM * DIM] = token
                out_int[gid] = mask
            elif punch == 0x0C:  # salamander_alloc
                token = int(in_ulong[gid])
                mask = int(in_int[gid])
                k = token % PRIME_COUNT
                out_int[gid] = k * SLOTS_PER_PRIME + mask % PRIMES[k]
            elif punch == 0x0D:  # beatty_partition
                alpha = 1.6180339887498949
                out_int[gid] = int(np.floor((gid + 1) * alpha)) % N
            elif punch == 0x0E:  # cassini_det
                k = int(in_ulong[gid])
                out_long[gid] = 1 if (k % 2) == 0 else -1
            elif punch == 0x0F:  # decoupling_mask
                M = int(in_int[gid])
                out_int[gid] = 1 if (M & (M << 1)) == 0 else 0
            elif punch == 0x10:  # millennium_verify
                problem = int(in_int[gid]) % 7
                bounds = [0.001, 15.0, 0.5, 2.0, 1.0, 1.0, 1.0]
                out_int[gid] = 1
                out_float[gid * DIM] = bounds[problem]
            elif punch == 0x11:  # schema_split
                out_float[gid * DIM] = in_float[gid]
                out_int[gid] = 0
            elif punch == 0x15:  # manifold_compute
                x = in_float[gid * DIM : (gid + 1) * DIM]
                out_float[gid * DIM] = _norm_sq_f32(x)
            elif punch == 0x16:  # millennium_all
                bounds = [0.001, 15.0, 0.5, 2.0, 1.0, 1.0, 1.0]
                for j in range(7):
                    out_float[gid * DIM + j] = bounds[j]
            elif punch == 0x17:  # hard_gate
                valid = int(in_int[gid])
                M = int(in_int[(gid + 1) % total])
                non_adj = 1 if (M & (M << 1)) == 0 else 0
                out_int[gid] = 1 if (valid and non_adj) else 0
            elif punch == 0x18:  # schema_enforce
                out_float[gid * DIM] = in_float[gid]
                out_int[gid] = 0
            elif punch == 0x19:  # immutable_proof
                out_int[gid] = 0
            elif punch == 0x1B:  # sha256d_grind_mark (own-block write)
                params = in_ulong[:3] if len(in_ulong) >= 3 else [0, 1, 1]
                nonce_start = int(params[0])
                window = int(params[1]) if int(params[1]) > 0 else 1
                stride = int(params[2]) if int(params[2]) > 0 else 1
                nonce = (nonce_start + gid * stride) % window + nonce_start
                nonce = nonce & 0xFFFFFFFF
                base = gid * DIM * DIM
                out_ulong[base + 0] = nonce
                out_ulong[base + 1] = stride
                out_int[gid] = 1
        self._emit_telemetry(punch_ids, total, N)
        return {
            "float": out_float,
            "ulong": out_ulong,
            "int": out_int,
            "long": out_long,
            "double": out_double,
        }

    # ------------------------------------------------------------------
    # Benchmark / telemetry
    # ------------------------------------------------------------------

    def benchmark(self, N: int = 1024, iterations: int = 10) -> Dict[str, Any]:
        self.execute_all_punches(N)
        kernel_ms = []
        start = time.perf_counter()
        for _ in range(iterations):
            self.execute_all_punches(N)
            if self.last_kernel_ms is not None:
                kernel_ms.append(self.last_kernel_ms)
        elapsed = (time.perf_counter() - start) / iterations
        # Nominal model: ~30 primitive ops per work-item per punch.
        total_ops = N * len(self.PUNCH_IDS) * 30
        return {
            "elapsed_seconds": elapsed,
            "teraops": total_ops / elapsed / 1e12,
            "backend": self.backend,
            "device": self.device_info.get("name", "cpu"),
            "device_type": self.device_info.get("type", "cpu"),
            "compute_units": self.device_info.get("compute_units", 0),
            "work_items": N * len(self.PUNCH_IDS),
            "kernel_ms": float(np.mean(kernel_ms)) if kernel_ms else None,
            "gpu_error": self.gpu_error,
        }

    def telemetry(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "opencl_available": self.use_opencl,
            "device_info": self.device_info,
            "gpu_error": self.gpu_error,
            "punch_count": len(self.PUNCH_IDS),
        }


# ----------------------------------------------------------------------
# Millennium sector dataclasses
# ----------------------------------------------------------------------

from dataclasses import dataclass  # noqa: E402


@dataclass
class ComputationalGeodesicSector:
    name: str = "P vs NP"

    def invariant(self):
        return SQRT5


@dataclass
class GaugeBundleSector:
    name: str = "Yang-Mills"

    def invariant(self):
        return PHI**-15


@dataclass
class SpectralOperatorSector:
    name: str = "Riemann"

    def invariant(self):
        return 0.5


@dataclass
class VectorFieldSector:
    name: str = "Navier-Stokes"

    def invariant(self):
        return 2.39996322972865332


@dataclass
class EllipticFibrationSector:
    name: str = "BSD"

    def invariant(self):
        return 1


@dataclass
class CohomologySector:
    name: str = "Hodge"

    def invariant(self):
        return (PHI, PSI)


@dataclass
class TopologySector:
    name: str = "Poincare"

    def invariant(self):
        return "S^3"


def _cassini_matrix() -> np.ndarray:
    Q = np.zeros((DIM, DIM))
    for i in range(DIM - 1):
        Q[i, i + 1] = 1.0
    Q[0, 0] = 1.0
    Q[1, 0] = 1.0
    Q[0, 1] = 1.0
    return Q


class MTheoryManifold:
    """11D sector registry + Cassini-matrix spectral verification.

    The Cassini matrix has eigenvalues {phi, -1/phi, 0 x9}: its spectral
    spread (max - min eigenvalue) is sqrt(5) and exactly one eigenvalue is
    >= 1 in magnitude — the Pisot property.
    """

    def __init__(self):
        self.dim = DIM
        self.compact = 7
        self.noncompact = 4
        self._runtime: Optional[UnifiedPhiRuntime] = None
        self.sectors = {
            "P_vs_NP": ComputationalGeodesicSector(),
            "Yang_Mills": GaugeBundleSector(),
            "Riemann": SpectralOperatorSector(),
            "Navier_Stokes": VectorFieldSector(),
            "BSD": EllipticFibrationSector(),
            "Hodge": CohomologySector(),
            "Poincare": TopologySector(),
        }

    @property
    def runtime(self) -> "UnifiedPhiRuntime":
        """Lazily constructed so manifold checks don't pay OpenCL init cost."""
        if self._runtime is None:
            self._runtime = UnifiedPhiRuntime()
        return self._runtime

    def compute_all(self) -> Dict[str, Any]:
        return {name: s.invariant() for name, s in self.sectors.items()}

    def verify_manifold(self) -> Dict[str, bool]:
        eig = np.linalg.eigvals(_cassini_matrix())
        spread = float(eig.real.max() - eig.real.min())
        n_big = int(np.sum(np.abs(eig) >= 1.0 - 1e-12))
        return {
            "dim_11": self.dim == 11,
            "compact_7": self.compact == 7,
            "noncompact_4": self.noncompact == 4,
            "dominant_eigenvalue_phi": abs(float(eig.real.max()) - PHI) < 1e-9,
            "spectral_spread_sqrt5": abs(spread - SQRT5) < 1e-9,
            "pisot": n_big == 1,
        }


class UnifiedPhiRuntime:
    """Classical unified-punch runtime with an optional quantum backend.

    A quantum backend can be injected as any object exposing
    ``quantum_phase_estimation()``, ``quantum_hamiltonian_simulation(n)``,
    ``quantum_grover_search(target)`` and ``get_telemetry()``. When absent,
    provenance honestly reports ``QUANTUM_UNAVAILABLE``.
    """

    def __init__(
        self,
        kernel_path: Optional[str] = None,
        quantum_backend: Optional[Any] = None,
    ):
        self.punch_host = UnifiedPunchHost(kernel_path)
        self.quantum = quantum_backend

    @property
    def quantum_available(self) -> bool:
        return self.quantum is not None

    def compute_all_punches(self, N: int = 1024) -> Dict[str, Any]:
        classical = self.punch_host.execute_all_punches(N)
        quantum: Dict[str, Any] = {}
        tel: Dict[str, Any] = {}
        if self.quantum is not None:
            quantum = {
                "quantum_phase": self.quantum.quantum_phase_estimation(),
                "quantum_hamiltonian": self.quantum.quantum_hamiltonian_simulation(15),
                "quantum_grover": self.quantum.quantum_grover_search(0),
            }
            tel = self.quantum.get_telemetry()
        else:
            tel = {"quantum_claim": "QUANTUM_UNAVAILABLE", "is_real_qpu": False}
        return {
            "classical": classical,
            "quantum": quantum,
            "provenance": {
                "classical_backend": self.punch_host.backend,
                "classical_device": self.punch_host.device_info.get("name", "cpu"),
                "quantum_backend": tel.get("backend_name", "none"),
                "is_real_qpu": bool(tel.get("is_real_qpu", False)),
                "quantum_claim": tel.get("quantum_claim", "QUANTUM_UNAVAILABLE"),
                "classical_punches": len(self.punch_host.PUNCH_IDS),
                "quantum_punches": 3 if self.quantum_available else 0,
                "manifold_dim": DIM,
            },
        }

    def benchmark(self, N: int = 1024) -> Dict[str, Any]:
        return self.punch_host.benchmark(N)


if __name__ == "__main__":
    runtime = UnifiedPhiRuntime()
    result = runtime.compute_all_punches(N=256)
    print("Classical punches:", len(runtime.punch_host.PUNCH_IDS))
    print("Classical backend:", result["provenance"]["classical_backend"])
    print("Classical device:", result["provenance"]["classical_device"])
    print("Quantum claim:", result["provenance"]["quantum_claim"])
    manifold = MTheoryManifold()
    print("Manifold verification:", manifold.verify_manifold())
    print("Millennium invariants:", manifold.compute_all())
