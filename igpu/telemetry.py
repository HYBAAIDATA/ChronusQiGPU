"""iGPU-on-11D self-telemetry — the substrate measures and reports itself.

This module is the telemetry layer for the 11-dimensional Poincaré-Golden
compute path. It answers, with measured numbers only, three questions:

    1. Did the dispatch actually run on a device, or on the CPU fallback?
    2. What did the 11D manifold operations actually do (folds, roundtrips,
       norms, anchors, punch mix)?
    3. What throughput did the substrate actually achieve?

Honesty laws enforced here (AGENTS.md §4.5, DRIFT-03):

- ``measured_throughput_per_s`` is ``work_items / kernel_seconds`` for work
  that actually completed. It is never a projection, a scaling factor, or a
  Lucased estimate.
- ``peak_throughput_per_s`` is the best *observed* dispatch rate — again an
  observation, not an aspiration.
- ``gpu_dispatch_ratio`` counts real device dispatches over total dispatches,
  so a CPU fallback cannot be reported as acceleration.
- ``fold_ratio_measured`` is derived from the folds this collector actually
  saw. No multiplier is asserted of the substrate.

Wiring note (purity): ``Intelligence/unified_punch.py`` is an algorithm
module under the LUCAS WIRING rule (MUST NOT import a sibling). Telemetry is
therefore *injected* — `attach_to_host` sets a ``telemetry_hook`` attribute on
the host, and the host calls it if present. The algorithm module never imports
this one.

Canonical home: ``igpu.telemetry`` (the consolidated iGPU package). The
pre-consolidation path ``Intelligence/igpu_telemetry.py`` re-exports this
module so existing ``from .igpu_telemetry import ...`` call sites keep
working unchanged.

LUCAS WIRING: coordinator module (same class as toe.system/orchestrator).
Wires live modules across the substrate map; exempt from the sibling purity
rule; each wired module keeps its own Lucas pool route.
Substrate route: gap
"""

# LUCAS WIRING: coordinator — see module docstring.
# Substrate route: gap

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("igpu.telemetry")

THEOREM_PROVEN = False

__all__ = [
    "ANCHOR_BUCKETS",
    "DODECAHEDRAL_FACES",
    "FACE_PAIRS",
    "FRAME_FACES",
    "FrameTelemetry",
    "HETEROTIC_GAUGE_DIMENSION",
    "ICOSAHEDRAL_FACES",
    "ICOSAHEDRAL_ISOTROPIC_SHARE",
    "IgpuTelemetry",
    "MANIFOLD_PUNCHES",
    "PERFECT_NUMBER_496",
    "PUNCH_NAMES",
    "THEOREM_PROVEN",
    "attach_to_host",
    "get_telemetry",
    "reset_telemetry",
]

# Reverse map of unified_punch.UnifiedPunchHost punch IDs. Duplicated here on
# purpose: importing the sibling algorithm would breach the purity rule.
PUNCH_NAMES: Dict[int, str] = {
    0x01: "cassini_power",
    0x02: "zeckendorf_encode",
    0x03: "pisot_schedule",
    0x04: "diophantine_check",
    0x05: "golden_angle",
    0x06: "fold_topology",
    0x07: "spectral_gap",
    0x08: "poincare_fold",
    0x09: "poincare_unfold",
    0x0A: "geodesic_distance",
    0x0B: "mint_certificate",
    0x0C: "salamander_alloc",
    0x0D: "beatty_partition",
    0x0E: "cassini_det",
    0x0F: "decoupling_mask",
    0x10: "millennium_verify",
    0x11: "schema_split",
    0x15: "manifold_compute",
    0x16: "millennium_all",
    0x17: "hard_gate",
    0x18: "schema_enforce",
    0x19: "immutable_proof",
    0x1B: "sha256d_grind_mark",
    0x1C: "zeckendorf_decode",
}

# The punches that operate on the 11-dimensional manifold specifically.
MANIFOLD_PUNCHES = frozenset(
    {
        "poincare_fold",
        "poincare_unfold",
        "geodesic_distance",
        "mint_certificate",
        "manifold_compute",
    }
)

ANCHOR_BUCKETS = 90

