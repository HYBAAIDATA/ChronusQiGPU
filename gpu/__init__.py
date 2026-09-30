"""Canonical GPU project package.

This package owns hardware-independent reference functions and provenance
contracts shared by iGPU, discrete-GPU and ASIC adapters. Physical execution
remains in backend packages and must report its actual backend.
"""

from .provenance import ProvenanceError, validate_provenance
from .readiness import (
    Gate,
    ProductionEvidence,
    audit_software_surfaces,
    production_readiness,
)
from .reference import (
    cassini_step,
    fibonacci,
    grover_hendrix_iterate,
    grover_iterate,
    korobov_point,
    lucas_wind,
    matmul_f4,
    matvec_f4,
    morton_step,
    pisot_wind,
    qfi_pure,
    sha256_midstate,
    sha256d,
    sha256d_merkle,
    sha256d_scan,
    sha256d_verify,
)

__all__ = [
    "ProvenanceError",
    "Gate",
    "ProductionEvidence",
    "cassini_step",
    "fibonacci",
    "grover_hendrix_iterate",
    "grover_iterate",
    "korobov_point",
    "lucas_wind",
    "matmul_f4",
    "matvec_f4",
    "morton_step",
    "pisot_wind",
    "qfi_pure",
    "sha256_midstate",
    "sha256d",
    "sha256d_merkle",
    "sha256d_scan",
    "sha256d_verify",
    "audit_software_surfaces",
    "production_readiness",
    "validate_provenance",
]
