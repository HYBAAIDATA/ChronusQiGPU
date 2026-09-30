"""Canonical GPU project package.

This package owns hardware-independent reference functions and provenance
contracts shared by iGPU, discrete-GPU and ASIC adapters. Physical execution
remains in backend packages and must report its actual backend.
"""

from .provenance import ProvenanceError, validate_provenance
from .reference import (
    grover_hendrix_iterate,
    grover_iterate,
    matmul_f4,
    matvec_f4,
    qfi_pure,
    sha256_midstate,
    sha256d,
    sha256d_merkle,
    sha256d_scan,
    sha256d_verify,
)

__all__ = [
    "ProvenanceError",
    "grover_hendrix_iterate",
    "grover_iterate",
    "matmul_f4",
    "matvec_f4",
    "qfi_pure",
    "sha256_midstate",
    "sha256d",
    "sha256d_merkle",
    "sha256d_scan",
    "sha256d_verify",
    "validate_provenance",
]
