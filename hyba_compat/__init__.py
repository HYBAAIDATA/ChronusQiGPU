"""Legacy-namespace compatibility for the consolidated HYBA intelligence stack.

The four packages imported from the earlier project (``asi``, ``agi``,
``enhanced_intelligence``, ``pci``) were written against a monorepo layout
with import roots ``hyba_backend``, ``hyba_platform`` and ``src``. Those roots
do not exist in this repository. What does exist is the same functionality
under different module paths, mostly consolidated into the top-level
``Intelligence`` package.

Rather than editing ~50 call sites by hand -- and rather than leaving three
already-broken modules inside ``Intelligence/`` itself -- this package
materialises the old paths as thin re-export shims pointing at the canonical
implementations.

Design rules
------------
1. Every shim resolves to a REAL canonical module in this repository. A shim
   never invents behaviour.
2. Where the earlier project referenced a module that was never migrated, the
   shim raises :class:`LegacyNamespaceRemoved` on attribute access rather than
   returning a placeholder. A loud failure is the honest signal; a quiet stub
   would let a caller believe it received real intelligence.
3. Only the compatibility surface lives here. The canonical implementations
   stay in their own packages and remain the single source of truth.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any, Dict, Iterable, Tuple

__all__ = [
    "LegacyNamespaceRemoved",
    "LEGACY_ROOTS",
    "LEGACY_MODULE_MAP",
    "KNOWN_REMOVED",
    "install",
    "uninstall",
    "is_installed",
]


class LegacyNamespaceRemoved(ImportError):
    """Raised when a pre-consolidation module has no successor in this repo."""


# The pre-consolidation import roots this shim answers for.
LEGACY_ROOTS: Tuple[str, ...] = ("hyba_backend", "hyba_platform", "src")


# Old dotted path -> canonical dotted path in THIS repository.
LEGACY_MODULE_MAP: Dict[str, str] = {
    # endpoint / bus / governance: canonical home is Intelligence/
    "hyba_backend.core.intelligence.intelligent_endpoint": ("Intelligence.intelligent_endpoint"),
    "hyba_backend.core.intelligence.intelligence_bus": "Intelligence.intelligence_bus",
    "hyba_backend.core.intelligence.autonomy_governance": ("Intelligence.autonomy_governance"),
    "hyba_backend.core.intelligence": "enhanced_intelligence",
    "hyba_backend.api.web_research": "agi.web_research",
    "hyba_backend.platform.intelligence.unified_intelligence": ("agi.unified_intelligence"),
    "hyba_backend.platform.intelligence.endpoint": "Intelligence.intelligent_endpoint",
    "hyba_backend.platform.intelligence.bus": "Intelligence.intelligence_bus",
    "hyba_backend.platform.intelligence.intelligence_bus": ("Intelligence.intelligence_bus"),
    # phi resonance scoring
    "hyba_backend.platform.resonance": "agi.resonance",
    "hyba_backend.platform.phi.resonance": "agi.resonance",
    "hyba_platform.platform.phi.resonance": "agi.resonance",
    # quantum processor
    "hyba_backend.platform.quantum_core.processor": "agi.quantum_processor",
    "hyba_platform.quantum_core.processor": "agi.quantum_processor",
    # services that became top-level packages here
    "hyba_backend.services.pci.qi": "pci.qi",
    "hyba_backend.services.pci.transparency_dashboard": "pci.transparency_dashboard",
    "hyba_backend.services.gateway.quantum_security": "agi.quantum_security",
    "hyba_backend.services.agi.reasoning": "agi.reasoning",
    "hyba_backend.services.agi.mass_gap_relaxation": "agi.mass_gap_relaxation",
    "hyba_backend.services.agi.coherence_auto_tuner": "agi.coherence_auto_tuner",
    "hyba_backend.services.agi.monitoring_dashboard": "agi.monitoring_dashboard",
    "hyba_backend.services.agi.intelligence_bus_integration": ("agi.intelligence_bus_integration"),
    "hyba_backend.services.agi.knowledge_base": "agi.enhanced_ai.knowledge_base",
    "hyba_backend.services.agi.enhanced_ai.knowledge_base": ("agi.enhanced_ai.knowledge_base"),
    "hyba_backend.services.agi.enhanced_ai.conversational_interface": (
        "agi.enhanced_ai.conversational_interface"
    ),
    "hyba_backend.services.agi.enhanced_ai.nlp_processor": ("agi.enhanced_ai.nlp_processor"),
    "hyba_backend.services.agi.protein_refolding_engine": ("agi.protein_refolding_engine"),
    # the old PCI algorithm package: canonical home is pci/engine
    "src.hyba_quantum.algorithms.pci": "pci.engine",
    "src.hyba_quantum.algorithms.asi_agency_framework": "agi.agency",
}

# Legacy roots that were never migrated and have no canonical successor.
# Listed so the failure message is specific rather than a bare ImportError.
KNOWN_REMOVED: Tuple[str, ...] = (
    "hyba_backend.platform.audit.logging",
    "hyba_backend.platform.intelligence.intelligence_middleware",
    "hyba_backend.platform.substrate.universal_substrate",
    "hyba_backend.platform.substrate.adapters",
    "hyba_backend.internal.backend.amplified_resonant_structured_grover",
    "hyba_backend.internal.backend.yang_mills_mining_bridge",
    "src.mining.pulvini_mining_engine",
)

# Intermediate packages that exist only so the leaf paths above resolve.
# Attribute access on one of these raises rather than silently returning None.
_ALIAS_PACKAGES: Tuple[str, ...] = (
    "hyba_backend",
    "hyba_backend.core",
    "hyba_backend.core.intelligence",
    "hyba_backend.platform",
    "hyba_backend.platform.intelligence",
    "hyba_backend.platform.phi",
    "hyba_backend.platform.quantum_core",
    "hyba_backend.platform.substrate",
    "hyba_backend.platform.audit",
    "hyba_backend.api",
    "hyba_backend.services",
    "hyba_backend.services.agi",
    "hyba_backend.services.agi.enhanced_ai",
    "hyba_backend.services.pci",
    "hyba_backend.services.gateway",
    "hyba_backend.internal",
    "hyba_backend.internal.backend",
    "hyba_platform",
    "hyba_platform.platform",
    "hyba_platform.platform.phi",
    "hyba_platform.quantum_core",
    "src",
    "src.hyba_quantum",
    "src.hyba_quantum.algorithms",
    "src.mining",
)

_INSTALLING = False


class _AliasModule(ModuleType):
    """A legacy module path that forwards attribute access to a real module."""

    _hyba_target: str = ""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        try:
            target = importlib.import_module(self._hyba_target)
        except ImportError as exc:  # pragma: no cover - defensive
            raise LegacyNamespaceRemoved(
                f"{self.__name__}.{name} forwards to "
                f"{self._hyba_target!r}, which failed to import: {exc}"
            ) from exc
        try:
            return getattr(target, name)
        except AttributeError as exc:
            raise AttributeError(
                f"{self.__name__!r} has no attribute {name!r} "
                f"(forwarded from {self._hyba_target!r})"
            ) from exc

    def __dir__(self) -> Iterable[str]:
        try:
            return dir(importlib.import_module(self._hyba_target))
        except ImportError:  # pragma: no cover - defensive
            return []


class _RemovedModule(ModuleType):
    """A legacy module path with no canonical successor in this repository."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        raise LegacyNamespaceRemoved(
            f"{self.__name__!r} was part of the pre-consolidation HYBA monorepo "
            f"and has no counterpart in this repository, so {name!r} is "
            f"unavailable. Implement the capability explicitly rather than "
            f"accepting a placeholder."
        )


