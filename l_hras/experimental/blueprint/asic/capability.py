# l_hras/asic/capability.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import numpy as np
from l_hras.experimental.blueprint.asic.types import *

@dataclass
class ASICCapability:
    """The complete capability of a quantum-armed ASIC."""

    # Identity
    device_id:          Id
    vendor:             str
    model:              str
    firmware_digest:    Digest
    technology:         Technology
    device_class:       DeviceClass

    # Classic performance
    hashrate:           Distribution
    power:              Distribution
    efficiency:         Distribution

    # Quantum arsenal
    fold_capable:       bool
    max_fold_qubits:    int
    supported_kernels:  Set[KernelName]

    # State
    state:              DeviceState

    # Attestation
    attestation_chain:  List[Dict]

    # Extensions
    vendor_extensions:  Dict[str, str] = field(default_factory=dict)
