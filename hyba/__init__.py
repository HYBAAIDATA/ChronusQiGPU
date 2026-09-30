"""HYBA substrate support package.

Turing owns computation. Chronus owns the canonical iGPU offering. ``hyba``
retains shared identity, vendor, backend, inventory, math-IR and attestation
primitives consumed by Chronus and the wider repository; it is not a competing
GPU product surface.

Nothing here invents silicon: when the HYBA MLA1517-class device is absent,
selection falls back to an enumerated GPU/CPU only where policy permits and
reports that fact, or refuses explicitly under ``HYBA_REQUIRE_HYBA=1``.

Key submodules:

- :mod:`hyba.device` — alias list, strict-mode flag, device ranking.
- :mod:`hyba.catalog` — vendor/device catalog (family, PCI, dispatch).
- :mod:`hyba.identify` — observed-evidence identity records.
- :mod:`hyba.dispatch` — enumerate + identify + rank every device.
- :mod:`hyba.vendors` — Metal / CUDA / ROCm / Vulkan / OpenCL probes.
- :mod:`hyba.backend` — fail-explicit backend binding.
- :mod:`hyba.punch` — unified punch support.
- :mod:`hyba.hasher` — SHA-256d hasher + pipeline support.
- :mod:`hyba.diagnose` — one-call observed-facts report.
- :mod:`hyba.inventory` — measured capability census across every backend.
- :mod:`chronus` — canonical iGPU offering, fabric routing and telemetry.
"""

from __future__ import annotations

__version__ = "0.1.0"

from hyba.device import (
    DEFAULT_HYBA_ALIASES,
    HYBA_REQUIRE_HYBA,
    aliases,
    describe,
    is_hyba_name,
    rank_key,
    require_hyba,
)

__all__ = [
    "__version__",
    "DEFAULT_HYBA_ALIASES",
    "HYBA_REQUIRE_HYBA",
    "aliases",
    "describe",
    "diagnose",
    "is_hyba_name",
    "rank_key",
    "require_hyba",
]


def diagnose() -> dict:
    """Collect observed device/backend facts without inventing throughput."""
    from hyba.diagnose import diagnose as _diagnose

    return _diagnose()
