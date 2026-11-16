"""OpenCL iGPU SHA-256d nonce-search adapter.

Executes the sha256d_search kernel (src/chronus/kernels/sha256d_search.cl) on
any OpenCL device — integrated or discrete GPU — discovered via pyopencl.
The host precomputes the header midstate with the exact unrolled engine
(chronus.execution.asic_sha256.sha256_block), so the kernel and the CPU
reference are bit-identical by construction.

Availability is opt-in: set CHRONUS_ENABLE_OPENCL_MINER=1 on hosts with an
OpenCL-capable iGPU. Without the flag, a device, or pyopencl, the adapter
reports unavailable and raises HardwareUnavailableError on execute.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

from chronus.backends.lattice import HardwareUnavailableError
from chronus.execution.asic_sha256 import _H0, sha256_block
from chronus.execution.hashrate_cap import process_cap

_KERNEL_PATH = Path(__file__).resolve().parent.parent / "kernels" / "sha256d_search.cl"
_MAX_REPORTED = 64


class OpenCLSha256dMinerBackend:
    """iGPU/GPU SHA-256d nonce-search backend over OpenCL."""

    name = "opencl-igpu-sha256d-miner"
    execution_mode = "PHYSICAL_HARDWARE_EXECUTION"
    runtime_classification = "PHYSICAL_HARDWARE_EXECUTION"
    supported_workloads = frozenset({"SHA256D_NONCE_SEARCH"})

    def __init__(
        self,
        platform_index: int = 0,
        device_index: int = 0,
        max_reported: int = _MAX_REPORTED,
    ) -> None:
        self.platform_index = platform_index
        self.device_index = device_index
        self.max_reported = max_reported
        self._ctx = None
        self._queue = None
        self._program = None
        self._device_info: Dict[str, Any] = {}
        self._last_span = 0
        self._available = self._probe()

    def _probe(self) -> bool:
        """Discover an OpenCL device and compile the search kernel."""
        if os.getenv("CHRONUS_ENABLE_OPENCL_MINER", "0") != "1":
            return False
        try:
            import pyopencl as cl
        except ImportError:
            return False
        try:
            platform = cl.get_platforms()[self.platform_index]
            device = platform.get_devices()[self.device_index]
            self._ctx = cl.Context([device])
            self._queue = cl.CommandQueue(self._ctx)
            self._program = cl.Program(self._ctx, _KERNEL_PATH.read_text()).build()
            self._device_info = {
                "device_name": device.name.strip(),
                "device_type": cl.device_type.to_string(device.type),
                "compute_units": device.max_compute_units,
                "max_work_group_size": device.max_work_group_size,
                "global_memory_bytes": device.global_mem_size,
            }
            return True
        except Exception:
            self._ctx = None
            self._queue = None
            self._program = None
            return False

    def is_available(self) -> bool:
        return self._available

    def supports(self, workload_type: str) -> bool:
        return self._available and workload_type in self.supported_workloads

    def get_queue_status(self) -> Dict[str, Any]:
        return {
            "available": self._available,
            "device": self._device_info or None,
            "kernel": _KERNEL_PATH.name,
        }

    @staticmethod
    def build_kernel_args(header: bytes, target: int, base_nonce: int):
        """Split an 80-byte header into midstate + tail words for the kernel.

        Shared with tests so the CPU reference and the GPU kernel consume
        identical preprocessed inputs.
        """
        if not isinstance(header, bytes) or len(header) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if not 0 <= target < 1 << 256:
            raise ValueError("target must be an unsigned 256-bit integer")
        if not 0 <= base_nonce < 1 << 32:
            raise ValueError("base_nonce must be a 32-bit unsigned integer")
        midstate = sha256_block(_H0, header[:64])
        tail = [
            int.from_bytes(header[64 + 4 * i : 68 + 4 * i], "big") for i in range(3)
        ]
        target_words = [(target >> (32 * i)) & 0xFFFFFFFF for i in range(8)]
        return midstate, tail, target_words

    def search(self, header: bytes, start: int, stop: int, target: int) -> List[int]:
        """Search [start, stop) on the OpenCL device; return matching nonces."""
        if not self._available:
            raise HardwareUnavailableError(
                "OpenCL iGPU miner is not available; set "
                "CHRONUS_ENABLE_OPENCL_MINER=1 on a host with an OpenCL device"
            )
        if not 0 <= start <= stop <= 1 << 32:
            raise ValueError("nonce range must be within [0, 2**32]")
        midstate, tail, target_words = self.build_kernel_args(header, target, start)

        import pyopencl as cl

        width = process_cap().allow(stop - start)
        self._last_span = width
        if width == 0:
            return []
        stop = start + width

        found = cl.Buffer(
            self._ctx, cl.mem_flags.WRITE_ONLY, size=4 * self.max_reported
        )
        count_host = bytearray(4)
        count = cl.Buffer(
            self._ctx,
            cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=bytes(count_host),
        )

        kernel = self._program.sha256d_search
        kernel.set_args(
            *[cl.cltypes.uint(v) for v in midstate],
            *[cl.cltypes.uint(v) for v in tail],
            cl.cltypes.uint(start),
            *[cl.cltypes.uint(v) for v in target_words],
            found,
            count,
            cl.cltypes.uint(self.max_reported),
        )
        cl.enqueue_nd_range_kernel(self._queue, kernel, (width,), None).wait()

        import numpy as np

        count_buf = np.zeros(1, dtype=np.uint32)
        cl.enqueue_copy(self._queue, count_buf, count).wait()
        hit_count = min(int(count_buf[0]), self.max_reported)
        if hit_count == 0:
            return []
        result_buf = np.zeros(hit_count, dtype=np.uint32)
        cl.enqueue_copy(self._queue, result_buf, found).wait()
        return sorted(int(n) for n in result_buf)

    def execute(self, payload: bytes, workload_type: str) -> Dict[str, Any]:
        """Dispatcher entry point: payload is the 80-byte header."""
        if workload_type not in self.supported_workloads:
            raise ValueError(f"Backend does not support {workload_type}")
        matches = self.search(payload, 0, 1 << 32, target=(1 << 256) - 1)
        return {
            "execution_mode": self.execution_mode,
            "runtime_classification": self.runtime_classification,
            "backend": self.name,
            "device": self._device_info,
            "tested": self._last_span,
            "match_count": len(matches),
            "matches": matches,
        }
