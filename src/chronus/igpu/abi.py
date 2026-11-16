"""IGPU ABI — Tier 4 role-aware negotiation for Chronus (HYBA Data).

Maps consortium institutions to adapter roles for scheduler fallback
routing. This is role metadata only; it does not provision hardware,
measure performance, or establish deployment. Requirements trace to
the Notion records in ``docs/notion-production-readiness.md``;
evidence status follows ``docs/claim-audit.md``.
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
        AdapterRole.TENSOR_COMPUTE: {AdapterRole.GENERAL, AdapterRole.DATA_INGEST},
        AdapterRole.VERIFICATION: {AdapterRole.GENERAL, AdapterRole.DATA_INGEST},
        AdapterRole.PHOTONIC: {AdapterRole.GENERAL, AdapterRole.TENSOR_COMPUTE},
        AdapterRole.AI_TRAINING: {AdapterRole.TENSOR_COMPUTE, AdapterRole.GENERAL},
        AdapterRole.GENERAL: set(),
    }
    return adjacency.get(role, set())
