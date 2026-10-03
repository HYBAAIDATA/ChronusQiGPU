"""HYBA device identity — the single source of truth for the alias contract.

The HYBA MLA1517-class iGPU is identified by substring match against the
OpenCL device name. ``HYBA_DEVICE_ALIAS`` overrides the default tuple with
a comma-separated list; ``HYBA_REQUIRE_HYBA=1`` refuses to substitute any
other device instead of silently hashing elsewhere.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Mapping, Optional

DEFAULT_HYBA_ALIASES = ("hyba-mla1517", "hyba_mla1517", "mla1517", "hyba")

HYBA_REQUIRE_HYBA = "HYBA_REQUIRE_HYBA"


class AliasUnresolvedError(RuntimeError):
    """No requested alias resolved while strict HYBA selection was required."""


def aliases(raw: Optional[str] = None) -> tuple:
    """Alias list for the HYBA iGPU; env override wins when non-empty."""
    text = raw if raw is not None else os.environ.get("HYBA_DEVICE_ALIAS", "")
    text = (text or "").strip()
    if text:
        return tuple(a.strip().lower() for a in text.split(",") if a.strip())
    return DEFAULT_HYBA_ALIASES


def require_hyba(raw: Optional[str] = None) -> bool:
    """True when strict HYBA-only selection is requested."""
    text = raw if raw is not None else os.environ.get(HYBA_REQUIRE_HYBA, "")
    return (text or "").strip().lower() in ("1", "true", "yes", "on")


def is_hyba_name(name: Any, alias_list: Optional[Iterable[str]] = None) -> Optional[str]:
    """Return the matching alias for a device name, else None."""
    lowered = str(getattr(name, "name", name) or "").strip().lower()
    for alias in alias_list if alias_list is not None else aliases():
        if alias and alias in lowered:
            return alias
    return None


def alias_registry() -> dict:
    """Every catalog alias mapped to its family, so an alias names real silicon.

    Built from :mod:`hyba.catalog` so an alias can never resolve to a family the
    catalog does not declare; an unknown alias stays unresolved.
    """
    from hyba.catalog import CATALOG

    registry: dict = {}
    for spec in CATALOG:
        for alias in spec.aliases:
            if alias:
                registry.setdefault(alias, spec.family)
    return registry


def resolve_alias(raw: Optional[str] = None, registry: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Resolve the first requested alias to a catalog family, else None.

    ``HYBA_REQUIRE_HYBA=1`` raises :class:`AliasUnresolvedError` when no alias
    resolves, so a strict deployment never binds a substitute device. With
    ``HYBA_REQUIRE_HYBA=0`` an unresolved alias is advisory and returns None:
    ``HYBA_REQUIRE_HYBA=0`` means exactly "do not fail when HYBA cannot resolve
    this", and the caller keeps its non-HYBA route.
    """
    table = dict(registry if registry is not None else alias_registry())
    for alias in aliases(raw):
        family = table.get(alias)
        if family:
            return family
    if require_hyba():
        raise AliasUnresolvedError(
            f"HYBA_REQUIRE_HYBA set but no alias in {list(aliases(raw))} "
            f"resolves to a catalog family"
        )
    return None


def rank_key(name: Any, is_gpu: bool, alias_list: Optional[Iterable[str]] = None) -> tuple:
    """Pure preference key: HYBA-alias device first, then GPU, then name."""
    lowered = str(getattr(name, "name", name) or "").strip().lower()
    hit = is_hyba_name(lowered, alias_list if alias_list is not None else aliases())
    return (0 if hit else 1, 0 if is_gpu else 1, lowered)


def describe(device: Any, alias_list: Optional[Iterable[str]] = None) -> dict:
    """Observed device facts: name, type flags, and alias match (if any)."""
    name = str(getattr(device, "name", "") or "").strip()
    dtype = int(getattr(device, "type", 0) or 0)
    return {
        "name": name,
        "type_bits": dtype,
        "hyba_alias": is_hyba_name(name, alias_list),
    }