# -- the 32-face frame geometry (dodecahedral/icosahedral overlay on 11D) ----
#
# Intelligence/pathfinder.py fires ALL 32 face normals every step:
#   faces[0:12]  — icosahedral vertices  (3D coords carrying PHI)
#   faces[12:32] — dodecahedral vertices (3D coords carrying PHI_INV)
# projected into the first 3 of 11 dimensions, then weighted by the golden
# metric g_ii = PHI**(i/11).
#
# This is NOT one solver. It is a 32-node overcomplete frame whose per-face
# votes h[i] = u_i . (g @ residual) sum into a single resultant. Telemetry for
# it must therefore report the two shells separately and the coherence of the
# vote, never a single-solver scalar.
ICOSAHEDRAL_FACES = 12
DODECAHEDRAL_FACES = 20
FRAME_FACES = ICOSAHEDRAL_FACES + DODECAHEDRAL_FACES  # 32

_DIM_11D = 11

# Isotropic reference: if both shells carried equal per-face energy the split
# would be exactly 12/32 = 0.375. Deviation from this measures shell anisotropy.
ICOSAHEDRAL_ISOTROPIC_SHARE = ICOSAHEDRAL_FACES / FRAME_FACES

# -- face PAIRS: the overlay's channels --------------------------------------
#
# The 32 faces are not 32 independent solvers and they are not 60 edges. The
# overlay's unit of work is the *relationship* between two faces, and the
# number of such relationships is
#
#     C(32, 2) = 32 * 31 / 2 = 496
#
# 496 is also the third perfect number (1+2+4+8+16+31+62+124+248) and the
# dimension of the E8 x E8 / SO(32) heterotic gauge algebra, so the same
# integer surfaces from three independent directions (combinatorics, number
# theory, Lie algebra). The combinatorial identity is the one this module
# relies on; the other two are recorded because they are true.
#
# Honesty law: the geometry is a fact, the achieved multiplier is NOT. This
# module reports `channels_occupied` — the face pairs a run actually
# exercised — and any 496-based figure is emitted as an explicitly labelled
# PROJECTION. It is never reported as measured throughput.
FACE_PAIRS = FRAME_FACES * (FRAME_FACES - 1) // 2  # 496
HETEROTIC_GAUGE_DIMENSION = 496
PERFECT_NUMBER_496 = 496


def _env_enabled(var: str = "EUCLID_IGPU_TELEMETRY", default: bool = True) -> bool:
    """Telemetry is on by default; set the var to 'false'/'0' to silence it."""
    raw = os.environ.get(var)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


