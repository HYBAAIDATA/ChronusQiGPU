"""Deterministic mining primitives used by PYTHIA.

PYTHIA has one production mining boundary: ``chronus/mla1517_platform``.
This package contains reusable exact mining primitives and tests; it must
not claim GPU execution, pool acceptance, or measured hashrate on its own.

The canonical runtime owns device dispatch, Stratum jobs, consensus
validation, persistence, and fail-closed behaviour. These primitives may
be used only when the caller supplies real work and records the resulting
measurement.
"""

from __future__ import annotations

from .difficulty import DifficultyController
from .nonce_scheduler import NonceScheduler
from .safety_fsm import EDGES, MiningState, SafetyFSM
from .search import GroverStyleSearch, MerklePathVerifier, PreimageSearch
from .stratum_v2 import StratumV2Client, Sv2Frame, Sv2ProtocolError

__all__ = [
    "EDGES",
    "MiningState",
    "SafetyFSM",
    "NonceScheduler",
    "DifficultyController",
    "GroverStyleSearch",
    "MerklePathVerifier",
    "PreimageSearch",
    "StratumV2Client",
    "Sv2Frame",
    "Sv2ProtocolError",
]

THEOREM_PROVEN = False
