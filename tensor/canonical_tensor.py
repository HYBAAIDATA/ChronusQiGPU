"""Re-export shim: bridges tensor package to kellogg.canonical_tensor.

Kellogg owns the tensor; this module provides the consolidated canonical import
point so all consumers can import from either kellogg.canonical_tensor or
tensor.canonical_tensor with identical semantics.
"""

from __future__ import annotations

from kellogg.canonical_tensor import (
    CanonicalKelloggTensor,
    CoverageProofCertificate,
    RepresentationChoice,
    build_kellogg_search_plan,
    host_sha256d_recheck,
    EstateChunk600,
    PartitionProof600,
    build_600_partition,
    AnsatzV3,
    load_ansatz,
    KelloggMotherTensor,
    PillarContractionResult,
    kellogg_state_600,
)

__all__ = [
    "CanonicalKelloggTensor",
    "CoverageProofCertificate",
    "RepresentationChoice",
    "build_kellogg_search_plan",
    "host_sha256d_recheck",
    "EstateChunk600",
    "PartitionProof600",
    "build_600_partition",
    "AnsatzV3",
    "load_ansatz",
    "KelloggMotherTensor",
    "PillarContractionResult",
    "kellogg_state_600",
]

