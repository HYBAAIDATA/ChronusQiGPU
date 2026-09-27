"""Vendor/device catalog — exact identity tuples for supported silicon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class DeviceSpec:
    """One supported device family: identity + dispatch contract."""

    family: str
    vendor: str
    aliases: Tuple[str, ...]
    pci_ids: Tuple[str, ...]
    backends: Tuple[str, ...]
    dispatch: str
    notes: str = ""


APPLE_SILICON = (
    DeviceSpec(
        "apple-m1",
        "Apple",
        ("apple-m1", "apple m1", "m1"),
        (),
        ("metal", "mlx", "opencl", "cpu"),
        "metal",
        "M1 GPU",
    ),
    DeviceSpec(
        "apple-m2",
        "Apple",
        ("apple-m2", "apple m2", "m2"),
        (),
        ("metal", "mlx", "opencl", "cpu"),
        "metal",
        "M2 GPU",
    ),
    DeviceSpec(
        "apple-m3",
        "Apple",
        ("apple-m3", "apple m3", "m3"),
        (),
        ("metal", "mlx", "opencl", "cpu"),
        "metal",
        "M3 target",
    ),
    DeviceSpec(
        "apple-m4",
        "Apple",
        ("apple-m4", "apple m4", "m4"),
        (),
        ("metal", "mlx", "opencl", "cpu"),
        "metal",
        "M4 GPU",
    ),
)

INTEL_IGPU = (
    DeviceSpec(
        "intel-uhd-620",
        "Intel",
        ("intel-uhd-620", "uhd 620", "uhd620", "0x5917", "5917"),
        ("0x5917", "5917"),
        ("opencl", "cpu"),
        "opencl",
        "Kaby Lake-R GT2 24EU dev reference",
    ),
    DeviceSpec(
        "intel-iris-xe",
        "Intel",
        ("intel-iris-xe", "iris xe", "iris-xe", "0x9a49", "9a49"),
        ("0x9a49", "9a49"),
        ("opencl", "cpu"),
        "opencl",
        "Tiger Lake GT2 96EU",
    ),
    DeviceSpec(
        "intel-arc",
        "Intel",
        ("intel-arc", "arc", "0x56a0", "56a0"),
        ("0x56a0", "56a0"),
        ("opencl", "cpu"),
        "opencl",
        "Arc Alchemist",
    ),
)
NVIDIA_GPU = (
    DeviceSpec(
        "nvidia-t4",
        "NVIDIA",
        ("nvidia-t4", "tesla t4", "t4"),
        ("0x1eb8", "1eb8"),
        ("cuda", "opencl", "cpu"),
        "cuda",
        "Turing 75W; HPE DL380 Gen10 option",
    ),
    DeviceSpec(
        "nvidia-l4",
        "NVIDIA",
        ("nvidia-l4", "l4"),
        ("0x27b8", "27b8"),
        ("cuda", "opencl", "cpu"),
        "cuda",
        "Ada 72W; HPE ProLiant Gen11 option",
    ),
    DeviceSpec(
        "nvidia-a10",
        "NVIDIA",
        ("nvidia-a10", "a10"),
        ("0x2236", "2236"),
        ("cuda", "opencl", "cpu"),
        "cuda",
        "Ampere 150W; HPE Apollo/ProLiant option",
    ),
    DeviceSpec(
        "nvidia-l40s",
        "NVIDIA",
        ("nvidia-l40s", "l40s"),
        ("0x26b5", "26b5"),
        ("cuda", "opencl", "cpu"),
        "cuda",
        "Ada 350W; HPE Cray XD/DL option",
    ),
    DeviceSpec(
        "nvidia-h100",
        "NVIDIA",
        ("nvidia-h100", "h100", "h200"),
        ("0x233a", "233a"),
        ("cuda", "opencl", "cpu"),
        "cuda",
        "Hopper 700W; HPE Cray XD670/GreenLake target",
    ),
    DeviceSpec(
        "nvidia-rtx4090",
        "NVIDIA",
        ("nvidia-rtx4090", "rtx 4090", "rtx4090"),
        ("0x2684", "2684"),
        ("cuda", "opencl", "cpu"),
        "cuda",
        "Ada workstation; Docker CUDA dev target",
    ),
)

AMD_GPU = (
    DeviceSpec(
        "amd-mi210",
        "AMD",
        ("amd-mi210", "mi210"),
        ("0x740f", "740f"),
        ("rocm", "opencl", "cpu"),
        "rocm",
        "CDNA2 300W; HPE Cray EX235a lineage",
    ),
    DeviceSpec(
        "amd-mi300x",
        "AMD",
        ("amd-mi300x", "mi300x", "mi300"),
        ("0x74a1", "74a1"),
        ("rocm", "opencl", "cpu"),
        "rocm",
        "CDNA3 750W 192GB; HPE Cray XD675 lineage",
    ),
    DeviceSpec(
        "amd-radeon-780m",
        "AMD",
        ("amd-radeon-780m", "radeon 780m", "780m"),
        ("0x15bf", "15bf"),
        ("rocm", "opencl", "cpu"),
        "opencl",
        "Phoenix APU iGPU reference",
    ),
)

HYBA_FABRIC = (
    DeviceSpec(
        "hyba-mla1517",
        "HYBA",
        ("hyba-mla1517", "hyba_mla1517", "mla1517", "hyba"),
        (),
        ("opencl", "cpu"),
        "opencl",
        "MLA1517 fabric; name-alias match",
    ),
)

CATALOG: Tuple[DeviceSpec, ...] = (
    *HYBA_FABRIC,
    *APPLE_SILICON,
    *INTEL_IGPU,
    *NVIDIA_GPU,
    *AMD_GPU,
)


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


def find_spec(
    name: Any = "",
    vendor: Any = "",
    pci_ids: Tuple[str, ...] = (),
) -> Optional[DeviceSpec]:
    """First catalog spec matching PCI evidence, alias, or vendor+alias."""
    name_l = _norm(name)
    vendor_l = _norm(vendor)
    given = tuple(t.strip().lower() for t in (pci_ids or ()) if str(t).strip())
    for spec in CATALOG:
        spec_vendor = _norm(spec.vendor)
        pci_hit = False
        for spec_id in spec.pci_ids:
            token = spec_id.lower()
            bare = token[2:] if token.startswith("0x") else token
            if (token and token in name_l) or (bare and bare in name_l):
                pci_hit = True
            for item in given:
                item_bare = item[2:] if item.startswith("0x") else item
                if item and (item == token or item == bare or item_bare == bare):
                    pci_hit = True
        alias_hit = any(a and a in name_l for a in spec.aliases)
        if pci_hit or alias_hit:
            if vendor_l and spec_vendor and spec_vendor not in vendor_l:
                continue
            return spec
    if vendor_l:
        for spec in CATALOG:
            if _norm(spec.vendor) and _norm(spec.vendor) in vendor_l:
                return spec
    return None