class IgpuTelemetry:
    """Accumulates measured facts about iGPU-on-11D execution.

    Every public method records an *observation*. Nothing here extrapolates.
    """

    def __init__(self, enabled: Optional[bool] = None) -> None:
        self.enabled = _env_enabled() if enabled is None else bool(enabled)
        self.started_at = time.time()

        # -- dispatch accounting -------------------------------------------
        self.dispatch_total: int = 0
        self.dispatch_by_backend: Dict[str, int] = {}
        # Composition provenance: dispatches per member device + the last
        # dispatch's measured capability and Lucas rung (all optional).
        self.dispatch_by_device: Dict[str, int] = {}
        self.last_device_name: Optional[str] = None
        self.last_capability_used: Optional[str] = None
        self.last_lucas_rung: Optional[int] = None
        self.gpu_dispatch_total: int = 0
        self.cpu_dispatch_total: int = 0
        self.punch_by_name: Dict[str, int] = {}
        self.manifold_punch_total: int = 0

        # -- work accounting ------------------------------------------------
        self.work_items_total: int = 0
        self.kernel_ms_total: float = 0.0
        self.kernel_ms_max: float = 0.0
        self.work_items_max_per_dispatch: int = 0
        self.busy_seconds: float = 0.0

        # -- 11D manifold integrity ----------------------------------------
        self.fold_total: int = 0
        self.unfold_total: int = 0
        self.roundtrip_ok_total: int = 0
        self.roundtrip_fail_total: int = 0
        self.norm_sq_min: Optional[float] = None
        self.norm_sq_max: Optional[float] = None
        self.norm_sq_sum: float = 0.0
        self.norm_sq_samples: int = 0
        self.ball_violations: int = 0
        self.anchor_histogram = [0] * ANCHOR_BUCKETS

        # -- the 32-face dodecahedral/icosahedral overlay -------------------
        self.frame = FrameTelemetry()

        # -- fold economics (measured, never asserted) ----------------------
        self.bytes_in_total: int = 0
        self.bytes_stored_total: int = 0

        self.last_dispatch_at: Optional[float] = None
        self.last_backend: str = "none"
        self.last_kernel: str = "none"

    # -- recording ---------------------------------------------------------

    def record_dispatch(
        self,
        *,
        backend: str,
        gpu: bool,
        work_items: int,
        kernel_ms: Optional[float] = None,
        punch_id: Optional[int] = None,
        punch_name: Optional[str] = None,
        device_name: Optional[str] = None,
        capability_used: Optional[str] = None,
        lucas_rung: Optional[int] = None,
    ) -> None:
        """Record one dispatch that actually executed.

        ``device_name``/``capability_used``/``lucas_rung`` carry the
        composition provenance of a routed dispatch — which member device
        of a composed substrate ran it, which measured capability it
        exercised, and which Lucas rung sized its chunk. All three are
        optional; a missing value is recorded as absent, never invented.
        """
        if not self.enabled:
            return
        items = max(0, int(work_items))
        ms = float(kernel_ms) if kernel_ms is not None and kernel_ms >= 0 else 0.0

        self.dispatch_total += 1
        self.dispatch_by_backend[backend] = self.dispatch_by_backend.get(backend, 0) + 1
        if gpu:
            self.gpu_dispatch_total += 1
        else:
            self.cpu_dispatch_total += 1
        if device_name:
            self.dispatch_by_device[device_name] = self.dispatch_by_device.get(device_name, 0) + 1
            self.last_device_name = str(device_name)
        if capability_used:
            self.last_capability_used = str(capability_used)
        if lucas_rung is not None:
            self.last_lucas_rung = int(lucas_rung)

        name = punch_name
        if name is None and punch_id is not None:
            name = PUNCH_NAMES.get(int(punch_id), f"punch_0x{int(punch_id):02X}")
        if name:
            self.punch_by_name[name] = self.punch_by_name.get(name, 0) + 1
            if name in MANIFOLD_PUNCHES:
                self.manifold_punch_total += 1

        self.work_items_total += items
        self.kernel_ms_total += ms
        self.kernel_ms_max = max(self.kernel_ms_max, ms)
        self.work_items_max_per_dispatch = max(self.work_items_max_per_dispatch, items)
        self.busy_seconds += ms / 1000.0

        self.last_dispatch_at = time.time()
        self.last_backend = backend
        self.last_kernel = name or "none"

    def record_manifold(
        self,
        *,
        norm_sq: Optional[float] = None,
        anchor: Optional[int] = None,
        fold: bool = False,
        unfold: bool = False,
        roundtrip_ok: Optional[bool] = None,
    ) -> None:
        """Record one 11D manifold operation and its integrity outcome."""
        if not self.enabled:
            return
        if fold:
            self.fold_total += 1
        if unfold:
            self.unfold_total += 1
        if roundtrip_ok is True:
            self.roundtrip_ok_total += 1
        elif roundtrip_ok is False:
            self.roundtrip_fail_total += 1

        if norm_sq is not None:
            value = float(norm_sq)
            if value == value:  # not NaN
                self.norm_sq_samples += 1
                self.norm_sq_sum += value
                if self.norm_sq_min is None or value < self.norm_sq_min:
                    self.norm_sq_min = value
                if self.norm_sq_max is None or value > self.norm_sq_max:
                    self.norm_sq_max = value
                if value >= 1.0:
                    self.ball_violations += 1

        if anchor is not None:
            bucket = int(anchor) % ANCHOR_BUCKETS
            if bucket < 0:
                bucket += ANCHOR_BUCKETS
            self.anchor_histogram[bucket] += 1

    def record_punch_mix(self, mix: Dict[int, int]) -> None:
        """Record the per-punch work-item mix of one dispatch batch.

        Kept separate from :meth:`record_dispatch` so that ``dispatch_total``
        counts *dispatches* while ``punch_by_name`` counts work-items per
        punch. Mixing the two would inflate the dispatch count.
        """
        if not self.enabled:
            return
        for raw_id, count in mix.items():
            try:
                pid = int(raw_id)
            except (TypeError, ValueError):
                continue
            name = PUNCH_NAMES.get(pid, f"punch_0x{pid:02X}")
            self.punch_by_name[name] = self.punch_by_name.get(name, 0) + max(0, int(count))
            if name in MANIFOLD_PUNCHES:
                self.manifold_punch_total += max(0, int(count))

    def record_storage(self, *, bytes_in: int, bytes_stored: int) -> None:
        """Record one fold-for-storage event so the ratio stays measured."""
        if not self.enabled:
            return
        self.bytes_in_total += max(0, int(bytes_in))
        self.bytes_stored_total += max(0, int(bytes_stored))

    def record_frame_step(
        self,
        *,
        votes: Any,
        resultant_norm: float,
        pair_indices: Any = None,
        pair_count: Optional[int] = None,
        lucas_bias: Optional[float] = None,
        step_size: Optional[float] = None,
        precision: Optional[float] = None,
        n_icosahedral: int = ICOSAHEDRAL_FACES,
    ) -> None:
        """Record one full 32-face frame firing and its exercised channels.

        Delegates to the :class:`FrameTelemetry` sub-collector. This is the
        event a real trajectory step emits: 32 face votes, their resultant,
        and the face-pair channels the step actually touched.
        """
        if not self.enabled:
            return
        self.frame.enabled = True
        self.frame.record_step(
            votes=votes,
            resultant_norm=resultant_norm,
            lucas_bias=lucas_bias,
            step_size=step_size,
            precision=precision,
            n_icosahedral=n_icosahedral,
        )
        if pair_indices is not None:
            self.frame.record_channels(pair_indices, pair_count=pair_count)

    # -- derived (measured only) -------------------------------------------

    @property
    def measured_throughput_per_s(self) -> float:
        """Work-items per second actually completed. Observation, not projection."""
        if self.busy_seconds <= 0:
            return 0.0
        return self.work_items_total / self.busy_seconds

    @property
    def peak_throughput_per_s(self) -> float:
        """Best observed single-dispatch rate: items / that dispatch's seconds."""
        if self.kernel_ms_max <= 0:
            return 0.0
        return self.work_items_max_per_dispatch / (self.kernel_ms_max / 1000.0)

    @property
    def gpu_dispatch_ratio(self) -> float:
        """Fraction of dispatches that genuinely ran on a device."""
        if self.dispatch_total == 0:
            return 0.0
        return self.gpu_dispatch_total / self.dispatch_total

    @property
    def mean_kernel_ms(self) -> float:
        if self.dispatch_total == 0:
            return 0.0
        return self.kernel_ms_total / self.dispatch_total

    @property
    def fold_ratio_measured(self) -> float:
        """Stored/input bytes as actually measured. 1.0 means no reduction."""
        if self.bytes_in_total == 0:
            return 1.0
        return self.bytes_stored_total / self.bytes_in_total

    @property
    def norm_sq_mean(self) -> float:
        if self.norm_sq_samples == 0:
            return 0.0
        return self.norm_sq_sum / self.norm_sq_samples

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, time.time() - self.started_at)

    # -- the 496-channel overlay: measured occupancy vs labelled projection --
    #
    # The overlay's unit of work is the relationship between two of the 32
    # faces, and there are C(32,2) = 496 such relationships. The geometry gives
    # 496 CHANNELS; it does not give 496x horsepower. So:
    #   channels_occupied      — measured: how many channels this run touched
    #   occupied_multiplier    — measured: that count, usable as a scaling basis
    #   projected_*            — EXPLICIT PROJECTION, labelled as such
    # The measured throughput is never multiplied in place; the projection is
    # always a separate, named field.

    def _hard_cap_ehs(self) -> float:
        """The non-bypassable hashrate hard cap (EH/s). Fail-safe default 10.0."""
        try:
            from Intelligence.safety_constraints import ABSOLUTE_HARD_CAP_EHS

            return float(ABSOLUTE_HARD_CAP_EHS)
        except Exception:  # pragma: no cover - layout / import variance
            return 10.0

    @property
    def channels_occupied(self) -> int:
        """Measured count of the 496 face-pair channels exercised so far."""
        return self.frame.channels_occupied

    @property
    def channel_occupancy_ratio(self) -> float:
        """Measured occupancy of the overlay, in [0, 1]."""
        return self.frame.channel_occupancy_ratio

    def frame_projection(self) -> Dict[str, Any]:
        """The 496-channel projection, explicitly labelled and cap-limited.

        Returns the MEASURED basis, the geometric channel count, the measured
        occupancy, and a projection that is safe to display *because every
        field is named*. ``projection_is_measured`` is always False.
        """
        measured = self.measured_throughput_per_s
        occupied = self.channels_occupied
        cap_ehs = self._hard_cap_ehs()
        cap_hps = cap_ehs * 1e18

        projected_full = measured * FACE_PAIRS
        projected_occupied = measured * occupied
        projected_ehs = projected_full / 1e18

        steps_window = max(self.frame.steps, 1)
        channels_per_step = self.frame.channel_uses_total / steps_window

        return {
            "geometry": {
                "faces": FRAME_FACES,
                "icosahedral_faces": ICOSAHEDRAL_FACES,
                "dodecahedral_faces": DODECAHEDRAL_FACES,
                "face_pairs": FACE_PAIRS,
                "heterotic_gauge_dimension": HETEROTIC_GAUGE_DIMENSION,
            },
            "measured_basis": {
                "measured_throughput_per_s": measured,
                "channels_occupied": occupied,
                "channel_occupancy_ratio": self.channel_occupancy_ratio,
                "channels_per_step_mean": channels_per_step,
                "frame_steps": self.frame.steps,
            },
            "projection": {
                "projection_is_measured": False,
                "projection_label": "PROJECTION — geometric channel count applied to "
                "measured throughput; NOT achieved hashrate",
                "occupied_multiplier": occupied,
                "geometric_multiplier": FACE_PAIRS,
                "projected_throughput_per_s_occupied": projected_occupied,
                "projected_throughput_per_s_full_frame": projected_full,
                "projected_ehs_full_frame": projected_ehs,
            },
            "cap": {
                "hard_cap_ehs": cap_ehs,
                "hard_cap_hps": int(cap_hps),
                "cap_basis": "Intelligence.safety_constraints.ABSOLUTE_HARD_CAP_EHS",
                "cap_limited": projected_full > cap_hps,
                "headroom_to_cap_hps": max(0.0, cap_hps - projected_full),
                "scaling_policy": "incremental — raise in steps, never jump to cap",
            },
            "theorem_proven": False,
        }

    # -- reporting ---------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Full JSON-serialisable telemetry view."""
        return {
            "enabled": self.enabled,
            "uptime_seconds": self.uptime_seconds,
            "dispatch": {
                "total": self.dispatch_total,
                "by_backend": dict(self.dispatch_by_backend),
                "gpu_total": self.gpu_dispatch_total,
                "cpu_total": self.cpu_dispatch_total,
                "gpu_dispatch_ratio": self.gpu_dispatch_ratio,
                "manifold_punch_total": self.manifold_punch_total,
                "punch_by_name": dict(self.punch_by_name),
                "last_backend": self.last_backend,
                "last_kernel": self.last_kernel,
                "last_dispatch_at": self.last_dispatch_at,
                "by_device": dict(self.dispatch_by_device),
                "last_device_name": self.last_device_name,
                "last_capability_used": self.last_capability_used,
                "last_lucas_rung": self.last_lucas_rung,
            },
            "work": {
                "work_items_total": self.work_items_total,
                "kernel_ms_total": self.kernel_ms_total,
                "kernel_ms_mean": self.mean_kernel_ms,
                "kernel_ms_max": self.kernel_ms_max,
                "busy_seconds": self.busy_seconds,
                "measured_throughput_per_s": self.measured_throughput_per_s,
                "peak_throughput_per_s": self.peak_throughput_per_s,
            },
            "manifold_11d": {
                "fold_total": self.fold_total,
                "unfold_total": self.unfold_total,
                "roundtrip_ok_total": self.roundtrip_ok_total,
                "roundtrip_fail_total": self.roundtrip_fail_total,
                "norm_sq_samples": self.norm_sq_samples,
                "norm_sq_mean": self.norm_sq_mean,
                "norm_sq_min": self.norm_sq_min,
                "norm_sq_max": self.norm_sq_max,
                "ball_violations": self.ball_violations,
                "anchor_histogram": list(self.anchor_histogram),
            },
            "storage": {
                "bytes_in_total": self.bytes_in_total,
                "bytes_stored_total": self.bytes_stored_total,
                "fold_ratio_measured": self.fold_ratio_measured,
            },
            "frame_32_face_overlay": self.frame.snapshot(),
            "frame_projection_496": self.frame_projection(),
            "theorem_proven": False,
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.snapshot(), indent=indent, sort_keys=True)

    def reset(self) -> None:
        """Clear all counters (test and scenario isolation)."""
        self.__init__(enabled=self.enabled)  # type: ignore[misc]


