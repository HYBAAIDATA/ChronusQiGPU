"""HYBA compute package — one honest home for device identity and backends.

This package consolidates the HYBA alias contract, the vendor catalog
(Apple / Intel / NVIDIA / AMD+HPE), OpenCL device ranking, backend
binding, punch scoring, SHA-256d hashing, and iGPU telemetry that were
previously duplicated across ``Intelligence/``, ``mining/``, and
``scripts/``. Nothing here invents silicon: when the HYBA MLA1517-class
device is absent, selection falls back to the enumerated GPU/CPU and says
so, or refuses explicitly under ``HYBA_REQUIRE_HYBA=1``.

Submodules:

- :mod:`hyba.device` — alias list, strict-mode flag, device ranking.
- :mod:`hyba.catalog` — vendor/device catalog (family, PCI, dispatch).
- :mod:`hyba.identify` — observed-evidence identity records.
- :mod:`hyba.dispatch` — enumerate + identify + rank every device.
- :mod:`hyba.vendors` — Metal / CUDA / ROCm / Vulkan / OpenCL probes.
- :mod:`hyba.gpureport` — one aggregated JSON GPU truth surface.
- :mod:`hyba.backend` — re-export of the fail-explicit backend binder.
- :mod:`hyba.punch` — re-export of the unified punch host.
- :mod:`hyba.hasher` — re-export of the SHA-256d hasher + pipeline.
- :mod:`hyba.telemetry` — re-export of the iGPU telemetry collector.
- :mod:`hyba.diagnose` — one-call observed-facts report (no projections).
- :mod:`hyba.inventory` — measured capability census across every backend.
- :mod:`hyba.virtual_gpu` — SuperGPU composition + op routing.
"""

from __future__ import annotations

# Canonical version declaration for the hyba package — the only literal
# in the package; tracks the repo distribution (see
# reports/version_consolidation.md).
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
