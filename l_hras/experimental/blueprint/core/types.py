# l_hras/core/types.py

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum
import numpy as np

# ============================================================
# PRIMITIVE TYPES
# ============================================================

Id = str
Digest = str
Signature = str
ISO8601 = str
CanonicalJSON = str
Duration = int          # nanoseconds
Energy = float          # joules
Complex = complex

@dataclass(frozen=True)
class Distribution:
    mean: float
    stddev: float
    samples: int
    p50: float
    p95: float
    p99: float

class Result(Enum):
    OK = "ok"
    ERR = "err"

@dataclass
class Ok:
    value: Any

@dataclass
class Err:
    error: 'Error'

# ============================================================
# ERRORS
# ============================================================

class Error(Enum):
    # Fold
    FOLD_NOT_EXACT = "fold_not_exact"
    UNFOLD_FAILED = "unfold_failed"
    PRIVACY_VIOLATION = "privacy_violation"
    # Attestation
    ATTESTATION_FAILURE = "attestation_failure"
    REPLAY_FAILURE = "replay_failure"
    FORGERY_DETECTED = "forgery_detected"
    # Security
    SECURITY_VIOLATION = "security_violation"
    TOPOLOGICAL_ANOMALY = "topological_anomaly"
    GEOMETRIC_DRIFT = "geometric_drift"
    ENTANGLEMENT_BREAK = "entanglement_break"
    SWARM_QUORUM_FAILED = "swarm_quorum_failed"
    HONEY_POT_ESCAPED = "honey_pot_escaped"
    WILLOW_FAILED = "willow_failed"
    # Mining
    POOL_DISCONNECT = "pool_disconnect"
    STALE_JOB = "stale_job"
    KERNEL_UNAVAILABLE = "kernel_unavailable"
    BUFFER_CORRUPTION = "buffer_corruption"
    HASHRATE_BELOW_FLOOR = "hashrate_below_floor"
    SHARE_REJECTED = "share_rejected"
    # Aethel
    AETHEL_WRITE_FAILURE = "aethel_write_failure"
    AETHEL_READ_FAILURE = "aethel_read_failure"
    # Generic
    UNKNOWN = "unknown"

# ============================================================
# DEVICE CLASSES
# ============================================================

class DeviceClass(Enum):
    GPU_INTEGRATED = "gpu_integrated"
    GPU_DISCRETE = "gpu_discrete"
    GPU_DATACENTER = "gpu_datacenter"
    ASIC = "asic"
    FPGA = "fpga"
    TPU = "tpu"
    CPU_REFERENCE = "cpu_reference"
    ADIABATIC_CMOS = "adiabatic_cmos"
    SUPERCONDUCTING = "superconducting"

class Technology(Enum):
    CONVENTIONAL_CMOS = "conventional_cmos"
    ADIABATIC_CMOS_2LAL = "adiabatic_cmos_2lal"
    SUPERCONDUCTING_AQFP = "superconducting_aqfp"
    QUANTUM_ANNEALER = "quantum_annealer"

class DeviceState(Enum):
    PRESENT = "present"
    ABSENT = "absent"
    PROVISIONING = "provisioning"
    QUARANTINED = "quarantined"
    REHABILITATED = "rehabilitated"
    DEPROVISIONED = "deprovisioned"
