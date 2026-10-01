# l_hras/asic/types.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import numpy as np

# ============================================================
# PRIMITIVE TYPES
# ============================================================

Id = str
Digest = str
Signature = str
ISO8601 = str
Duration = int
Energy = float

@dataclass(frozen=True)
class Distribution:
    mean: float
    stddev: float
    samples: int
    p50: float
    p95: float
    p99: float

@dataclass
class Ok:
    value: Any

@dataclass
class Err:
    error: 'ASICError'

# ============================================================
# ERRORS
# ============================================================

class ASICError(Enum):
    # Fold
    FOLD_NOT_APPLICABLE = "fold_not_applicable"
    FOLD_NOT_EXACT = "fold_not_exact"
    UNFOLD_FAILED = "unfold_failed"
    PRIVACY_VIOLATION = "privacy_violation"

    # Attestation
    ATTESTATION_FAILURE = "attestation_failure"
    REPLAY_FAILURE = "replay_failure"
    FORGERY_DETECTED = "forgery_detected"

    # Hash
    NO_SHARE_FOUND = "no_share_found"
    SHARE_REJECTED = "share_rejected"
    HASH_MISMATCH = "hash_mismatch"

    # Boundary
    QUBITS_EXCEEDED = "qubits_exceeded"
    NON_STABILIZER_REFUSED = "non_stabilizer_refused"

    # Hardware
    ASIC_ABSENT = "asic_absent"
    ASIC_QUARANTINED = "asic_quarantined"
    FIRMWARE_MISMATCH = "firmware_mismatch"

    # Aethel
    AETHEL_WRITE_FAILURE = "aethel_write_failure"
    AETHEL_READ_FAILURE = "aethel_read_failure"

    # Generic
    UNKNOWN = "unknown"

# ============================================================
# DEVICE CLASSES
# ============================================================

class DeviceClass(Enum):
    ASIC_CLASSIC = "asic_classic"
    ASIC_QUANTUM_ARMED = "asic_quantum_armed"

class Technology(Enum):
    CONVENTIONAL_CMOS = "conventional_cmos"
    ADIABATIC_CMOS_2LAL = "adiabatic_cmos_2lal"
    SUPERCONDUCTING_AQFP = "superconducting_aqfp"

class DeviceState(Enum):
    PRESENT = "present"
    ABSENT = "absent"
    PROVISIONING = "provisioning"
    QUARANTINED = "quarantined"
    REHABILITATED = "rehabilitated"
    DEPROVISIONED = "deprovisioned"

# ============================================================
# KERNELS
# ============================================================

class KernelName(Enum):
    # Hash
    SHA256D_SCAN = "sha256d_scan"
    SHA256D_VERIFY = "sha256d_verify"
    SHA256D_MIDSTATE = "sha256d_midstate"
    SHA256D_MERKLE = "sha256d_merkle"
    # Fold
    FOLD_11D = "fold_11d"
    UNFOLD_11D = "unfold_11d"
    ZECKENDORF_CERTIFICATE = "zeckendorf_certificate"
    # Attestation
    ATTEST_RESULT = "attest_result"
    ATTEST_COMPOSE = "attest_compose"

# ============================================================
# INTELLIGENCE
# ============================================================

class IntelligenceType(Enum):
    PREDICTIVE = "predictive"
    CAUSAL = "causal"
    COUNTERFACTUAL = "counterfactual"
    TOPOLOGICAL = "topological"
    GEOMETRIC = "geometric"
    QUANTUM = "quantum"

# ============================================================
# MODES
# ============================================================

class Mode(Enum):
    MULTIPLY = "multiply"
    ENTANGLE = "entangle"
    SWARM = "swarm"
    HONEY_POT = "honey_pot"
    WILLOW_EXPOSE = "willow_expose"
