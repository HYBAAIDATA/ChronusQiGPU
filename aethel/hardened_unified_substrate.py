"""Flat compatibility façade for the consolidated Aethel substrate.

This module preserves the historical ``hardened_unified_substrate`` import
surface — every public name the monolith exported is re-exported here from
the focused ``aethel`` submodules.  ``toe.hardened_unified_substrate`` and
``Intelligence.hardened_unified_substrate`` resolve to this module object,
so isinstance checks and module identity hold across all three paths.
"""

from .cassini import CassiniVerifier
from .compute import (
    CollectiveOps,
    ComputeUnitPool,
    DAGNode,
    DependencyDAG,
    DistributedActor,
    DistributedDataflowGraph,
    MicroKernelLibrary,
    OptimizedTensorMicroKernel,
    RTCoreMicroKernel,
    SPMDExecutor,
    VirtualSM,
    VirtualWarp,
)
from .constants import (
    DIM,
    LUCAS_15,
    LUCAS_20,
    LUCAS_31,
    MODULUS_Q,
    PHI,
    PRIMES_25,
    PSI,
    SQRT5,
)
from .gpu import TensorCoreGPU_Context
from .manifold import (
    GeodesicNavigator,
    ManifoldCurvature,
    ManifoldSector,
    PrimeStorageManifold,
    SelfHealingSubstrate,
    TopologicalTensor,
)
from .primes import GaloisPrimeSubstrate, PrimeCell
from .unified import HardenedUnifiedSubstrate, UnifiedSubstrate
from .zeckendorf import (
    PUNCH_MANIFOLD_COMPUTE,
    PUNCH_ZECKENDORF_DECODE,
    PUNCH_ZECKENDORF_ENCODE,
    HardenedZeckendorfCodec,
    SparseTopology,
    apply_zeckendorf_compression,
    reverse_zeckendorf_expansion,
)

__all__ = [
    # constants
    "DIM", "PHI", "PSI", "SQRT5",
    "LUCAS_15", "LUCAS_20", "LUCAS_31",
    "MODULUS_Q", "PRIMES_25",
    # Cassini invariant
    "CassiniVerifier",
    # Zeckendorf codec + sparse topology
    "HardenedZeckendorfCodec", "SparseTopology",
    "apply_zeckendorf_compression", "reverse_zeckendorf_expansion",
    "PUNCH_MANIFOLD_COMPUTE", "PUNCH_ZECKENDORF_ENCODE", "PUNCH_ZECKENDORF_DECODE",
    # Galois prime substrate
    "GaloisPrimeSubstrate", "PrimeCell",
    # Layer 1: compute units
    "VirtualSM", "ComputeUnitPool",
    # Layer 2: SPMD / SIMT
    "VirtualWarp", "SPMDExecutor",
    # Layer 3: micro-kernels
    "OptimizedTensorMicroKernel", "RTCoreMicroKernel", "MicroKernelLibrary",
    # Layer 4: distributed
    "DistributedActor", "CollectiveOps", "DistributedDataflowGraph",
    # Layer 5: DAG
    "DAGNode", "DependencyDAG",
    # GPU context
    "TensorCoreGPU_Context",
    # Manifold
    "ManifoldCurvature", "ManifoldSector", "TopologicalTensor",
    "GeodesicNavigator", "SelfHealingSubstrate", "PrimeStorageManifold",
    # Unified substrate
    "UnifiedSubstrate", "HardenedUnifiedSubstrate",
]
