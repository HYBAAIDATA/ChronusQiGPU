"""Consortium reference mapping - Tier 13: institution to Chronus capability.

Each appendix entry becomes a typed mapping. This is the institution-level
reference that the roadmap's consortium projection table links to.
"""

from __future__ import annotations

from enum import Enum

from chronus.core.dataclasses import ConsortiumProjection
from chronus.core.enums import (
    AdapterRole,
    EvidenceClass,
    CapacityLabel,
)


class InstitutionStatus(Enum):
    PROJECTED = "PROJECTED"
    THEORETICAL = "THEORETICAL"


INSTITUTION_ROLES = {
    "CERN": (AdapterRole.DATA_INGEST, InstitutionStatus.PROJECTED),
    "MIT": (AdapterRole.TENSOR_COMPUTE, InstitutionStatus.PROJECTED),
    "Caltech": (AdapterRole.PHOTONIC, InstitutionStatus.THEORETICAL),
    "Princeton": (AdapterRole.VERIFICATION, InstitutionStatus.PROJECTED),
    "Stanford": (AdapterRole.TENSOR_COMPUTE, InstitutionStatus.PROJECTED),
    "Oxford": (AdapterRole.GENERAL, InstitutionStatus.THEORETICAL),
    "Cambridge": (AdapterRole.PHOTONIC, InstitutionStatus.THEORETICAL),
}

INSTITUTION_STRENGTHS = {
    "CERN": ("Petabyte/s trigger pipelines, radiation-hard silicon, WLCG"),
    "MIT": ("Nanofab, superconducting qubits, reversible compute"),
    "Caltech": ("Trapped ions, photonic interconnects, LIGO-grade metrology"),
    "Princeton": ("Topological qubits, QEC, MBE materials"),
    "Stanford": ("Custom accelerators, HBM, foundation models"),
    "Oxford": ("Distributed entanglement, ion networking, quantum RAM"),
    "Cambridge": ("Silicon photonics, optical compute, ML statistics"),
}

INSTITUTION_MAPS = {
    "CERN": ("Dedicated ingest adapter role + high-throughput link"),
    "MIT": ("Compute adapter with fabrication-control capability"),
    "Caltech": ("Photonic tensor core (typed unavailable; external)"),
    "Princeton": ("Verification adapter (QEC-adjacent role)"),
    "Stanford": ("GPU-class adapter (CUDA, ROCm, Metal)"),
    "Oxford": ("TURING scheduler + Chronus execution fabric"),
    "Cambridge": ("Photonic tensor core (typed unavailable; external)"),
}


def map_institution_to_chronus(inst: str) -> ConsortiumProjection:
    """Map an institution to a CapabilityManifest for the consortium reference."""
    adapter_role, status = INSTITUTION_ROLES.get(inst, (AdapterRole.GENERAL, InstitutionStatus.PROJECTED))

    evidence_class = {
        InstitutionStatus.PROJECTED: EvidenceClass.PROJECTED,
        InstitutionStatus.THEORETICAL: EvidenceClass.THEORETICAL,
    }.get(status, EvidenceClass.PROJECTED)

    label = {
        InstitutionStatus.PROJECTED: CapacityLabel.ROADMAP_TARGET,
        InstitutionStatus.THEORETICAL: CapacityLabel.ROADMAP_TARGET,
    }.get(status, CapacityLabel.DESIGN_ENVELOPE)

    return ConsortiumProjection(
        aspect=f"Institution: {inst}",
        projection_value=INSTITUTION_STRENGTHS.get(inst, ""),
        honest_mapping=INSTITUTION_MAPS.get(inst, ""),
        label=label,
        evidence_class=evidence_class,
    )


def institution_status_mapping():
    """Return the full institution-to-mapping table as a dict."""
    return {
        inst: {
            "strengths": INSTITUTION_STRENGTHS.get(inst, ""),
            "chronus_map": INSTITUTION_MAPS.get(inst, ""),
            "adapter_role": role,
            "status": status.value,
        }
        for inst, (role, status) in INSTUTION_ROLES.items()
    }
