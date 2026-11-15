"""IGPU ABI — Tier 4 role-aware negotiation for the Chronus elevation.

This module implements:

    PHASE 3 — Heterogeneous Pad Role Assignment (2–3 weeks)
        Deliverable: scheduler demonstrates heterogeneous work allocation.
        Metric: 3 roles, 95%+ correct role selection.
        Gate: role negotiation contract test.
"""

from __future__ import annotations

from chronus.core.enums import AdapterRole

__all__ = [
    "role_from_consortium",
    "role_adjacency",
]


# ---------------------------------------------------------------------------
# Tier 4.1 — Consortium → role mapping (§1 table)
# ---------------------------------------------------------------------------


def role_from_consortium(institution: str) -> AdapterRole:
    """Map a consortium institution to its Chronus adapter role.

    This is the typed mapping that replaces the ad-hoc string comparisons in
    the roadmap pseudocode (§2.4).

        CERN       -> DATA_INGEST       (petabyte/s trigger pipelines)
        MIT        -> TENSOR_COMPUTE    (fabrication control -> compute)
        Caltech    -> PHOTONIC          (photonic control + metrology)
        Princeton  -> VERIFICATION      (QEC -> verification)
        Stanford   -> TENSOR_COMPUTE    (accelerators, HBM)
        Oxford     -> GENERAL           (distributed entanglement, host)
        Cambridge  -> PHOTONIC          (silicon photonics)
    """
    mapping = {
        "CERN": AdapterRole.DATA_INGEST,
        "MIT": AdapterRole.TENSOR_COMPUTE,
        "Caltech": AdapterRole.PHOTONIC,
        "Princeton": AdapterRole.VERIFICATION,
        "Stanford": AdapterRole.TENSOR_COMPUTE,
        "Oxford": AdapterRole.GENERAL,
        "Cambridge": AdapterRole.PHOTONIC,
    }
    return mapping.get(institution, AdapterRole.GENERAL)


# ---------------------------------------------------------------------------
# Tier 4.2 — Role adjacency (§2.4)
# ---------------------------------------------------------------------------


def role_adjacency(role: AdapterRole) -> set[AdapterRole]:
    """Return the adjacent roles for the given role.

    Adjacent roles share a neighbouring function in the execution substrate,
    so fallback routing never jumps arbitrarily far.
    """
    adjacency = {
        AdapterRole.DATA_INGEST: {AdapterRole.GENERAL, AdapterRole.VERIFICATION},
        AdapterRole.TENSOR_COMPUTE: {AdapterRole.GENERAL, AdapterRole.AI_TRAINING},
        AdapterRole.VERIFICATION: {AdapterRole.GENERAL, AdapterRole.DATA_INGEST},
        AdapterRole.PHOTONIC: {AdapterRole.GENERAL, AdapterRole.TENSOR_COMPUTE},
        AdapterRole.AI_TRAINING: {AdapterRole.TENSOR_COMPUTE, AdapterRole.GENERAL},
        AdapterRole.GENERAL: set(),
    }
    return adjacency.get(role, set())
