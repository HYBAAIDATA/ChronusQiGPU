"""Platform-aware hardware configuration for PYTHIA.

Detects the deployment environment and configures the hardware profile:

- **M3 Studio/Ultra** (80-core GPU = 80 SMs × 128 ALU lanes = 10,240 shader
  lanes, 96GB unified): the original target — Apple Metal detected on macOS.
  This is the integrated iGPU (`EUCLID_VGPU`) and the default mining
  substrate under ``EUCLID_CHRONUS_SCHED`` (default on).
- **Docker + NVIDIA GPU**: CUDA-capable GPU detected via nvidia-smi or
  Docker GPU passthrough.
- **Docker + AMD GPU**: AMD ROCm or OpenCL backend.
- **Docker + CPU** (100GB): CPU/Turing exact-math fallback. The Q[√5]
  rational core still mines — the Lucas scaling amplifies the effective
  hashrate. This is the universal substrate.

The hashrate cap is configurable via environment variable
``EUCLID_MINING_CAP_EHS`` (default 1.0 EH/s for Docker, 10.0 for M3 Studio).
The cap can be raised up to 20.0 EH/s from the frontend, but never beyond,
and only incrementally (one ladder rung per request).

The hardware profile is selected via ``EUCLID_HARDWARE_PROFILE``:
- ``auto`` (default): detect at runtime
- ``m3_studio``: force M3 Studio profile
- ``docker``: force Docker CPU profile
- ``docker_gpu``: force Docker + GPU profile
- ``hybrid``: local GPU + Docker CPU + scalable cloud GPU

The **hybrid** profile is for deployments that combine:
1. A local iGPU (e.g. AMD Radeon) for lightweight hashing
2. Docker CPU (100GB) for the Turing exact-math core + PYTHIA memory
3. Scalable cloud GPU (added on demand) for hashrate scaling

The Lucas scaling ladder projects an EFFECTIVE-RATE accounting figure —
it is not a physical hashrate and no share is ever produced at these rates
(projection_is_measured: False, same truth label as
``Intelligence/chronus_telemetry.py``):
- L_10 = 123x  → 8 MH/s × 123 = 984 MH/s effective-equivalent (projected)
- L_15 = 1364x → 8 MH/s × 1364 = 10.9 GH/s effective-equivalent (projected)
- L_20 = 15127x → 8 MH/s × 15127 = 121 GH/s effective-equivalent (projected)
- L_41 = 5.4 billion x → 8 MH/s × 5.4B = 43 EH/s effective-equivalent,
  but the configured safety ceiling clamps the reported effective rate at
  20 EH/s; physical hashing remains 8 MH/s regardless.

The ceiling is a safety/effective-rate bound only. Pool acceptance is
governed solely by real shares meeting the real target. Scaling is always
incremental: the cap advances one rung of ``INCREMENTAL_SCALE_STEPS_EHS``
per request and never jumps.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: step

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("Intelligence.hardware_config")

# Hard ceiling — no deployment can exceed this, regardless of hardware.
# MUST stay equal to Intelligence.safety_constraints.ABSOLUTE_HARD_CAP_EHS;
# tests/test_chronus_telemetry.py asserts the two agree so they cannot diverge.
ABSOLUTE_HARD_CAP_EHS: float = 20.0
ABSOLUTE_HARD_CAP_HPS: int = int(ABSOLUTE_HARD_CAP_EHS * 1e18)


@dataclass
class HardwareProfile:
    """The detected hardware profile for PYTHIA's deployment."""

    profile_name: str  # "m3_studio", "docker_gpu", "docker_cpu", "hybrid"
    platform: str
    gpu_count: int
    gpu_type: str  # "apple_metal", "nvidia_cuda", "amd_rocm", "none"
    gpu_cores: int
    memory_gb: int
    power_watts: int
    # Estimated physical hashrate (H/s) before Lucas scaling — a
    # detector/lookup-table figure, never a measurement.
    estimated_physical_hps: int
    # Hashrate cap (H/s) — adjustable from frontend up to ABSOLUTE_HARD_CAP.
    hashrate_cap_hps: int
    # Backend: "metal", "cuda", "rocm", "cpu" (Turing exact-math)
    backend: str
    # Whether a GPU is genuinely available.
    gpu_available: bool
    # Lucas scale index for effective hashrate amplification.
    default_lucas_scale: int = 10  # L_10 = 123x amplification
    # Whether this is a hybrid deployment (local + Docker + cloud).
    is_hybrid: bool = False
    # Cloud GPU scaling target (0 = no cloud GPU, >0 = N cloud GPUs).
    cloud_gpu_count: int = 0
    # Measured physical hashrate (H/s). 0 until a real grind measures it;
    # reachability math may consume only this field, never the estimate.
    measured_hps: int = 0

    @property
    def physical_hashrate_hps(self) -> int:
        """Physical-rate basis for the effective-rate *projection*.

        The measured rate when one exists, else the estimate — the
        effective rate is a labeled projection either way, so a basis is
        always defined. Reachability gates use ``measured_hps`` directly
        and never see an estimate.
        """
        return self.measured_hps if self.measured_hps > 0 else self.estimated_physical_hps

    @property
    def physical_rate_source(self) -> str:
        """Provenance of the physical-rate basis: "measured" or "estimated"."""
        return "measured" if self.measured_hps > 0 else "estimated"

    def record_measured_hps(self, hps: int) -> None:
        """Record a measured physical hashrate (replaces the estimate as basis)."""
        if hps < 0:
            raise ValueError("measured hashrate cannot be negative")
        self.measured_hps = int(hps)

    def effective_hashrate_hps(self, lucas_scale_value: int = 123) -> int:
        """Effective hashrate = physical * L_n (a labeled projection)."""
        return self.physical_hashrate_hps * lucas_scale_value

    def effective_hashrate_ehs(self, lucas_scale_value: int = 123) -> float:
        """Effective hashrate in EH/s."""
        return self.effective_hashrate_hps(lucas_scale_value) / 1e18

    def can_reach_cap(self, lucas_scale_value: int = 123) -> bool:
        """True iff a *measured* rate × L_n reaches the cap.

        An estimate can never assert reachability — returns False until a
        real grind measures ``measured_hps``.
        """
        if self.measured_hps <= 0:
            return False
        return self.measured_hps * lucas_scale_value >= self.hashrate_cap_hps

    def projected_can_reach_cap(self, lucas_scale_value: int = 123) -> bool:
        """Same question answered on the estimate — projection, not a claim."""
        return self.estimated_physical_hps * lucas_scale_value >= self.hashrate_cap_hps

    def lucas_scale_needed_for_cap(self) -> Optional[int]:
        """Lucas value needed to reach the cap on the *measured* rate.

        Returns None until ``measured_hps`` exists — an estimate cannot
        certify a required scale.
        """
        if self.measured_hps <= 0:
            return None
        return self._lucas_scale_for(self.measured_hps)

    def projected_lucas_scale_needed_for_cap(self) -> Optional[int]:
        """Same answer computed on the estimate — projection, not a claim."""
        if self.estimated_physical_hps <= 0:
            return None
        return self._lucas_scale_for(self.estimated_physical_hps)

    def _lucas_scale_for(self, physical_hps: int) -> Optional[int]:
        """Return the smallest Lucas scale value reaching the cap, or None."""
        needed = self.hashrate_cap_hps / physical_hps
        from .lucas_scales import LUCAS_SCALE_LADDER

        for idx in sorted(LUCAS_SCALE_LADDER.keys()):
            lv_value = LUCAS_SCALE_LADDER[idx]
            if lv_value >= needed:
                return lv_value
        return None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile_name,
            "platform": self.platform,
            "gpu_count": self.gpu_count,
            "gpu_type": self.gpu_type,
            "gpu_cores": self.gpu_cores,
            "memory_gb": self.memory_gb,
            "power_watts": self.power_watts,
            "physical_hashrate_hps": self.physical_hashrate_hps,
            "physical_hashrate_mhs": self.physical_hashrate_hps / 1e6,
            "estimated_physical_hps": self.estimated_physical_hps,
            "measured_hps": self.measured_hps,
            # "measured" only when a real grind produced the basis figure.
            "physical_rate_source": self.physical_rate_source,
            "effective_hashrate_hps": self.effective_hashrate_hps(),
            "effective_hashrate_ehs": self.effective_hashrate_ehs(),
            "hashrate_cap_hps": self.hashrate_cap_hps,
            "hashrate_cap_ehs": self.hashrate_cap_hps / 1e18,
            "absolute_hard_cap_ehs": ABSOLUTE_HARD_CAP_EHS,
            "backend": self.backend,
            "gpu_available": self.gpu_available,
            "default_lucas_scale": self.default_lucas_scale,
            "is_hybrid": self.is_hybrid,
            "cloud_gpu_count": self.cloud_gpu_count,
            # Measured-only reachability; None/False while unmeasured.
            "can_reach_cap": self.can_reach_cap(),
            "lucas_scale_needed_for_cap": self.lucas_scale_needed_for_cap(),
            # Estimate-derived answers, labeled as projections.
            "projected_can_reach_cap": self.projected_can_reach_cap(),
            "projected_lucas_scale_needed_for_cap": (
                self.projected_lucas_scale_needed_for_cap()
            ),
        }


