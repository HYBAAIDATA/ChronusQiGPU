"""Historical July-2026 GPU/HBM reference database for Chronus comparisons.

This module preserves the Geodesic Tensor Engine reference capability exactly
as a dated *reference snapshot*.  Values are not Chronus measurements and are
not automatically treated as current vendor specifications.  Measured device
facts belong to :mod:`chronus.telemetry` and the Tensor execution evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Tuple

REFERENCE_DATE = "2026-07-24"


@dataclass(frozen=True)
class GPUArchitectureSpec:
    name: str
    manufacturer: str
    process_nm: int
    transistors_b: int
    memory_type: str
    memory_capacity_gb: int
    memory_bandwidth_tbs: float
    fp4_pflops: float
    fp8_tflops: float
    fp16_tflops: float
    fp32_tflops: float
    tensor_core_gen: str
    transformer_engine_gen: str
    nvlink_bandwidth_tbs: float
    tdp_watts: int
    release_period: str
    source_refs: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["reference_date"] = REFERENCE_DATE
        result["truth_class"] = "historical_public_reference"
        result["measured_by_chronus"] = False
        return result


GPU_REFERENCE_2026: Dict[str, GPUArchitectureSpec] = {
    "rubin_r100": GPUArchitectureSpec(
        name="NVIDIA Rubin R100",
        manufacturer="NVIDIA",
        process_nm=3,
        transistors_b=336,
        memory_type="HBM4",
        memory_capacity_gb=288,
        memory_bandwidth_tbs=22.0,
        fp4_pflops=50.0,
        fp8_tflops=17500.0,
        fp16_tflops=8750.0,
        fp32_tflops=130.0,
        tensor_core_gen="6th Gen",
        transformer_engine_gen="3rd Gen",
        nvlink_bandwidth_tbs=3.6,
        tdp_watts=2700,
        release_period="H2 2026",
        source_refs=(
            "NVIDIA Newsroom: Rubin Platform AI Supercomputer",
            "NVIDIA Developer Blog: Inside NVIDIA Rubin GPU Architecture",
            "Wikipedia: Rubin (microarchitecture)",
            "Spheron: NVIDIA Rubin R100 GPU Chip Specs (2026)",
            "CNBC: First look at Vera Rubin (Feb 2026)",
        ),
    ),
    "blackwell_ultra_b300": GPUArchitectureSpec(
        name="NVIDIA Blackwell Ultra (HGX B300)",
        manufacturer="NVIDIA",
        process_nm=4,
        transistors_b=208,
        memory_type="HBM3e",
        memory_capacity_gb=288,
        memory_bandwidth_tbs=10.0,
        fp4_pflops=15.0,
        fp8_tflops=5000.0,
        fp16_tflops=2500.0,
        fp32_tflops=80.0,
        tensor_core_gen="5th Gen",
        transformer_engine_gen="2nd Gen",
        nvlink_bandwidth_tbs=1.8,
        tdp_watts=1800,
        release_period="H2 2025 / H1 2026",
        source_refs=(
            "NVIDIA Developer Blog: Inside Blackwell Ultra",
            "Tom's Hardware: Blackwell Ultra confirmations",
            "Tech-Insider: Blackwell Ultra specs",
        ),
    ),
    "amd_mi355x": GPUArchitectureSpec(
        name="AMD Instinct MI355X",
        manufacturer="AMD",
        process_nm=3,
        transistors_b=185,
        memory_type="HBM3e",
        memory_capacity_gb=288,
        memory_bandwidth_tbs=8.0,
        fp4_pflops=20.1,
        fp8_tflops=10066.0,
        fp16_tflops=5033.0,
        fp32_tflops=157.3,
        tensor_core_gen="CDNA 4 Matrix Core",
        transformer_engine_gen="CDNA 4 FP4/FP6/FP8 Engine",
        nvlink_bandwidth_tbs=1.008,
        tdp_watts=1400,
        release_period="H2 2025 / 2026",
        source_refs=(
            "AMD Instinct MI350 Series Product Brief (2025/2026)",
            "AMD CDNA 4 Architecture Whitepaper",
        ),
    ),
    "amd_mi325x": GPUArchitectureSpec(
        name="AMD Instinct MI325X",
        manufacturer="AMD",
        process_nm=5,
        transistors_b=153,
        memory_type="HBM3e",
        memory_capacity_gb=256,
        memory_bandwidth_tbs=6.0,
        fp4_pflops=0.0,
        fp8_tflops=2614.9,
        fp16_tflops=1307.4,
        fp32_tflops=163.4,
        tensor_core_gen="CDNA 3 Matrix Core",
        transformer_engine_gen="CDNA 3 FP8 Engine",
        nvlink_bandwidth_tbs=0.896,
        tdp_watts=1000,
        release_period="Q4 2024 / 2025",
        source_refs=(
            "AMD Instinct MI325X Datasheet",
            "AMD CDNA 3 Architecture Whitepaper",
        ),
    ),
    "hopper_h100": GPUArchitectureSpec(
        name="NVIDIA Hopper H100",
        manufacturer="NVIDIA",
        process_nm=4,
        transistors_b=80,
        memory_type="HBM3",
        memory_capacity_gb=80,
        memory_bandwidth_tbs=3.35,
        fp4_pflops=0.0,
        fp8_tflops=3958.0,
        fp16_tflops=1979.0,
        fp32_tflops=67.0,
        tensor_core_gen="4th Gen",
        transformer_engine_gen="1st Gen",
        nvlink_bandwidth_tbs=0.9,
        tdp_watts=700,
        release_period="2022-2023",
        source_refs=(
            "NVIDIA Developer Blog: Hopper Architecture In-Depth",
            "Spheron: NVIDIA Rubin vs Blackwell vs Hopper",
            "arXiv: How Much Progress in NVIDIA Datacenter GPUs?",
        ),
    ),
}

GPU_ALIASES = {
    "rubin": "rubin_r100",
    "r100": "rubin_r100",
    "b300": "blackwell_ultra_b300",
    "hgx_b300": "blackwell_ultra_b300",
    "blackwell_ultra": "blackwell_ultra_b300",
    "mi355x": "amd_mi355x",
    "mi325x": "amd_mi325x",
    "h100": "hopper_h100",
    "hopper": "hopper_h100",
}

HBM_GENERATIONS: Dict[str, Dict[str, Any]] = {
    "HBM3": {
        "bus_width_pins": 1024,
        "data_rate_gbps": 6.4,
        "bandwidth_per_stack_tbs": 1.6,
        "capacity_per_stack_gb": 24,
        "source": "JEDEC HBM3 standard (Jan 2022); SK Hynix",
    },
    "HBM3e": {
        "bus_width_pins": 1024,
        "data_rate_gbps": 9.6,
        "bandwidth_per_stack_tbs": 2.4,
        "capacity_per_stack_gb": 36,
        "source": "Samsung/SK Hynix HBM3e; NVIDIA Blackwell",
    },
    "HBM4": {
        "bus_width_pins": 2048,
        "data_rate_gbps": 11.0,
        "bandwidth_per_stack_tbs": 2.8,
        "capacity_per_stack_gb": 48,
        "source": "JEDEC HBM4 (Apr 2025); Micron; Samsung",
    },
}


def get_gpu_spec(name: str) -> GPUArchitectureSpec:
    key = str(name).strip().lower()
    key = GPU_ALIASES.get(key, key)
    try:
        return GPU_REFERENCE_2026[key]
    except KeyError as exc:
        raise KeyError(
            f"unknown July-2026 GPU reference {name!r}; available: {', '.join(GPU_REFERENCE_2026)}"
        ) from exc


def list_available_gpus() -> Tuple[str, ...]:
    return tuple(GPU_REFERENCE_2026)


def gpu_comparison() -> Tuple[Dict[str, Any], ...]:
    """Structured replacement for the July print helper."""
    return tuple(GPU_REFERENCE_2026[key].as_dict() for key in GPU_REFERENCE_2026)


def print_gpu_comparison() -> None:
    """Print the dated reference table for CLI/interactive parity."""
    for spec in gpu_comparison():
        print(
            f"{spec['name']}: {spec['memory_type']} {spec['memory_capacity_gb']}GB, "
            f"{spec['memory_bandwidth_tbs']} TB/s, FP32 {spec['fp32_tflops']} TFLOPS "
            f"[reference {REFERENCE_DATE}]"
        )


__all__ = [
    "GPUArchitectureSpec",
    "GPU_ALIASES",
    "GPU_REFERENCE_2026",
    "HBM_GENERATIONS",
    "REFERENCE_DATE",
    "get_gpu_spec",
    "gpu_comparison",
    "list_available_gpus",
    "print_gpu_comparison",
]
