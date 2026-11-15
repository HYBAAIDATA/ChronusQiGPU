"""Chronus Stratum V1 mining protocol implementation.

Public API surface for Stratum V1 pool communication, block-header assembly,
and share validation. All runtime code should import from this package rather
than the deprecated ``chronus.execution.stratum`` module.
"""

from chronus.stratum.endian_engine import (
    StratumJob,
    StratumSession,
    build_header80,
    build_header_prefix,
    compute_merkle_root_stratum,
    difficulty_to_target,
    merkle_root,
    sha256d,
    swap_prevhash_words,
)
from chronus.stratum.gateway import StratumGateway
from chronus.stratum.bip310 import apply_version_rolling
from chronus.stratum.sharding import WorkPartitioner, ShareCandidate
from chronus.stratum.gatekeeper import LocalPreSubmitGatekeeper, compute_share_target_exact

__all__ = [
    "StratumGateway",
    "StratumJob",
    "StratumSession",
    "build_header80",
    "build_header_prefix",
    "compute_merkle_root_stratum",
    "difficulty_to_target",
    "merkle_root",
    "sha256d",
    "swap_prevhash_words",
    "apply_version_rolling",
    "WorkPartitioner",
    "ShareCandidate",
    "LocalPreSubmitGatekeeper",
    "compute_share_target_exact",
]
