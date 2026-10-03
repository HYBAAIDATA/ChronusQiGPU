"""Aethel — the PYTHIA topological storage substrate.

First-class package consolidating the hardened unified substrate (GPU
abstraction + topological storage) and the shared-memory ingestion ABI:

    aethel.cassini        Cassini-Hoggatt invariant verifier
    aethel.zeckendorf     hardened Zeckendorf codec (F_93, full uint64) +
                          SparseTopology payload compression
    aethel.primes         Galois-field prime substrate (MODULUS_Q = 2^61-1)
    aethel.compute        layers 1-5: virtual SMs, SPMD warps, micro-kernels,
                          distributed actors, dependency DAG
    aethel.gpu            ChronusContext pv-lattice projection
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
    aethel.phyllotaxis    sunflower/Vogel packing (golden angle)
    aethel.ovid           metamorphosis owner — fold = working form
    aethel.theseus        self-healing prime-manifold storage owner
    aethel.triad          Chronus · Theseus · Ovid production façade

Optional OpenCL punch hosts are injected or resolved lazily; the package
requires only NumPy and never substitutes a storage heuristic for a real
integrity check — every decode is verified against the SHA-256 digest
committed at ingest.

``toe.hardened_unified_substrate`` remains importable as an
identity-preserving alias of ``aethel.hardened_unified_substrate`` —
every toe/Intelligence consumer binds to this package through it.

Production owners (elevated names):
    Chronus  — iGPU offering (``chronus`` package / ``aethel.chronus``)
    Theseus  — self-healing prime storage (``aethel.theseus``)
    Ovid     — fold metamorphosis working form (``aethel.ovid``)
"""

import re as _re

