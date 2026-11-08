"""Backend-neutral mathematical execution interfaces and acceleration fabric."""

from chronus.execution.hardware_dispatcher import (
    HardwareAcceleratorDispatcher,
    MATHEMATICAL_EXECUTION,
    SOFTWARE_EXECUTION,
    PHYSICAL_HARDWARE_EXECUTION,
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
    "MATHEMATICAL_EXECUTION",
    "SOFTWARE_EXECUTION",
    "PHYSICAL_HARDWARE_EXECUTION",
]
