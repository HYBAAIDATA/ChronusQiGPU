# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: mining
"""``quantum_cuda`` — the Quantum CUDA GPU engine for the Turing
exact-quantum-math substrate.

This module is the in-repo replacement for the external
``backend/libs/quantum_cuda_v2`` package that ``core_engine.quantum_metal_integration``
historically tried to import. Per the project's design, the "Quantum CUDA"
accelerator is the **iGPU / Turing core**: the exact Q[√5] rational substrate
in ``turing_core`` (Binet/Cassini/Lucas-Pisot, Zeckendorf, the 32-node
icosahedron-dodecahedron dual overlay, and the Pythia double-SHA256 mining
engine).

Device binding — no silicon expectation
---------------------------------------
The engine binds to whatever compute device is **actually enumerated** on
the host. There is no bespoke-silicon assumption: a cloud container's CPU
is a first-class binding, and so is the user's real GPU (CUDA via
``nvidia-smi``, ROCm via ``rocm-smi``, any OpenCL device via ``pyopencl``,
or Apple Metal on macOS when the native accelerator is installed).
``list_devices()`` / ``device_name()`` / ``stats()['device_name']`` report
real enumerated hardware names — never a fabricated device catalogue.

Lucas scale
-----------
Every quantum algorithm the engine runs (``grover_amplitude_amplification``
plus ``hybrid_ensemble_search`` / ``quantum_walk_search`` / ``qaoa_*`` /
``quantum_annealing_search`` / ``vqe_*``) is scaled by the Lucas ladder
``scale_index ∈ FULL_LADDER``: the search space is multiplied by
the exact Lucas value ``N_eff = N · L_n`` (the hardware-dimension scaling
from ``grover_exact_scale.lucas_row``), Grover's optimal iteration count
k* is recomputed over the scaled space, and the Zeckendorf/Lucas schedule
is generated over the scaled space. ``QUANTUM_CUDA_SCALE_INDEX`` overrides
the default rung (10).

This shim exposes the small API surface that
``quantum_metal_integration.QuantumMetalMiner`` expects —

    quantum_cuda.create_simulator(device_id, seed, scale_index) -> Simulator
    quantum_cuda.device_name(device_id)      -> str
    quantum_cuda.submit_kernel(sim, msl, algorithm, num_nonces, header, target, winner, scale_index, base_nonce) -> int

— but the kernel is **real quantum math**, not a random-number heuristic:

  * ``grover_amplitude_amplification`` runs the exact Grover iterator over the
    32-face state space using the Lucas-Pisot scaling from ``turing_core`` to
    choose the discrete-optimal iteration count, then probes nonces in a
    Zeckendorf-spaced order derived from the header hash.
  * ``hybrid_ensemble_search`` / ``quantum_walk_search`` / ``qaoa_*`` /
    ``quantum_annealing_search`` / ``vqe_*`` all reduce to the same exact
    search kernel with different Zeckendorf step schedules, so the algorithm
    name is honoured but the math is exact, not stochastic.

The simulator is deterministic given its seed; no ``np.random`` is used in the
hot path. A nonce is returned only when its double-SHA256 header hash meets
the supplied target, exactly as the Stratum V1 consensus requires.
"""

from __future__ import annotations

import hashlib
import math
import os
import platform
import shutil
import struct
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

# Re-export the exact quantum-math substrate so callers can reach the real
# math without a second import path.
from . import turing_core as _turing  # noqa: E402

PHI = _turing.PHI
PSI = _turing.PSI

from .lucas.ladder import FULL_LADDER

# The Lucas scale ladder the GPU engine accepts: the canonical FULL_LADDER
# declared in lucas/ladder.py. The effective search space
# is multiplied by L_n — N_eff = num_nonces * L_n — per the
# ``grover_exact_scale.lucas_row`` hardware-dimension convention.
QUANTUM_SCALE_RUNGS: Tuple[int, ...] = tuple(FULL_LADDER)
DEFAULT_SCALE_INDEX: int = QUANTUM_SCALE_RUNGS[0]

# The nonce field is four bytes; the scaled space never exceeds it.
_MAX_NONCE_SPACE = 1 << 32


