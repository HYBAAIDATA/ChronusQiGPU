"""Aethel — the PYTHIA topological storage substrate.

First-class package consolidating the hardened unified substrate (GPU
abstraction + topological storage) and the shared-memory ingestion ABI:

    aethel.cassini        Cassini-Hoggatt invariant verifier
    aethel.zeckendorf     hardened Zeckendorf codec (F_93, full uint64) +
                          SparseTopology payload compression
    aethel.primes         Galois-field prime substrate (MODULUS_Q = 2^61-1)
    aethel.compute        layers 1-5: virtual SMs, SPMD warps, micro-kernels,
                          distributed actors, dependency DAG
    aethel.gpu            TensorCoreGPU_Context pv-lattice projection
    aethel.manifold       PrimeStorageManifold: curvature/sector tensors,
                          geodesic navigation, self-healing
    aethel.unified        UnifiedSubstrate facade across all layers
    aethel.shm            AethelQueue — mmap seqlock slot queue implementing
                          the native mla1517_aethel shared-memory ABI v1
    aethel.fibonacci      exact Fibonacci/Binet index arithmetic + Cassini
                          address-stream primitives
    aethel.encoding       Binet + Zeckendorf payload fold/unfold
    aethel.storage        Fibonacci-indexed AddressSpace + CassiniLedger
    aethel.costs          measured CPU/memory overhead accounting
    aethel.geodesic       handoff adapter into Intelligence.search_crystal
                          (the existing geodesic engine — imported, never
                          reimplemented)

Optional OpenCL punch hosts are injected or resolved lazily; the package
requires only NumPy and never substitutes a storage heuristic for a real
integrity check — every decode is verified against the SHA-256 digest
committed at ingest.

``toe.hardened_unified_substrate`` remains importable as an
identity-preserving alias of ``aethel.hardened_unified_substrate`` —
every toe/Intelligence consumer binds to this package through it.
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
from .costs import (
    OpCost,
    OverheadMeter,
    container_bytes,
    measure_alloc,
    metered,
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
from .shm import (
    AETHEL_ABI_VERSION,
    AETHEL_D10_OFFSET,
    AETHEL_D7_OFFSET,
    AETHEL_HEADER_BYTES,
    AETHEL_MAGIC,
    AETHEL_SLOT_STRIDE,
    STATE_BYTES,
    AethelError,
    AethelQueue,
    AethelRecord,
)
from .errors import (
    AbiVersionMismatch,
    EncodingError,
    EngineUnavailable,
    FoldDomainOverflow,
    GapDetected,
    HandoffRejection,
    InvalidAddress,
    SegmentMissing,
    ZeckendorfInvariantError,
)
from .fibonacci import (
    BinetIndex,
    binet_approx,
    binet_fibonacci,
    cassini_holds,
    cassini_quadruple,
    fibonacci,
    fibonacci_index,
    is_fibonacci,
    lucas,
)
from .encoding import (
    MAX_FOLD_LEN,
    ZeckendorfVector,
    encoding_domain,
    fold,
    unfold,
)
from .geodesic import GeodesicHandoff, ManifoldPoint
from .phi_fold import (
    KernelBoundary,
    NumericFoldState,
    PhiFoldError,
    phi_fold,
    phi_unfold,
    reconstruction_error,
    unfold_partial,
    working_set_ratio,
)
from .phi_memory import (
    IntegrityVerdict,
    MemoryHierarchyError,
    MemoryTier,
    PhiMemoryHierarchy,
    TierResident,
    TopologicalIntegrityGate,
)
from .storage import (
    DEFAULT_MAX_STEP,
    AddressSpace,
    CassiniLedger,
    FibonacciAddress,
    LedgerEntry,
)
from .unified import HardenedUnifiedSubstrate, UnifiedSubstrate
from .overhead import OverheadLedger, price_addresses, price_exact_generator
from .zeckendorf import (
    PUNCH_MANIFOLD_COMPUTE,
    PUNCH_ZECKENDORF_DECODE,
    PUNCH_ZECKENDORF_ENCODE,
    HardenedZeckendorfCodec,
    SparseTopology,
    apply_zeckendorf_compression,
    reverse_zeckendorf_expansion,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
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
    # Overhead ledger — declared cost, not a device measurement
    "OverheadLedger", "price_addresses", "price_exact_generator",
    # Shared-memory ingestion ABI
    "AethelQueue", "AethelRecord", "AethelError",
    "STATE_BYTES", "AETHEL_ABI_VERSION", "AETHEL_MAGIC",
    "AETHEL_HEADER_BYTES", "AETHEL_SLOT_STRIDE",
    "AETHEL_D7_OFFSET", "AETHEL_D10_OFFSET",
    # Contract errors
    "AbiVersionMismatch", "EncodingError", "EngineUnavailable",
    "FoldDomainOverflow", "GapDetected", "HandoffRejection",
    "InvalidAddress", "SegmentMissing", "ZeckendorfInvariantError",
    # Fibonacci/Binet/Cassini address arithmetic
    "BinetIndex", "binet_approx", "binet_fibonacci", "fibonacci",
    "fibonacci_index", "is_fibonacci", "lucas",
    "cassini_quadruple", "cassini_holds",
    # Encoding (Binet + Zeckendorf)
    "ZeckendorfVector", "fold", "unfold",
    "encoding_domain", "MAX_FOLD_LEN",
    # Storage (Fibonacci + Cassini)
    "FibonacciAddress", "LedgerEntry",
    "CassiniLedger", "AddressSpace", "DEFAULT_MAX_STEP",
    # Geodesic handoff (adapter — the engine lives in Intelligence)
    "GeodesicHandoff", "ManifoldPoint",
    # Numeric phi fold + folded memory hierarchy
    "KernelBoundary", "NumericFoldState", "PhiFoldError",
    "phi_fold", "phi_unfold", "unfold_partial",
    "reconstruction_error", "working_set_ratio",
    "MemoryTier", "TierResident", "PhiMemoryHierarchy",
    "TopologicalIntegrityGate", "IntegrityVerdict", "MemoryHierarchyError",
    # Overhead accounting (measured CPU + structural memory)
    "OpCost", "OverheadMeter",
    "container_bytes", "measure_alloc", "metered",
]