class FrameTelemetry:
    """The 32-face dodecahedral/icosahedral overlay — measured per shell.

    The trajectory engine does not run one solver over the 11D manifold. It
    fires 32 face normals every step and sums their votes into a resultant.
    Twelve of those normals are icosahedral (carrying PHI); twenty are
    dodecahedral (carrying PHI_INV). This collector reports the two shells
    separately so the overlay's real behaviour is visible:

        shell energy share   E_ico / (E_ico + E_dodeca)
        frame coherence      ||gradient|| / sum(|h_i|)      in [0, 1]
        cancellation         1 - coherence
        redundancy           32 faces resolving into 11 dimensions

    Coherence is the honest measure of constructive overlap: 1.0 means all
    thirty-two faces pulled the same way, 0.0 means complete cancellation.
    Both are observations of a real step, never projections.
    """

    def __init__(self) -> None:
        self.enabled: bool = True
        self.steps: int = 0
        self.faces_fired: int = 0
        self.faces_per_step_min: Optional[int] = None
        self.faces_per_step_max: int = 0

        # shell vote mass: sum(|h_i|) within each shell
        self.ico_vote_total: float = 0.0
        self.dodeca_vote_total: float = 0.0

        # shell energy: sum(h_i^2) within each shell
        self.ico_energy_total: float = 0.0
        self.dodeca_energy_total: float = 0.0

        # frame resultant
        self.resultant_norm_total: float = 0.0
        self.coherence_min: Optional[float] = None
        self.coherence_max: Optional[float] = None
        self.coherence_sum: float = 0.0

        self.zero_vote_steps: int = 0
        self.lucas_bias_sum: float = 0.0
        self.lucas_bias_samples: int = 0
        self.step_size_sum: float = 0.0
        self.step_size_samples: int = 0
        self.precision_best: Optional[float] = None

        # -- face-pair channels (the 496) ------------------------------------
        # Bitmap over the C(32,2) pairs. Bit k set means pair k was exercised.
        self.channel_bitmap: int = 0
        self.channel_uses_total: int = 0
        self.channels_per_step_max: int = 0
        self.full_frame_steps: int = 0

    def record_step(
        self,
        *,
        votes: Any,
        resultant_norm: float,
        lucas_bias: Optional[float] = None,
        step_size: Optional[float] = None,
        precision: Optional[float] = None,
        n_icosahedral: int = ICOSAHEDRAL_FACES,
    ) -> None:
        """Record one full frame firing.

        ``votes`` is the per-face array ``h`` (any indexable of numbers). The
        shell split is positional: the first ``n_icosahedral`` entries are the
        icosahedral shell, the remainder the dodecahedral shell — exactly the
        ordering produced by ``Pathfinder._build_faces``.
        """
        try:
            values = [float(v) for v in votes]
        except (TypeError, ValueError):  # pragma: no cover - malformed event
            return

        n_ico = max(0, min(int(n_icosahedral), len(values)))
        ico = values[:n_ico]
        dodeca = values[n_ico:]

        self.steps += 1
        self.faces_fired += len(values)
        if self.faces_per_step_min is None or len(values) < self.faces_per_step_min:
            self.faces_per_step_min = len(values)
        self.faces_per_step_max = max(self.faces_per_step_max, len(values))

        self.ico_vote_total += sum(abs(v) for v in ico)
        self.dodeca_vote_total += sum(abs(v) for v in dodeca)
        self.ico_energy_total += sum(v * v for v in ico)
        self.dodeca_energy_total += sum(v * v for v in dodeca)

        norm = max(0.0, float(resultant_norm))
        self.resultant_norm_total += norm

        mass = sum(abs(v) for v in values)
        if mass <= 0.0:
            self.zero_vote_steps += 1
        else:
            coherence = min(1.0, norm / mass)
            self.coherence_sum += coherence
            self.coherence_min = (
                coherence if self.coherence_min is None else min(self.coherence_min, coherence)
            )
            self.coherence_max = (
                coherence if self.coherence_max is None else max(self.coherence_max, coherence)
            )

        if lucas_bias is not None:
            self.lucas_bias_sum += float(lucas_bias)
            self.lucas_bias_samples += 1
        if step_size is not None:
            self.step_size_sum += float(step_size)
            self.step_size_samples += 1
        if precision is not None:
            value = float(precision)
            self.precision_best = (
                value if self.precision_best is None else min(self.precision_best, value)
            )

    @property
    def shell_energy_share_icosahedral(self) -> Optional[float]:
        """Icosahedral share of frame energy; None until a step is recorded."""
        total = self.ico_energy_total + self.dodeca_energy_total
        if total <= 0.0:
            return None
        return self.ico_energy_total / total

    @property
    def shell_vote_share_icosahedral(self) -> Optional[float]:
        total = self.ico_vote_total + self.dodeca_vote_total
        if total <= 0.0:
            return None
        return self.ico_vote_total / total

    @property
    def shell_anisotropy(self) -> Optional[float]:
        """Signed deviation of the icosahedral energy share from isotropy.

        Positive: the icosahedral shell (PHI) dominates. Negative: the
        dodecahedral shell (PHI_INV) dominates. Zero: balanced frame.
        """
        share = self.shell_energy_share_icosahedral
        if share is None:
            return None
        return share - ICOSAHEDRAL_ISOTROPIC_SHARE

    @property
    def coherence_mean(self) -> Optional[float]:
        resolved = self.steps - self.zero_vote_steps
        if resolved <= 0:
            return None
        return self.coherence_sum / resolved

    @property
    def cancellation_mean(self) -> Optional[float]:
        value = self.coherence_mean
        return None if value is None else 1.0 - value

    @property
    def mean_resultant_norm(self) -> Optional[float]:
        if self.steps == 0:
            return None
        return self.resultant_norm_total / self.steps

    @property
    def mean_lucas_bias(self) -> Optional[float]:
        if self.lucas_bias_samples == 0:
            return None
        return self.lucas_bias_sum / self.lucas_bias_samples

    @property
    def mean_step_size(self) -> Optional[float]:
        if self.step_size_samples == 0:
            return None
        return self.step_size_sum / self.step_size_samples

    @property
    def redundancy_ratio(self) -> float:
        """Faces per resolved dimension — the frame's overcompleteness."""
        return FRAME_FACES / float(_DIM_11D)

    def record_channels(
        self,
        pair_indices: Any,
        *,
        pair_count: Optional[int] = None,
    ) -> None:
        """Record which of the 496 face-pair channels a step exercised.

        ``pair_indices`` is any iterable of integers in ``[0, FACE_PAIRS)``.
        Out-of-range values are clamped into the bitmap rather than crashing
        a mining run: telemetry must never break the pipeline.
        """
        if not self.enabled:
            return
        seen_this_step = 0
        try:
            iterator = iter(pair_indices)
        except TypeError:
            return
        for raw in iterator:
            try:
                pair = int(raw) % FACE_PAIRS
            except (TypeError, ValueError):
                continue
            if pair < 0:
                pair += FACE_PAIRS
            bit = 1 << pair
            if not (self.channel_bitmap & bit):
                self.channel_bitmap |= bit
            seen_this_step += 1
        self.channel_uses_total += seen_this_step
        if seen_this_step > self.channels_per_step_max:
            self.channels_per_step_max = seen_this_step
        if pair_count is None:
            pair_count = seen_this_step
        if pair_count >= FACE_PAIRS:
            self.full_frame_steps += 1

    @staticmethod
    def face_pair_index(face_a: int, face_b: int) -> int:
        """Map an unordered face pair to its index in ``[0, 496)``.

        Lexicographic enumeration of ``{i, j}`` with ``i < j``. Both faces
        are taken modulo ``FRAME_FACES`` so an out-of-range face still maps
        somewhere valid instead of raising inside a hot loop.
        """
        i = int(face_a) % FRAME_FACES
        j = int(face_b) % FRAME_FACES
        if i == j:
            i = (i + 1) % FRAME_FACES
        if i > j:
            i, j = j, i
        return i * (2 * FRAME_FACES - i - 1) // 2 + (j - i - 1)

    @property
    def channels_occupied(self) -> int:
        """How many of the 496 face-pair channels this run actually touched."""
        return bin(self.channel_bitmap).count("1")

    @property
    def channel_occupancy_ratio(self) -> float:
        """Occupied channels / 496 — the MEASURED share of the overlay in use."""
        return self.channels_occupied / float(FACE_PAIRS)

    @property
    def is_full_frame_observed(self) -> bool:
        """True only when every one of the 496 channels has been exercised."""
        return self.channels_occupied >= FACE_PAIRS

    def snapshot(self) -> Dict[str, Any]:
        """Full JSON-serialisable view of the 32-face overlay."""
        return {
            "geometry": {
                "faces_total": FRAME_FACES,
                "icosahedral_faces": ICOSAHEDRAL_FACES,
                "dodecahedral_faces": DODECAHEDRAL_FACES,
                "ambient_dimensions": _DIM_11D,
                "redundancy_ratio": self.redundancy_ratio,
                "icosahedral_isotropic_share": ICOSAHEDRAL_ISOTROPIC_SHARE,
            },
            "firing": {
                "steps": self.steps,
                "faces_fired": self.faces_fired,
                "faces_per_step_min": self.faces_per_step_min,
                "faces_per_step_max": self.faces_per_step_max,
                "zero_vote_steps": self.zero_vote_steps,
            },
            "shells": {
                "ico_vote_total": self.ico_vote_total,
                "dodeca_vote_total": self.dodeca_vote_total,
                "ico_energy_total": self.ico_energy_total,
                "dodeca_energy_total": self.dodeca_energy_total,
                "shell_vote_share_icosahedral": self.shell_vote_share_icosahedral,
                "shell_energy_share_icosahedral": self.shell_energy_share_icosahedral,
                "shell_anisotropy": self.shell_anisotropy,
            },
            "resultant": {
                "mean_resultant_norm": self.mean_resultant_norm,
                "coherence_mean": self.coherence_mean,
                "coherence_min": self.coherence_min,
                "coherence_max": self.coherence_max,
                "cancellation_mean": self.cancellation_mean,
            },
            "trajectory": {
                "mean_lucas_bias": self.mean_lucas_bias,
                "mean_step_size": self.mean_step_size,
                "precision_best": self.precision_best,
            },
            "channels": {
                "face_pairs_total": FACE_PAIRS,
                "channels_occupied": self.channels_occupied,
                "channel_occupancy_ratio": self.channel_occupancy_ratio,
                "channel_uses_total": self.channel_uses_total,
                "channels_per_step_max": self.channels_per_step_max,
                "full_frame_steps": self.full_frame_steps,
                "is_full_frame_observed": self.is_full_frame_observed,
                "heterotic_gauge_dimension": HETEROTIC_GAUGE_DIMENSION,
                "perfect_number_496": PERFECT_NUMBER_496,
            },
        }