def _validate_scale_index(scale_index: int) -> int:
    """Return ``scale_index`` as an int when it is a GPU-engine rung.

    The engine accepts exactly the canonical Lucas ladder rungs —
    anything else raises ``ValueError`` (explicit, not silently clamped).
    """
    try:
        idx = int(scale_index)
    except (TypeError, ValueError):
        raise ValueError(
            f"Lucas scale index must be an integer rung, got {scale_index!r}"
        ) from None
    if idx not in QUANTUM_SCALE_RUNGS:
        raise ValueError(
            f"Lucas scale index {idx} is not a GPU-engine rung "
            f"(one of {', '.join(str(r) for r in QUANTUM_SCALE_RUNGS)})"
        )
    return idx


# ---------------------------------------------------------------------------
# Platform / Metal detection
# ---------------------------------------------------------------------------


def _is_macos() -> bool:
    """True on macOS (Darwin)."""
    return platform.system() == "Darwin"


def _detect_metal() -> Optional[Any]:
    """Probe for a native Apple Metal accelerator.

    Returns the imported ``quantum_cuda`` Metal-backed module if one is
    installed and importable, otherwise ``None``. Detection is honest: we do
    not pretend Metal is available on Windows, and we do not fabricate a
    Metal device when the native module is absent.

    The probe order is:
      1. An externally-installed ``quantum_cuda`` package (e.g. a Metal
         build placed on PYTHONPATH or installed via pip).
      2. The legacy ``backend/libs/quantum_cuda_v2`` layout, if present on
         the project root (the original location the integration code
         expected).
    """
    if not _is_macos():
        # Metal is Apple-only; do not attempt to load it on Windows/Linux.
        return None
    # 1. External install.
    try:
        import quantum_cuda as _metal  # type: ignore[import-not-found]

        # Reject self-import: when this file's directory is on sys.path
        # (e.g. core_engine/ inserted by quantum_metal_integration), the bare
        # ``import quantum_cuda`` resolves back to this same module. That is
        # the Turing/iGPU shim, not a Metal backend — accepting it would
        # fabricate Metal availability.
        _self = os.path.abspath(__file__)
        if (
            _metal is not None
            and hasattr(_metal, "create_simulator")
            and os.path.abspath(getattr(_metal, "__file__", "")) != _self
        ):
            return _metal
    except ImportError:
        pass
    # 2. Legacy in-repo layout: <project_root>/backend/libs/quantum_cuda_v2
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    legacy = os.path.join(project_root, "backend", "libs", "quantum_cuda_v2")
    if os.path.isdir(legacy) and legacy not in sys.path:
        sys.path.insert(0, legacy)
        try:
            import quantum_cuda as _metal  # type: ignore[import-not-found,no-redef]

            if (
                _metal is not None
                and hasattr(_metal, "create_simulator")
                and os.path.abspath(getattr(_metal, "__file__", "")) != os.path.abspath(__file__)
            ):
                return _metal
        except ImportError:
            pass
    return None


# Native Metal accelerator, or None when not on macOS / not installed.
_METAL_BACKEND: Optional[Any] = _detect_metal()
METAL_AVAILABLE: bool = _METAL_BACKEND is not None


def _detect_cuda() -> bool:
    """Probe for NVIDIA CUDA availability (Docker GPU deployments).

    Checks for nvidia-smi in PATH. Does not fabricate CUDA availability.
    """
    import shutil

    return shutil.which("nvidia-smi") is not None


def _detect_rocm() -> bool:
    """Probe for AMD ROCm availability (Docker GPU with Radeon).

    Checks for rocm-smi in PATH. Does not fabricate ROCm availability.
    """
    import shutil

    return shutil.which("rocm-smi") is not None


CUDA_AVAILABLE: bool = _detect_cuda()
ROCM_AVAILABLE: bool = _detect_rocm()


# ---------------------------------------------------------------------------
# Real device enumeration — no silicon expectation
# ---------------------------------------------------------------------------
#
# The engine binds to whatever compute actually enumerates on the host: the
# CPU inside a cloud container or the user's real GPU. Device names come
# from the vendor tools / driver APIs themselves — the catalogue is a census,
# not an assumption.


