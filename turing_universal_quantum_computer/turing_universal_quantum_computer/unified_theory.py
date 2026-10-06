"""Executable Unified Theory foundation contract.

The contract is intentionally small and dependency-free so the operational
PYTHIA distribution and the separately built Turing VQC distribution can each
carry, validate, and expose the same foundation without importing one another.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

SCHEMA = "hyba.unified_theory.foundation.v1"
VERSION = "1.0.0"

_AXIOMS = (
    (
        "representation_truth",
        "Every result names its producing representation and whether state "
        "was materialized.",
    ),
    (
        "evidence_separation",
        "Verified computation, experimental hypotheses, and speculative "
        "foundations remain distinct.",
    ),
    (
        "validity_authority",
        "Ordering and intelligence never override the domain's exact validity predicate.",
    ),
    (
        "finite_resource_accounting",
        "Logical or symbolic address spaces never become claims of "
        "unallocated physical resources.",
    ),
    (
        "immutable_reference_constants",
        "Reference constants are immutable; overrides create labelled simulation contexts only.",
    ),
    (
        "deterministic_provenance",
        "Material decisions bind inputs, configuration, execution class, and evidence to a digest.",
    ),
    (
        "complete_fallback",
        "Experimental ordering may lead, but an exact complete fallback remains available.",
    ),
    (
        "measurement_before_promotion",
        "Correctness tests do not establish comparative advantage; promotion "
        "requires measured evidence.",
    ),
)


@dataclass(frozen=True)
class UnifiedTheoryFoundation:
    schema: str = SCHEMA
    version: str = VERSION

    @property
    def axioms(self):
        return MappingProxyType(dict(_AXIOMS))

    def payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "axioms": [{"id": key, "statement": value} for key, value in _AXIOMS],
            "scope": "computational architecture and evidence governance",
            "physical_theory_claimed": False,
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def report(self) -> dict[str, Any]:
        return {
            **self.payload(),
            "digest": self.digest,
            "axiom_count": len(_AXIOMS),
            "verified": self.verify(),
        }

    def verify(self) -> bool:
        ids = [key for key, _value in _AXIOMS]
        return (
            self.schema == SCHEMA
            and self.version == VERSION
            and len(ids) == len(set(ids))
            and all(key and statement for key, statement in _AXIOMS)
        )


UNIFIED_THEORY = UnifiedTheoryFoundation()

__all__ = [
    "SCHEMA",
    "UNIFIED_THEORY",
    "VERSION",
    "UnifiedTheoryFoundation",
]