def _detect_nvidia_gpu() -> tuple[int, str]:
    """Detect NVIDIA GPU count and type via nvidia-smi."""
    if not shutil.which("nvidia-smi"):
        return 0, "none"
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=count,name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            count = len(lines)
            gpu_name = lines[0].split(", ")[-1].strip() if lines else "unknown"
            return count, gpu_name
    except Exception:
        pass
    return 0, "none"


def _detect_amd_gpu() -> tuple[bool, str]:
    """Detect AMD GPU via rocm-smi (Linux) or PowerShell WMI (Windows).

    Returns (has_amd, gpu_name).
    """
    # Linux: check for rocm-smi
    if shutil.which("rocm-smi"):
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True, "AMD ROCm GPU"
        except Exception:
            pass
    # Windows: check via PowerShell WMI
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_VideoController | "
                    "Where-Object {$_.Name -match 'AMD|Radeon'} | "
                    "Select-Object -ExpandProperty Name",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_name = result.stdout.strip().split("\n")[0].strip()
                if gpu_name:
                    return True, gpu_name
        except Exception:
            pass
    return False, "none"


def _get_cpu_cores() -> int:
    """Get CPU core count."""
    return os.cpu_count() or 4


def _clamp_cap(requested_ehs: float) -> int:
    """Clamp the requested hashrate cap to the absolute hard cap."""
    capped = min(requested_ehs, ABSOLUTE_HARD_CAP_EHS)
    return int(capped * 1e18)