def _make_alias(fullname: str, target: str) -> ModuleType:
    mod = _AliasModule(fullname)
    mod._hyba_target = target
    mod.__doc__ = (
        f"Compatibility alias: ``{fullname}`` -> ``{target}``."
        f" Canonical implementation is ``{target}``."
    )
    return mod


def _make_removed(fullname: str) -> ModuleType:
    mod = _RemovedModule(fullname)
    mod.__doc__ = f"Removed legacy namespace: ``{fullname}``. No canonical successor."
    return mod


def _alias_parents(fullname: str) -> Iterable[str]:
    """Yield every ancestor package path of ``fullname``."""
    parts = fullname.split(".")
    for i in range(1, len(parts)):
        yield ".".join(parts[:i])


def install() -> Dict[str, str]:
    """Register every legacy alias in :data:`sys.modules`.

    Returns a mapping of installed legacy path -> canonical path so a caller
    or test can audit exactly what was bridged.
    """
    global _INSTALLING
    if _INSTALLING:  # pragma: no cover - re-entrancy guard
        return {}
    _INSTALLING = True
    installed: Dict[str, str] = {}
    try:
        for legacy, canonical in LEGACY_MODULE_MAP.items():
            for parent in _alias_parents(legacy):
                if parent not in sys.modules:
                    sys.modules[parent] = _make_removed(parent)
            sys.modules[legacy] = _make_alias(legacy, canonical)
            installed[legacy] = canonical

        for removed in KNOWN_REMOVED:
            for parent in _alias_parents(removed):
                if parent not in sys.modules:
                    sys.modules[parent] = _make_removed(parent)
            if removed not in sys.modules:
                sys.modules[removed] = _make_removed(removed)
                installed[removed] = "<removed>"

        for pkg in _ALIAS_PACKAGES:
            if pkg not in sys.modules:
                sys.modules[pkg] = _make_removed(pkg)
                installed[pkg] = "<namespace>"
    finally:
        _INSTALLING = False
    return installed


def uninstall() -> None:
    """Remove every alias this shim installed, leaving the rest untouched."""
    managed = (
        set(LEGACY_MODULE_MAP)
        | set(KNOWN_REMOVED)
        | set(_ALIAS_PACKAGES)
        | {p for legacy in LEGACY_MODULE_MAP for p in _alias_parents(legacy)}
        | {p for removed in KNOWN_REMOVED for p in _alias_parents(removed)}
    )
    for name in managed:
        sys.modules.pop(name, None)


def is_installed() -> bool:
    """True when a legacy root currently resolves through this shim."""
    return any(
        isinstance(sys.modules.get(root), (_AliasModule, _RemovedModule)) for root in LEGACY_ROOTS
    )
