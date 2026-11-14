"""Consortium mapping - Tier 10 & 13: consortium to Chronus, labelled and mapped.

Translates Section 1's projection table and Section 7's detailed mappings
into typed ConsortiumProjection objects with both a projection_value and an
honest_mapping. The appendix references map institutions to capabilities.
"""

from __future__ import annotations

from .mapping import (
    ConsortiumProjection,
    map_hilbert_space,
    map_bandwidth,
    map_memory,
    map_roles,
    map_entanglement,
    project_consortium_to_chronus,
)
from .references import (
    InstitutionStatus,
    INSTITUTION_ROLES,
    INSTITUTION_STRENGTHS,
    INSTITUTION_MAPS,
    map_institution_to_chronus,
    institution_status_mapping,
)

__all__ = [
    # Tier 10 - Mapping
    "ConsortiumProjection",
    "map_hilbert_space",
    "map_bandwidth",
    "map_memory",
    "map_roles",
    "map_entanglement",
    "project_consortium_to_chronus",
    # Tier 13 - Institution references
    "InstitutionStatus",
    "INSTITUTION_ROLES",
    "INSTITUTION_STRENGTHS",
    "INSTITUTION_MAPS",
    "map_institution_to_chronus",
    "institution_status_mapping",
]