def detect_hardware_profile() -> HardwareProfile:
    """Detect the hardware profile from the environment.

    Detection order:
    1. If ``EUCLID_HARDWARE_PROFILE`` is set, use it (forced).
    2. If macOS and Metal is available → M3 Studio profile.
    3. If nvidia-smi detects GPUs → Docker + NVIDIA GPU profile.
    4. If AMD GPU detected → Docker + AMD GPU profile.
    5. If EUCLID_CLOUD_GPU_COUNT > 0 → hybrid profile.
    6. Otherwise → Docker + CPU (Turing exact-math) profile.
    """
    forced = os.environ.get("EUCLID_HARDWARE_PROFILE", "auto")
    cap_ehs = float(os.environ.get("EUCLID_MINING_CAP_EHS", "1.0"))
    cap_hps = _clamp_cap(cap_ehs)
    max_mem_gb = int(os.environ.get("EUCLID_MAX_MEMORY_GB", "100"))
    cloud_gpus = int(os.environ.get("EUCLID_CLOUD_GPU_COUNT", "0"))
    sys_platform = platform.system()

    # -- M3 Studio (Apple Metal on macOS) --
    if forced in ("m3_studio", "auto") and sys_platform == "Darwin":
        try:
            import subprocess as sp

            r = sp.run(
                ["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True, timeout=5
            )
            if "Metal" in r.stdout or "Apple" in r.stdout:
                logger.info("Hardware profile: M3 Studio (Apple Metal)")
                return HardwareProfile(
                    profile_name="m3_studio",
                    platform="Darwin",
                    gpu_count=1,
                    gpu_type="apple_metal",
                    gpu_cores=80,
                    memory_gb=96,
                    power_watts=100,
                    # Topology-derived estimate: EUCLID vGPU = 10,240 ALU lanes ×
                    # 1.7 GHz boost / 4,096 cycles per SHA-256d ≈ 4.25 GH/s
                    estimated_physical_hps=4_250_000_000,  # ~4.25 GH/s
                    hashrate_cap_hps=_clamp_cap(min(cap_ehs, 10.0)),
                    backend="metal",
                    gpu_available=True,
                    default_lucas_scale=10,
                )
        except Exception:
            pass

    # -- Docker + NVIDIA GPU --
    gpu_count, gpu_name = _detect_nvidia_gpu()
    if forced in ("docker_gpu", "auto") and gpu_count > 0:
        logger.info("Hardware profile: Docker + GPU (%dx %s)", gpu_count, gpu_name)
        estimated_cores = gpu_count * 80
        estimated_hps = estimated_cores * 100_000_000  # 100 MH/s per core — estimate
        return HardwareProfile(
            profile_name="docker_gpu",
            platform=sys_platform,
            gpu_count=gpu_count,
            gpu_type=f"nvidia_cuda ({gpu_name})",
            gpu_cores=estimated_cores,
            memory_gb=max_mem_gb,
            power_watts=gpu_count * 250,
            estimated_physical_hps=estimated_hps,
            hashrate_cap_hps=cap_hps,
            backend="cuda",
            gpu_available=True,
            default_lucas_scale=10,
            cloud_gpu_count=cloud_gpus,
        )

    # -- Hybrid (local AMD iGPU + Docker CPU + cloud GPU) --
    has_amd, amd_name = _detect_amd_gpu()
    if forced in ("hybrid", "auto") and (has_amd or cloud_gpus > 0):
        cpu_cores = _get_cpu_cores()
        # Local AMD iGPU/dGPU: ~500 MH/s (integrated) to ~5 GH/s (discrete)
        amd_hps = 500_000_000 if has_amd else 0
        # Docker CPU: ~1 MH/s per core
        cpu_hps = cpu_cores * 1_000_000
        # Cloud GPU: ~10.3 GH/s per datacenter-class GPU (RTX 4090-class model)
        cloud_hps = cloud_gpus * 10_300_000_000
        total_estimated = amd_hps + cpu_hps + cloud_hps
        gpu_type = f"amd_rocm ({amd_name})" if has_amd else "none"
        if cloud_gpus > 0:
            gpu_type += f" + {cloud_gpus}x cloud_cuda"
        logger.info(
            "Hardware profile: Hybrid (AMD=%s [%s], CPU=%d cores, Cloud=%d GPUs, "
            "total=%.1f MH/s)",
            has_amd,
            amd_name,
            cpu_cores,
            cloud_gpus,
            total_estimated / 1e6,
        )
        return HardwareProfile(
            profile_name="hybrid",
            platform=sys_platform,
            gpu_count=cloud_gpus,
            gpu_type=gpu_type,
            gpu_cores=cloud_gpus * 80 if cloud_gpus > 0 else cpu_cores,
            memory_gb=max_mem_gb,
            power_watts=100 + cloud_gpus * 250,
            estimated_physical_hps=total_estimated,
            hashrate_cap_hps=cap_hps,
            backend="rocm" if has_amd and cloud_gpus == 0 else "hybrid",
            gpu_available=has_amd or cloud_gpus > 0,
            default_lucas_scale=10,
            is_hybrid=True,
            cloud_gpu_count=cloud_gpus,
        )

    # -- Docker + CPU (Turing exact-math fallback) --
    logger.info("Hardware profile: Docker + CPU (Turing exact-math fallback)")
    cpu_cores = _get_cpu_cores()
    estimated_hps = cpu_cores * 1_000_000  # 1 MH/s per core — estimate
    return HardwareProfile(
        profile_name="docker_cpu",
        platform=sys_platform,
        gpu_count=0,
        gpu_type="none",
        gpu_cores=cpu_cores,
        memory_gb=max_mem_gb,
        power_watts=100,
        estimated_physical_hps=estimated_hps,
        hashrate_cap_hps=cap_hps,
        backend="cpu",
        gpu_available=False,
        default_lucas_scale=10,
        cloud_gpu_count=cloud_gpus,
    )


# Singleton
_PROFILE: Optional[HardwareProfile] = None


def get_hardware_profile() -> HardwareProfile:
    """Return the process-wide hardware profile (singleton)."""
    global _PROFILE
    if _PROFILE is None:
        _PROFILE = detect_hardware_profile()
    return _PROFILE


def reset_hardware_profile() -> None:
    """Reset the singleton (mainly for tests)."""
    global _PROFILE
    _PROFILE = None


__all__ = [
    "HardwareProfile",
    "ABSOLUTE_HARD_CAP_EHS",
    "ABSOLUTE_HARD_CAP_HPS",
    "detect_hardware_profile",
    "get_hardware_profile",
    "reset_hardware_profile",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (step_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("step_kernel")({"states": 8}, n)
    result["module"] = __name__
    return result
