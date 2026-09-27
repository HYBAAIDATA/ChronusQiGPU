"""hyba.hybrid — GPU + ASIC hybrid substrate.

Two heterogeneous silicon substrates cooperate on the same nonce search:
the GPU runs the traversal layer (ordering, scheduling, attestation) and
the ASIC — when physically attached — runs raw double-SHA256 at silicon
speed. A deterministic Lucas-weighted partitioner assigns nonce windows
by predicted yield; a coordinator dispatches them, re-verifies every
returned share on the host, and attests every lifecycle event.

When no ASIC is present the path degrades to GPU-only with an explicit
attestation gap — never to a simulated ASIC.
"""

from hyba.hybrid.asic_solver import ASICSolver
from hyba.hybrid.coordinator import HybridCoordinator, JobResult, StratumJob
from hyba.hybrid.gpu_solver import GPUSolver
from hyba.hybrid.lucas_partition import (
    CoverageCertificate,
    FACE_COUNT,
    SpanAssignment,
    TraversalHistory,
    TraversalRecord,
    lucas_alignment,
    lucas_weight,
    partition,
)
from hyba.hybrid.nonce_scheduler import (
    ASICNotPresent,
    AttestationRegistry,
    AttestationViolation,
    DeviceCapability,
    DeviceUnsupportedError,
    DispatchHandle,
    ExecutionAttestation,
    NONCE_SPACE,
    NonceScheduler,
    NonceWindow,
    Share,
    verify_share,
)

__all__ = [
    "ASICNotPresent",
    "ASICSolver",
    "AttestationRegistry",
    "AttestationViolation",
    "CoverageCertificate",
    "DeviceCapability",
    "DeviceUnsupportedError",
    "DispatchHandle",
    "ExecutionAttestation",
    "FACE_COUNT",
    "GPUSolver",
    "HybridCoordinator",
    "JobResult",
    "NONCE_SPACE",
    "NonceScheduler",
    "NonceWindow",
    "Share",
    "SpanAssignment",
    "StratumJob",
    "TraversalHistory",
    "TraversalRecord",
    "lucas_alignment",
    "lucas_weight",
    "partition",
    "verify_share",
]
