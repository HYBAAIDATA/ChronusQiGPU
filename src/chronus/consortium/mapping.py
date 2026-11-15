"""Consortium mapping - Tier 10: consortium to Chronus, labelled and mapped.

Translates Section 1's projection table and Section 7's detailed mappings
into typed ConsortiumProjection objects with both a projection_value and an
honest_mapping.
"""

from __future__ import annotations

from typing import List

from chronus.core.dataclasses import ConsortiumProjection
from chronus.core.enums import (
    CapacityLabel,
    EvidenceClass,
)

__all__ = [
    "ConsortiumProjection",
    "map_hilbert_space",
    "map_bandwidth",
    "map_memory",
    "map_roles",
    "map_entanglement",
    "project_consortium_to_chronus",
]


# ---------------------------------------------------------------------------
# Tier 10.1 - Hilbert space mapping (section 7.1)
# ---------------------------------------------------------------------------


def map_hilbert_space() -> ConsortiumProjection:
    """Map the consortium Hilbert-space projection."""
    return ConsortiumProjection(
        aspect="hilbert_dimension",
        projection_value="2^640 = (2^64)^10",
        honest_mapping=(
            "dim=32 per pad; multipad state is tensor product only when pads "
            "execute jointly"
        ),
        label=CapacityLabel.ROADMAP_TARGET,
        evidence_class=EvidenceClass.THEORETICAL,
    )


# ---------------------------------------------------------------------------
# Tier 10.2 - Bandwidth mapping (section 7.2)
# ---------------------------------------------------------------------------


def map_bandwidth(fleet: List[dict]) -> ConsortiumProjection:
    """Map the consortium bandwidth projection."""
    aggregate = sum(a.get("bandwidth_mbps", 0) for a in fleet) / 1e6
    return ConsortiumProjection(
        aspect="interconnect",
        projection_value="1.2 PB/s optical + 10 PBS CERN trigger + infinity entanglement",
        honest_mapping=(
            "per-adapter bandwidth declared in capabilities; aggregate = "
            "sum(adapter_bw) / 1e6; current=%s PB/s" % aggregate
        ),
        label=CapacityLabel.DESIGN_ENVELOPE,
        evidence_class=EvidenceClass.MEASURED,
    )


# ---------------------------------------------------------------------------
# Tier 10.3 - Memory mapping (section 7.3)
# ---------------------------------------------------------------------------


def map_memory() -> ConsortiumProjection:
    """Map the consortium memory projection."""
    return ConsortiumProjection(
        aspect="memory",
        projection_value="1 EB + 20 TB + 2 TB/pad + quantum RAM",
        honest_mapping=(
            "Tier 0: <= 2 TB/adapter; Tier 1: <= 20 TB shared; Tier 2: remote/"
            "cloud (external); Tier 3: theoretical (TURING)"
        ),
        label=CapacityLabel.DESIGN_ENVELOPE,
        evidence_class=EvidenceClass.MEASURED,
    )


# ---------------------------------------------------------------------------
# Tier 10.4 - Role heterogeneity mapping (section 7.4)
# ---------------------------------------------------------------------------


def map_roles() -> ConsortiumProjection:
    """Map the consortium role heterogeneity projection."""
    return ConsortiumProjection(
        aspect="institutions/roles",
        projection_value="CERN ingest, MIT fabrication, Caltech photonics, ...",
        honest_mapping=(
            "adapter declares role in CapabilityManifest; scheduler routes by "
            "role preference + load; fallback: any trusted adapter can run any "
            "work"
        ),
        label=CapacityLabel.DESIGN_ENVELOPE,
        evidence_class=EvidenceClass.PROJECTED,
    )


# ---------------------------------------------------------------------------
# Tier 10.5 - GHZ entanglement mapping (section 7.5)
# ---------------------------------------------------------------------------


def map_entanglement() -> ConsortiumProjection:
    """Map the consortium GHZ entanglement projection."""
    return ConsortiumProjection(
        aspect="ghz_entanglement",
        projection_value="Full-mesh cluster state on 10 pads",
        honest_mapping=(
            "TURING substrate; Chronus schedules, does not materialize quantum "
            "state; measurement bases per-adapter via trust class"
        ),
        label=CapacityLabel.ROADMAP_TARGET,
        evidence_class=EvidenceClass.THEORETICAL,
    )


# ---------------------------------------------------------------------------
# Tier 10.6 - Master projection table (section 1)
# ---------------------------------------------------------------------------


def project_consortium_to_chronus(fleet: List[dict] = None) -> List[ConsortiumProjection]:
    """Project the consortium mapping to Chronus as a list of labelled projections."""
    projections = [
        map_hilbert_space(),
        map_bandwidth(fleet or []),
        map_memory(),
        map_roles(),
        map_entanglement(),
    ]
    return projections
