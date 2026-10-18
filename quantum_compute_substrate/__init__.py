"""
HYBA Quantum Titan X-Infinity — φ-Resonance Algebraic Compute Substrate
========================================================================
A general-purpose quantum-mathematical algebraic tensor processing architecture
for the EUCLID computational intelligence system.

This is a hardware-agnostic quantum-mathematical substrate. Quantum content
is defined mathematically and is substrate-invariant; wall-clock is measured
on the current host. Invariant tests certify quantum-mathematical correctness
(Bell/CHSH -> 2*sqrt(2), no-cloning, GHZ Mermin, Sorkin, PR-box). See
docs/THESIS.md, docs/AGI_THESIS.md, and docs/POST_QUANTUM_SUBSTRATE.md.

Qubit dimensionality note: a 4,096-dimensional Hilbert space is equivalent
to approximately 12 qubits (2^12 = 4,096). It does NOT represent 4,096
physical qubits, which would require a 2^4096-dimensional state vector.

All performance figures are MEASURED on the host classical processor.
Architecture targets from the specification are clearly labelled as
mathematical information-density bounds, not achieved hardware performance.

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)
    Research prototype demonstrating quantum algebraic structure on classical
    substrate. No quantum advantage, exascale performance, or capability beyond
    what is measured and tested herein is claimed.

2026 GPU Advances Modelled:
    - FP4/FP6 precision, HBM4 memory, 3nm process node
    - 6th-gen Tensor Cores, 3rd-gen Transformer Engine
    - NVLink 6, Chiplet architecture, PCIe Gen 6
    - 2:4 structured sparsity, Dynamic precision switching
    - MIG partitioning, Confidential computing
    - Co-packaged optics, Tensor Memory
    - Direct-to-chip liquid cooling, Diamond substrate, Liquid helium

Cross-Vendor Analysis (Parts 14-16):
    - Part 14: NVIDIA (Rubin R100, Blackwell B300, Hopper H100)
    - Part 15: Apple Silicon (M5 Ultra, M5 Max)
    - Part 16: HP/HPE (Cray EX4000, Superdome Flex)
"""

__version__ = "0.4.2"

from . import cathedral  # noqa: F401
from . import phi_infinity_tensor  # noqa: F401
from . import pulvini  # noqa: F401

__claim_lane__ = "RESTRICTED"
__status__ = "INTERNAL_RESEARCH_PROTOTYPE"

from .phi_tensor_core import QuantumFoldTensorCore, FoldState, PHI
from .hilbert_space import QuantumComputeState, HilbertSpaceProcessor
from .unitary_transforms import UnitaryHashTransform
from .density_operators import DensityMatrixProcessor
from .natural_gradient import QuantumNaturalGradientOptimizer
from .tensor_networks import MatrixProductStateProcessor
from .amplitude_amplification import AmplitudeAmplificationProcessor
from .quantum_fourier import QuantumFourierProcessor
from .topological_protection import TopologicalProtector
from .quantum_kernel import QuantumKernelProcessor
from .variational_eigensolver import VQEOptimizer
from .grover_search import GroverSearch
from .error_correction import SurfaceCodeQEC
from .quantum_neural_net import QuantumNeuralNetwork, QuantumNeuralLayer
from .compute_engine import ComputeEngine
from .memory_hierarchy import QuantumMemoryHierarchy
from .emergent_time import (
    ClockType,
    EmergentTimeSample,
    ClockMetrologyReport,
    MagneticClock,
    PageWoottersUniverse,
    build_coppo_system,
    FeynmanKitaevHistory,
    RelationalScheduler,
)

# Part 14: NVIDIA advances
from .nvidia_advances import NVIDIAAdvances, NVIDIAGPU

from .gpu_advances_2026 import (
    PrecisionMode,
    PRECISION_THROUGHPUT,
    PRECISION_BITS,
    GPUArchitectureSpec,
    GPUComparisonTable,
    RUBIN_R100,
    BLACKWELL_ULTRA_B300,
    HOPPER_H100,
    HYBA_QUANTUM_TITAN,
    ALL_GPUS,
    FP4Precision,
    SparseTensorCore,
    TransformerEngine,
    NVLink6Interconnect,
    ChipletArchitecture,
    HBM4Memory,
    DynamicPrecisionManager,
    MIGPartitioning,
    ConfidentialComputing,
    OpticalInterconnect,
    TensorMemory,
)

# Part 15: Apple Silicon advances
from .apple_advances import AppleAdvances, AppleSilicon

# Part 16: HP/HPE advances
from .hp_advances import HPAdvances, HPEArchitecture

from .power_cooling import (
    QuantumPowerSystem,
    LiquidHeliumCooling,
    DiamondSubstrateCooling,
    QuantumCryostat,
    DirectToChipLiquidCooling,
)
from .golden_ratio_scaling import (
    GoldenRatioScaler,
    ArchitectureTargets,
    ScaledArchitecture,
    ScalingTier,
    PHI_10,
    PHI_12,
    PHI_15,
    PHI_37,
    phi_power,
    fibonacci,
    phi_power_decomposition,
)
from .benchmark import BenchmarkSuite
from .system import QuantumGPUSystem
from .deployment import QuantumGPUDeployment, PerformanceValidation, PerformanceTargets

# ==================================================================
# v0.3.2 elevation: formal verification, applications, hardware co-
# design, interop, comparative benchmarks.
# ==================================================================
from .formal_properties import (
    check_norm_preservation,
    check_phi_fibonacci_identity,
    check_grover_diffusion_reflection,
    check_fold_unfold_reconstruction,
    run_all_properties,
)
from .benchmarks_comparative import (
    QiskitAdapter,
    CirqAdapter,
    PennyLaneAdapter,
    RigettiAdapter,
    ScalingStudy,
    ComparativeBenchmarks,
)
from .applications import (
    LHCEventClassifier,
    H2VQE,
    AdvectionKernel,
    QuantumSequenceAligner,
)
from .hardware_codesign import (
    FPGAKernelSpec,
    PhiScaledTensorCoreASIC,
    PhotonicPhiFold,
    NeuromorphicHybrid,
)
from .interop import (
    TorchAdapter,
    TensorFlowAdapter,
    MPIAdapter,
    KubernetesManifest,
    EdgeDeployment,
)
