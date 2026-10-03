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
    generic: bool = False


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

INTEL_Chronus = (
    DeviceSpec(
        "intel-uhd-620",
        "Intel",
        ("intel-uhd-620", "uhd graphics 620", "uhd 620", "uhd620", "0x5917", "5917"),
        ("0x5917", "5917"),
        ("opencl", "cpu"),
        "opencl",
        "Kaby Lake-R GT2 24EU dev reference",
    ),
    DeviceSpec(
        "intel-uhd-630",
        "Intel",
        ("intel-uhd-630", "uhd graphics 630", "uhd 630", "uhd630"),
        (),
        ("opencl", "cpu"),
        "opencl",
        "Comet Lake GT2; name-alias match only (PCI id unverified)",
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

# Last-resort vendor entries. They exist so an unlisted GPU of a known vendor
# reports "vendor, model unverified" instead of being filed under whichever
# model happens to sit first in the catalog, and so a generic token such as
# "graphics" can never win over a model-specific rule.
GENERIC_VENDORS = (
    DeviceSpec(
        "intel-generic",
        "Intel",
        ("graphics",),
        (),
        ("opencl", "cpu"),
        "opencl",
        "Intel GPU, model unverified; name-alias only",
        generic=True,
    ),
    DeviceSpec(
        "apple-generic",
        "Apple",
        ("gpu",),
        (),
        ("opencl", "cpu"),
        "opencl",
        "Apple GPU, model unverified; name-alias only",
        generic=True,
    ),
    DeviceSpec(
        "nvidia-generic",
        "NVIDIA",
        ("gpu",),
        (),
        ("opencl", "cpu"),
        "opencl",
        "NVIDIA GPU, model unverified; name-alias only",
        generic=True,
    ),
    DeviceSpec(
        "amd-generic",
        "AMD",
        ("gpu",),
        (),
        ("opencl", "cpu"),
        "opencl",
        "AMD GPU, model unverified; name-alias only",
        generic=True,
    ),
)

CATALOG: Tuple[DeviceSpec, ...] = (
    *HYBA_FABRIC,
    *APPLE_SILICON,
    *INTEL_Chronus,
    *NVIDIA_GPU,
    *AMD_GPU,
    *GENERIC_VENDORS,
)


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


# Match tiers, strongest evidence first. A generic vendor entry can never reach
# a model-specific tier, so "graphics" can only be selected after every
# model-specific rule has been tried and found nothing.
_TIER_PCI_ENV = 4
_TIER_PCI_NAME = 3
_TIER_ALIAS = 2
_TIER_GENERIC_ALIAS = 1
_TIER_VENDOR = 0


def _pci_tokens(spec: DeviceSpec) -> Tuple[str, ...]:
    """Every form of each PCI id: prefixed and bare."""
    tokens: list = []
    for spec_id in spec.pci_ids:
        token = _norm(spec_id)
        if not token:
            continue
        tokens.append(token)
        if token.startswith("0x") and len(token) > 2:
            tokens.append(token[2:])
    return tuple(tokens)


def _match_score(
    spec: DeviceSpec,
    name_l: str,
    vendor_l: str,
    given: Tuple[str, ...],
) -> Optional[Tuple[int, int]]:
    """``(tier, specificity)`` for one spec against observed evidence.

    Tiers descend from an operator-supplied PCI id, to a PCI id visible in the
    reported name, to a name alias, to a generic alias, to vendor evidence
    alone. Within the alias tiers the longest matching alias wins, so a
    model-specific rule always outranks a shorter or generic one. A generic
    spec is limited to the two lowest tiers: it must never claim a model on
    evidence that does not identify one.
    """
    spec_vendor = _norm(spec.vendor)
    if vendor_l and spec_vendor and spec_vendor not in vendor_l:
        return None

    tokens = _pci_tokens(spec)
    if spec_vendor or tokens:
        if any(token in given for token in tokens):
            return (_TIER_PCI_ENV, 0)
        if any(token in name_l for token in tokens):
            return (_TIER_PCI_NAME, 0)

    hits = [alias for alias in spec.aliases if alias and alias in name_l]
    if hits and not spec.generic:
        return (_TIER_ALIAS, max(len(alias) for alias in hits))
    if hits and spec.generic:
        return (_TIER_GENERIC_ALIAS, max(len(alias) for alias in hits))
    if spec.generic and vendor_l and spec_vendor and spec_vendor in vendor_l:
        return (_TIER_VENDOR, 0)
    return None


def find_spec(
    name: Any = "",
    vendor: Any = "",
    pci_ids: Tuple[str, ...] = (),
) -> Optional[DeviceSpec]:
    """Best catalog spec for the observed evidence, or None when unverified.

    The strongest evidence wins, not the catalog order. A vendor string alone no
    longer selects that vendor's first-listed model: it selects the vendor's
    generic entry, so an unlisted GPU is reported as unverified rather than
    mislabelled as a model that was never observed.
    """
    name_l = _norm(name)
    vendor_l = _norm(vendor)
    given = tuple(t.strip().lower() for t in (pci_ids or ()) if str(t).strip())
    best: Optional[DeviceSpec] = None
    best_score: Optional[Tuple[int, int]] = None
    for spec in CATALOG:
        score = _match_score(spec, name_l, vendor_l, given)
        if score is None:
            continue
        # Strictly greater keeps the first catalog entry on an exact tie.
        if best_score is None or score > best_score:
            best, best_score = spec, score
    return best
