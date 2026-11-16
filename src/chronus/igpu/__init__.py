"""iGPU — role-aware negotiation and adapter declarations for Chronus.

Chronus is a HYBA Data product/platform, not a separate company or GPU
device. This package declares Tier 4 role-aware negotiation and Tier 6
cloud-adapter rows, and re-exports the tensor representation for
iGPU-facing imports. The default execution route is CPU reference;
any client GPU route is opt-in, device-bound and fail-closed.

Requirements source: Notion records listed in
``docs/notion-production-readiness.md`` and reconciled in
``docs/production/NOTION_LIBRARY_RECONCILIATION.md``. Notion supplies
requirements and decisions, not execution evidence; release credit
requires exact-commit CI, attested gates and device-bound evidence per
``docs/claim-audit.md``.
"""

from __future__ import annotations

from importlib import resources

from .abi import role_adjacency, role_from_consortium
from .adapters import ADAPTER_TABLE, promote_adapter


def kernel_source(name: str) -> str:
    """Return the source text of a packaged OpenCL kernel."""
    if not name.endswith(".cl") or "/" in name or "\\" in name:
        raise ValueError("kernel name must be a bare *.cl file name")
    return resources.files("chronus.kernels").joinpath(name).read_text(encoding="utf-8")


__all__ = [
    "role_from_consortium",
    "role_adjacency",
    "ADAPTER_TABLE",
    "promote_adapter",
    "kernel_source",
]