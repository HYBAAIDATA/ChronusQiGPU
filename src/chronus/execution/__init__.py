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

__all__ = [
    "ExecutionRouter",
    "NativeMathReferenceBackend",
    "execution_router",
    "HardwareAcceleratorDispatcher",
    "SystemVerilogHardwareSimulatorBackend",
    "CUDABackendAdapter",
    "OpenCLAcceleratorBackend",
    "MATHEMATICAL_EXECUTION",
    "SOFTWARE_EXECUTION",
    "PHYSICAL_HARDWARE_EXECUTION",
]