from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _metadata_version

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
from .costs import OpCost, OverheadMeter, container_bytes, measure_alloc, metered
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
from .gpu import ChronusContext
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
from .encoding import MAX_FOLD_LEN, ZeckendorfVector, encoding_domain, fold, unfold
from .geodesic import GeodesicHandoff, ManifoldPoint
from .phyllotaxis import (
    GOLDEN_ANGLE,
    PhyllotaxisSite,
    pack_from_anchor,
    pack_indices,
    verify_golden_angle_constant,
    vogel_site,
)
from .ovid import (
    CLAIM_BOUNDARY as OVID_CLAIM_BOUNDARY,
    FoldedWorkingForm,
    Ovid,
    open_ovid,
)
from .theseus import (
    CLAIM_BOUNDARY as THESEUS_CLAIM_BOUNDARY,
    Theseus,
    TheseusError,
    TheseusRecord,
    open_theseus,
)
from .triad import (
    TRIAD_CLAIM_BOUNDARY,
    TRIAD_ID,
    Triad,
    open_triad,
)
from .enterprise_bridge import (
    CapStatus,
    TruthClass,
    emit_envelope,
    open_enterprise_store,
    report as enterprise_capability_report,
)
from .enterprise import (
    AuthenticityError as EnterpriseAuthenticityError,
    AuthorityBoundaryError,
    CompositionRoot,
    ConcurrencyConflict,
    EnterpriseCustody,
    EnterpriseTheseus,
    EvidenceTelemetry,
    Quotas,
    ReadOnlyModeError,
    ResourceExhausted,
    SchemaVersionError,
    UnrecoverableCustodyError,
    assert_cpu_accel_parity,
    compose as compose_enterprise_custody,
    content_digest as enterprise_content_digest,
)
from .phi_fold import (
    KernelBoundary,
    NumericFoldState,
    PartialUnfoldStats,
    PhiFoldError,
    fold_result,
    phi_fold,
    phi_unfold,
    reconstruction_error,
    unfold_partial,
    unfold_partial_with_stats,
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

__version__, __version_source__ = "0.1.0", "source"


def _resolve_version() -> tuple[str, str]:
    canonical = "0.1.0"
    try:
        installed = _metadata_version("aethel")
    except _PackageNotFoundError:
        return canonical, "source_fallback"
    if _re.fullmatch(r"\d+\.\d+\.\d+", installed):
        return installed, "distribution"
    return canonical, "source_fallback"


__version__, __version_source__ = _resolve_version()

# Identity-preserving alias used by toe/Intelligence consumers
hardened_unified_substrate = HardenedUnifiedSubstrate

__all__ = [
    "__version__",
    "DIM", "PHI", "PSI", "SQRT5",
    "LUCAS_15", "LUCAS_20", "LUCAS_31", "MODULUS_Q", "PRIMES_25",
    "CassiniVerifier",
    "HardenedZeckendorfCodec", "SparseTopology",
    "apply_zeckendorf_compression", "reverse_zeckendorf_expansion",
    "PUNCH_ZECKENDORF_ENCODE", "PUNCH_ZECKENDORF_DECODE", "PUNCH_MANIFOLD_COMPUTE",
    "GaloisPrimeSubstrate", "PrimeCell",
    "VirtualSM", "ComputeUnitPool", "VirtualWarp", "SPMDExecutor",
    "OptimizedTensorMicroKernel", "RTCoreMicroKernel", "MicroKernelLibrary",
    "DistributedActor", "CollectiveOps", "DistributedDataflowGraph",
    "DAGNode", "DependencyDAG", "ChronusContext",
    "ManifoldCurvature", "ManifoldSector", "TopologicalTensor",
    "GeodesicNavigator", "SelfHealingSubstrate", "PrimeStorageManifold",
    "UnifiedSubstrate", "HardenedUnifiedSubstrate",
    "OverheadLedger", "price_addresses", "price_exact_generator",
    "AethelQueue", "AethelRecord", "AethelError",
    "STATE_BYTES", "AETHEL_ABI_VERSION", "AETHEL_MAGIC",
    "AETHEL_HEADER_BYTES", "AETHEL_SLOT_STRIDE", "AETHEL_D7_OFFSET", "AETHEL_D10_OFFSET",
    "AbiVersionMismatch", "EncodingError", "EngineUnavailable",
    "FoldDomainOverflow", "GapDetected", "HandoffRejection",
    "InvalidAddress", "SegmentMissing", "ZeckendorfInvariantError",
    "BinetIndex", "binet_approx", "binet_fibonacci", "fibonacci",
    "fibonacci_index", "is_fibonacci", "lucas", "cassini_quadruple", "cassini_holds",
    "ZeckendorfVector", "fold", "unfold", "encoding_domain", "MAX_FOLD_LEN",
    "FibonacciAddress", "LedgerEntry", "CassiniLedger", "AddressSpace", "DEFAULT_MAX_STEP",
    "GeodesicHandoff", "ManifoldPoint",
    "KernelBoundary", "NumericFoldState", "PartialUnfoldStats", "PhiFoldError",
    "phi_fold", "phi_unfold", "unfold_partial", "unfold_partial_with_stats", "fold_result",
    "reconstruction_error", "working_set_ratio",
    "MemoryTier", "TierResident", "PhiMemoryHierarchy",
    "TopologicalIntegrityGate", "IntegrityVerdict", "MemoryHierarchyError",
    "OpCost", "OverheadMeter", "container_bytes", "measure_alloc", "metered",
    # Chronus · Theseus · Ovid triad
    "GOLDEN_ANGLE",
    "PhyllotaxisSite",
    "vogel_site",
    "pack_indices",
    "pack_from_anchor",
    "verify_golden_angle_constant",
    "Ovid",
    "FoldedWorkingForm",
    "open_ovid",
    "OVID_CLAIM_BOUNDARY",
    "Theseus",
    "TheseusRecord",
    "TheseusError",
    "open_theseus",
    "THESEUS_CLAIM_BOUNDARY",
    "Triad",
    "open_triad",
    "TRIAD_ID",
    "TRIAD_CLAIM_BOUNDARY",
    # Enterprise bridge (Rule 7)
    "CapStatus",
    "TruthClass",
    "emit_envelope",
    "open_enterprise_store",
    "enterprise_capability_report",
    # Enterprise custody substrate (single-root software; not hyperscaler)
    "EnterpriseCustody",
    "EnterpriseTheseus",
    "CompositionRoot",
    "compose_enterprise_custody",
    "AuthorityBoundaryError",
    "UnrecoverableCustodyError",
    "ResourceExhausted",
    "ConcurrencyConflict",
    "SchemaVersionError",
    "EnterpriseAuthenticityError",
    "ReadOnlyModeError",
    "Quotas",
    "EvidenceTelemetry",
    "assert_cpu_accel_parity",
    "enterprise_content_digest",
]