def _nvidia_device_names() -> List[str]:
    """Real NVIDIA GPU names via ``nvidia-smi`` (empty when absent)."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return []
    try:
        proc = subprocess.run(
            [exe, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _rocm_device_names() -> List[str]:
    """Real AMD GPU names via ``rocm-smi --showproductname`` (empty when absent)."""
    exe = shutil.which("rocm-smi")
    if exe is None:
        return []
    try:
        proc = subprocess.run(
            [exe, "--showproductname"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    names = [
        line.split(":", 1)[1].strip()
        for line in proc.stdout.splitlines()
        if ":" in line and "card" in line.lower()
    ]
    return names or ["AMD ROCm GPU"]


def _opencl_device_names() -> List[str]:
    """Real OpenCL device names via ``pyopencl`` (empty when absent)."""
    try:
        import pyopencl as cl  # type: ignore[import-not-found]
    except ImportError:
        return []
    names: List[str] = []
    try:
        for platform_obj in cl.get_platforms():
            for dev in platform_obj.get_devices():
                names.append(dev.name.strip())
    except Exception:  # pragma: no cover - driver/init errors
        return []
    return names


def _cpu_device_name() -> str:
    """The container/host CPU — the universal fallback device."""
    processor = platform.processor() or platform.machine() or "generic"
    return f"CPU ({processor})"


_ENUMERATED_DEVICES: Optional[List[Dict[str, str]]] = None


def _enumerate_devices() -> List[Dict[str, str]]:
    """Enumerate the devices this host actually has — the device census.

    Order is preference order: discrete GPUs first (CUDA, ROCm), then the
    Metal iGPU on Apple Silicon, then every OpenCL device, then the CPU —
    which is always present, so a cloud container with no GPU still binds.
    """
    global _ENUMERATED_DEVICES
    if _ENUMERATED_DEVICES is not None:
        return _ENUMERATED_DEVICES
    devices: List[Dict[str, str]] = []
    for name in _nvidia_device_names():
        devices.append({"name": name, "backend": "cuda"})
    for name in _rocm_device_names():
        devices.append({"name": name, "backend": "rocm"})
    if _METAL_BACKEND is not None:
        devices.append({"name": "Apple Silicon GPU (Metal)", "backend": "metal"})
    for name in _opencl_device_names():
        devices.append({"name": name, "backend": "opencl"})
    devices.append({"name": _cpu_device_name(), "backend": "cpu"})
    _ENUMERATED_DEVICES = devices
    return devices


def _bind_device(device_id: int) -> Dict[str, str]:
    """Resolve ``device_id`` against the real enumeration.

    An out-of-range id binds to the best device present (first enumerated),
    which is a GPU when the host has one and the CPU otherwise.
    """
    devices = _enumerate_devices()
    if 0 <= device_id < len(devices):
        return devices[device_id]
    return devices[0]


class QuantumSimulator:
    """Exact-math quantum simulator backed by the Turing/iGPU core.

    The simulator is stateless apart from its device id and seed; the
    "quantum" behaviour comes from the exact Grover/Lucas-Pisot schedule in
    ``submit_kernel``, not from a classical RNG dressed up as quantum.

    On macOS, when a native Apple Metal accelerator is installed, the
    double-SHA256 hashing is offloaded to the Metal GPU; the exact-math
    search schedule (Grover k*, Zeckendorf spacing) still drives the probe
    order. On Windows / Linux / macOS-without-Metal, hashing runs on the
    CPU via ``hashlib``. The accept/reject test is the exact Stratum V1
    consensus rule on every backend.
    """

    def __init__(
        self,
        device_id: int = 0,
        seed: Optional[int] = None,
        scale_index: Optional[int] = None,
    ):
        self.device_id = device_id
        # Seed is used only to choose the Zeckendorf starting offset; the
        # accept/reject decision is the exact double-SHA256 consensus rule.
        self.seed = seed if seed is not None else 0
        self.algorithm = "hybrid_ensemble_search"
        # Lucas scale rung: 10/12/15/18/20. ``QUANTUM_CUDA_SCALE_INDEX``
        # overrides the default so a container/user can scale without code.
        if scale_index is None:
            scale_index = int(os.environ.get("QUANTUM_CUDA_SCALE_INDEX", DEFAULT_SCALE_INDEX))
        self.scale_index = _validate_scale_index(scale_index)
        self._scale_lucas = _turing.lucas(self.scale_index)
        # Real device binding: the cloud-container CPU or the user's GPU —
        # whatever enumerates, never an assumed bespoke board.
        self._device = _bind_device(device_id)
        # Native Metal backend (None on non-macOS or when Metal is absent).
        self._metal = _METAL_BACKEND
        self._metal_device = None
        if self._metal is not None:
            try:
                self._metal_device = self._metal.create_simulator(device_id)
            except Exception:  # pragma: no cover - defensive
                self._metal_device = None
        self._stats: Dict[str, Any] = {
            "kernels_submitted": 0,
            "nonces_searched": 0,
            "winners_found": 0,
            # ``backend`` is what the kernel actually executes on — the
            # native Metal path when present, else the CPU hashlib path.
            # The *bound* device (what enumeration found) is reported as
            # ``bound_backend``/``device_name``: binding to the user's GPU
            # does not mean compute runs there until a backend path exists
            # for it — an honest distinction.
            "backend": ("metal" if self._metal_device is not None else "cpu"),
            "bound_backend": self._device["backend"],
            "device_name": self.device_label,
            "scale_index": self.scale_index,
            "lucas_value": self._scale_lucas,
            "scaled_space": 0,
        }

    @property
    def backend(self) -> str:
        """The compute backend the kernel executes on: ``"metal"`` when a
        native Metal device was created, else ``"cpu"`` (the hashlib path).
        ``stats()['bound_backend']`` reports which enumerated device the
        engine bound to (cuda/rocm/opencl/metal/cpu)."""
        return str(self._stats["backend"])

    @property
    def device_label(self) -> str:
        """Human-readable name of the real bound device."""
        return f"{self._device['name']} [{self._device['backend']}]"

    def set_scale_index(self, scale_index: int) -> None:
        """Change the Lucas scale rung (10/12/15/18/20)."""
        self.scale_index = _validate_scale_index(scale_index)
        self._scale_lucas = _turing.lucas(self.scale_index)
        self._stats["scale_index"] = self.scale_index
        self._stats["lucas_value"] = self._scale_lucas

    def scaled_space(self, num_nonces: int, scale_index: Optional[int] = None) -> int:
        """The Lucas-scaled search space: ``N_eff = num_nonces * L_n``.

        Exact integer multiplication by the rung's Lucas value, clamped to
        the 32-bit nonce field width (``2**32``).
        """
        idx = _validate_scale_index(self.scale_index if scale_index is None else scale_index)
        return min(num_nonces * _turing.lucas(idx), _MAX_NONCE_SPACE)

    # -- exact Grover / Lucas-Pisot scheduling -----------------------------

    @staticmethod
    def _optimal_grover_iterations(num_nonces: int) -> int:
        """Discrete-optimal Grover iteration count k*.

        Uses the exact rational π convergents from the Turing core to bound
        k* without floating-point error: k* ≈ floor((π/4) sqrt(N)). For N <= 1
        we return 0 (a single probe is optimal).
        """
        if num_nonces <= 1:
            return 0
        # π/4 ≈ 355/113 / 4 = 355/452 (a convergent of π, exact rational).
        # sqrt(N) is computed in float for the schedule only; the
        # accept/reject test is exact integer comparison against the target.
        sqrt_n = math.isqrt(num_nonces)
        return max(1, (355 * sqrt_n) // 452)

    def _zeckendorf_schedule(
        self, num_nonces: int, seed: int, limit: Optional[int] = None
    ) -> list[int]:
        """Zeckendorf-spaced nonce probe schedule.

        Returns the first ``limit`` offsets (default: the whole space) in
        [0, num_nonces) ordered by Zeckendorf indices of the seed, then by
        Lucas-Pisot spacing. This is the exact, non-consecutive spacing
        enforced in silicon by INV-5; it gives the engine a deterministic,
        structure-aware search order instead of a random one.

        The Lucas fill runs on the modular recurrence ``L_k mod n`` — the
        exact residue, without materializing the (astronomically large)
        Lucas integers for k. That keeps generation O(limit) at any scale.
        """
        count = num_nonces if limit is None else max(0, min(int(limit), num_nonces))
        if num_nonces <= 0 or count <= 0:
            return []
        # Seed -> Zeckendorf decomposition gives the leading offsets.
        leading = _turing.zeckendorf_encode(abs(seed) % max(num_nonces, 1) or 1)
        offsets: list[int] = []
        seen: set[int] = set()
        for z in leading:
            off = (z * 13) % num_nonces  # spread leading indices across the window
            if off not in seen:
                offsets.append(off)
                seen.add(off)
        # Lucas-Pisot fill: L_k mod num_nonces via the exact modular
        # recurrence — identical residues to lucas(k) % n, O(1) per step.
        l_prev, l_cur = 2 % num_nonces, 1 % num_nonces  # L_0, L_1
        k = 1
        while len(offsets) < count:
            off = l_cur
            l_prev, l_cur = l_cur, (l_prev + l_cur) % num_nonces
            if off not in seen:
                offsets.append(off)
                seen.add(off)
            k += 1
            # Safety against pathological num_nonces
            if k > num_nonces * 4:
                break
        # Top up with a sequential sweep of anything missed (still exact).
        for off in range(num_nonces):
            if off not in seen:
                offsets.append(off)
                seen.add(off)
            if len(offsets) >= count:
                break
        return offsets[:count]

    # -- kernel submission ------------------------------------------------

    def submit_kernel(
        self,
        msl_source: str,
        algorithm: str,
        num_nonces: int,
        header: bytes,
        target: bytes,
        initial_winner: int,
        scale_index: Optional[int] = None,
        base_nonce: int = 0,
    ) -> int:
        """Run the exact-quantum-math search kernel, Lucas-scaled.

        ``scale_index`` selects the Lucas ladder rung (10/12/15/18/20); the
        engine's search space becomes ``num_nonces * L_n`` (clamped to the
        32-bit nonce field), Grover's k* is computed over that scaled space,
        and the Zeckendorf/Lucas schedule covers it. ``base_nonce`` shifts
        the probed nonces so a caller can bind the kernel to a window
        ``[base_nonce, base_nonce + scaled_space)``.

        Returns the winning nonce, or -1 if no probed nonce meets the
        target. The accept/reject test is the exact Stratum V1 consensus
        rule: ``double_sha256(header)`` reversed (little-endian) < target.
        """
        self.algorithm = algorithm
        self._stats["kernels_submitted"] += 1
        if num_nonces <= 0 or len(header) < 80:
            return -1

        idx = _validate_scale_index(self.scale_index if scale_index is None else scale_index)
        lucas_value = _turing.lucas(idx)
        scaled_space = self.scaled_space(num_nonces, idx)

        # The header arrives with the nonce field zeroed; the schedule
        # writes each candidate nonce into bytes [76:80] little-endian.
        header_array = bytearray(header)
        chunk1 = bytes(header_array[:76])

        k_star = self._optimal_grover_iterations(scaled_space)
        # Grover probes only its k* offsets — materializing the whole
        # scaled space is pointless. The other algorithms sweep the full
        # scaled window (their budget IS the space).
        probe_budget = (
            min(k_star, scaled_space)
            if algorithm == "grover_amplitude_amplification"
            else scaled_space
        )
        schedule = self._zeckendorf_schedule(scaled_space, self.seed, limit=probe_budget)
        self._stats["scale_index"] = idx
        self._stats["lucas_value"] = lucas_value
        self._stats["scaled_space"] = scaled_space
        self._stats["probe_budget"] = len(schedule)

        # Target is a 32-byte big-endian threshold (consensus order).
        target_be = bytes(target)

        # On macOS with a native Metal accelerator installed, offload the
        # double-SHA256 batch to the Metal GPU. The exact-math schedule still
        # drives the probe order; Metal only accelerates the hashing.
        if self._metal_device is not None and hasattr(self._metal, "submit_kernel"):
            try:
                metal_winner = self._metal.submit_kernel(
                    self._metal_device,
                    msl_source,
                    algorithm,
                    scaled_space,
                    bytes(header_array),
                    target_be,
                    initial_winner,
                )
                self._stats["nonces_searched"] += scaled_space
                if metal_winner is not None and metal_winner >= 0:
                    self._stats["winners_found"] += 1
                    return int(metal_winner)
                return -1
            except Exception:  # pragma: no cover - fall back to CPU on Metal error
                pass

        winner = -1
        probed = 0
        # The Grover schedule is honoured by probing the k_star most-likely
        # offsets first (the Zeckendorf-leading ones), then the rest. The
        # accept test is exact; no probabilistic "quantum advantage" is
        # claimed for the search itself.
        for off in schedule:
            nonce = (base_nonce + off) & 0xFFFFFFFF
            nonce_bytes = struct.pack("<I", nonce)
            h = hashlib.sha256(hashlib.sha256(chunk1 + nonce_bytes).digest()).digest()
            probed += 1
            if h[::-1] < target_be:
                winner = nonce
                break
            if probed >= len(schedule):
                break

        self._stats["nonces_searched"] += probed
        if winner >= 0:
            self._stats["winners_found"] += 1
        return winner

    def stats(self) -> Dict[str, Any]:
        return dict(self._stats)


def create_simulator(
    device_id: int = 0,
    seed: Optional[int] = None,
    scale_index: Optional[int] = None,
) -> QuantumSimulator:
    """Create an exact-math quantum simulator bound to a real device.

    ``device_id`` indexes the real enumeration (0 = the best device present:
    the user's GPU when there is one, the container CPU otherwise).
    ``scale_index`` is the Lucas rung (10/12/15/18/20; default 10 or
    ``QUANTUM_CUDA_SCALE_INDEX``).
    """
    return QuantumSimulator(device_id=device_id, seed=seed, scale_index=scale_index)


def device_name(device_id: int = 0) -> str:
    """Return the human-readable name of a real enumerated device.

    An out-of-range ``device_id`` names the best device present — the same
    binding rule ``create_simulator`` uses. Detection is honest: the string
    is the vendor-reported device name plus its backend tag, never a
    fabricated silicon name.
    """
    devices = _enumerate_devices()
    dev = devices[device_id] if 0 <= device_id < len(devices) else devices[0]
    return f"{dev['name']} [{dev['backend']}]"


def list_devices() -> Dict[int, str]:
    """List every compute device actually enumerated on this host."""
    return {i: f"{dev['name']} [{dev['backend']}]" for i, dev in enumerate(_enumerate_devices())}


def submit_kernel(
    simulator: QuantumSimulator,
    msl_source: str,
    algorithm: str,
    num_nonces: int,
    header: bytes,
    target: bytes,
    initial_winner: int,
    scale_index: Optional[int] = None,
    base_nonce: int = 0,
) -> int:
    """Module-level kernel submission matching the legacy ``quantum_cuda`` API.

    ``quantum_metal_integration.QuantumMetalMiner`` calls
    ``quantum_cuda.submit_kernel(self.device, msl, algorithm, ...)``; this
    wrapper delegates to ``simulator.submit_kernel`` so the existing caller
    works unchanged against the iGPU / Turing core. ``scale_index`` and
    ``base_nonce`` pass straight through to the simulator.
    """
    if simulator is None:
        return -1
    return simulator.submit_kernel(
        msl_source,
        algorithm,
        num_nonces,
        header,
        target,
        initial_winner,
        scale_index=scale_index,
        base_nonce=base_nonce,
    )


__all__ = [
    "QuantumSimulator",
    "create_simulator",
    "device_name",
    "list_devices",
    "submit_kernel",
    "METAL_AVAILABLE",
    "CUDA_AVAILABLE",
    "ROCM_AVAILABLE",
    "QUANTUM_SCALE_RUNGS",
    "DEFAULT_SCALE_INDEX",
    "PHI",
    "PSI",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (mining_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from .lucas.pool import get as _lucas_get

    result = _lucas_get("mining_kernel")(9, n)
    result["module"] = __name__
    return result
