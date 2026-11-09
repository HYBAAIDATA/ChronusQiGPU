"""Backend-neutral mathematical execution interfaces and acceleration fabric."""

from chronus.execution.hardware_dispatcher import (
    HardwareAcceleratorDispatcher,
    MATHEMATICAL_EXECUTION,
    SOFTWARE_EXECUTION,
    PHYSICAL_HARDWARE_EXECUTION,
)
from chronus.execution.native_simd import (
    NativeSIMDBackendAdapter,
    ResidentConfig,
    ResidentLogicalScheduler,
    dual_space_in_place_query,
    fold_pairs_vectorized,
    unfold_pairs_vectorized,
)
from chronus.execution.reference import (
    ExecutionRouter,
    NativeMathReferenceBackend,
    execution_router,
)
from chronus.execution.systemverilog_backend import (
    SystemVerilogHardwareSimulatorBackend,
)
from chronus.execution.cuda_backend import CUDABackendAdapter
from chronus.execution.opencl_backend import OpenCLAcceleratorBackend
from chronus.execution.opencl_sha256d import OpenCLSha256dMinerBackend
from chronus.execution.geometric_galois_miner import (
    DSW1CycleInstantonCobordism,
    ExactGaloisOracleF257,
    GeometricGaloisMiner,
    GeometricGaloisMinerBackend,
    GeometricMiningResult,
    HodgeSheafLaplacianConsensus,
    LiePoissonRamanujanExpander,
    ZeckendorfBasePhiIndexer,
)
from chronus.execution.master_e2e_engine import (
    F257GaloisOracle,
    MyrmidonSearcher,
    PatroclusGateway,
    StealthEngine,
    StratumMultiPoolServer,
    SystemInvariantContracts,
    build_block_header,
    check_share_difficulty_exact,
    compute_merkle_root,
    execute_master_end_to_end,
    format_extranonce2,
    prevhash_le_to_stratum_hex,
    roll_version,
    swap_endian_words,
)
from chronus.execution.myrmidon_orchestrator import (
    STRATUM_ERROR_CODES,
    PatroclusCharter,
)
from chronus.execution.stealth_orchestrator import (
    PatroclusStealthGateway,
    StealthConfig,
    run_stealth_simulation,
)

__all__ = [
    "ExecutionRouter",
    "NativeMathReferenceBackend",
    "execution_router",
    "HardwareAcceleratorDispatcher",
    "SystemVerilogHardwareSimulatorBackend",
    "CUDABackendAdapter",
    "OpenCLAcceleratorBackend",
    "OpenCLSha256dMinerBackend",
    "GeometricGaloisMiner",
    "GeometricGaloisMinerBackend",
    "GeometricMiningResult",
    "ExactGaloisOracleF257",
    "LiePoissonRamanujanExpander",
    "HodgeSheafLaplacianConsensus",
    "DSW1CycleInstantonCobordism",
    "ZeckendorfBasePhiIndexer",
    "SystemInvariantContracts",
    "PatroclusGateway",
    "MyrmidonSearcher",
    "StealthEngine",
    "StealthConfig",
    "PatroclusStealthGateway",
    "PatroclusCharter",
    "STRATUM_ERROR_CODES",
    "F257GaloisOracle",
    "StratumMultiPoolServer",
    "swap_endian_words",
    "prevhash_le_to_stratum_hex",
    "compute_merkle_root",
    "roll_version",
    "format_extranonce2",
    "build_block_header",
    "check_share_difficulty_exact",
    "execute_master_end_to_end",
    "run_stealth_simulation",
    "MATHEMATICAL_EXECUTION",
    "SOFTWARE_EXECUTION",
    "PHYSICAL_HARDWARE_EXECUTION",
    "NativeSIMDBackendAdapter",
    "ResidentConfig",
    "ResidentLogicalScheduler",
    "fold_pairs_vectorized",
    "unfold_pairs_vectorized",
    "dual_space_in_place_query",
]