# -- module-level singleton + purity-safe host injection --------------------

_TELEMETRY: Optional[IgpuTelemetry] = None


def get_telemetry() -> IgpuTelemetry:
    """Process-wide telemetry singleton."""
    global _TELEMETRY
    if _TELEMETRY is None:
        _TELEMETRY = IgpuTelemetry()
    return _TELEMETRY


def reset_telemetry(enabled: Optional[bool] = None) -> IgpuTelemetry:
    """Replace the singleton (tests, scenario boundaries)."""
    global _TELEMETRY
    _TELEMETRY = IgpuTelemetry(enabled=enabled)
    return _TELEMETRY


def attach_to_host(host: Any, telemetry: Optional[IgpuTelemetry] = None) -> IgpuTelemetry:
    """Inject a ``telemetry_hook`` into a punch host without importing it.

    ``Intelligence/unified_punch.py`` is a LUCAS WIRING algorithm module and
    must not import a sibling. So the *coordinator* (this module) reaches in
    and installs a plain callable on the host. The host calls it when present;
    if it is absent or disabled the host behaves exactly as before.

    The hook signature is ``hook(event: dict) -> None`` and it is safe to call
    from any backend, including the pure-numpy CPU fallback.
    """
    tel = telemetry if telemetry is not None else get_telemetry()

    def telemetry_hook(event: Dict[str, Any]) -> None:
        kind = event.get("kind")
        if kind == "dispatch":
            mix = event.get("punch_mix")
            has_mix = isinstance(mix, dict) and bool(mix)
            tel.record_dispatch(
                backend=str(event.get("backend", "unknown")),
                gpu=bool(event.get("gpu", False)),
                work_items=int(event.get("work_items", 0)),
                kernel_ms=event.get("kernel_ms"),
                punch_id=None if has_mix else event.get("punch_id"),
                punch_name=None if has_mix else event.get("punch_name"),
                device_name=event.get("device_name"),
                capability_used=event.get("capability_used"),
                lucas_rung=event.get("lucas_rung"),
            )
            if has_mix:
                tel.record_punch_mix(mix)
        elif kind == "manifold":
            tel.record_manifold(
                norm_sq=event.get("norm_sq"),
                anchor=event.get("anchor"),
                fold=bool(event.get("fold", False)),
                unfold=bool(event.get("unfold", False)),
                roundtrip_ok=event.get("roundtrip_ok"),
            )
        elif kind == "storage":
            tel.record_storage(
                bytes_in=int(event.get("bytes_in", 0)),
                bytes_stored=int(event.get("bytes_stored", 0)),
            )
        elif kind == "frame":
            votes = event.get("votes")
            if votes is not None:
                tel.record_frame_step(
                    votes=votes,
                    resultant_norm=float(event.get("resultant_norm", 0.0)),
                    pair_indices=event.get("pair_indices"),
                    pair_count=event.get("pair_count"),
                    lucas_bias=event.get("lucas_bias"),
                    step_size=event.get("step_size"),
                    precision=event.get("precision"),
                    n_icosahedral=int(event.get("n_icosahedral", ICOSAHEDRAL_FACES)),
                )

    try:
        host.telemetry_hook = telemetry_hook
    except (AttributeError, TypeError):  # pragma: no cover - frozen host
        logger.debug("punch host does not accept a telemetry hook")
    return tel
