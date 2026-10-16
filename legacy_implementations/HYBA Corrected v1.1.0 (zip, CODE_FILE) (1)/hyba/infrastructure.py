"""
HYBA Infrastructure — Top-Level Integration (Corrected)
All layers unified into a single infrastructure substrate.
"""

from typing import Dict, Any, Optional, List, Union
from python_backend.hyba.core import HYBACore
from python_backend.hyba.memory import HYBAMemory
from python_backend.hyba.storage import HYBAStorage
from python_backend.hyba.compute import HYBACompute


class HYBAInfrastructure:
    """HYBA Infrastructure — The Complete Substrate (Corrected)"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._core = HYBACore()
        self._memory = HYBAMemory(max_primes=self.config.get('max_primes', 10000))
        self._storage = HYBAStorage(block_size=self.config.get('block_size', 512))
        self._compute = HYBACompute()
        self._running = False
        self._initialized = False
        self._metrics = {}

    def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            for n in range(1, 101):
                det = self._core.matrix_det(self._core.matrix_power(n))
                expected = -1 if n % 2 == 1 else 1
                if det != expected:
                    raise RuntimeError(f"Cassini invariant failed at n={n}")

            for n in [0, 1, 10, 50, 100, 500, 1000]:
                if self._core.fibonacci(n) != self._core.binet_f(n):
                    raise RuntimeError(f"Binet exactness failed at n={n}")

            # Verify integrity check rejects impostors
            if self._core.cassini_integrity_check([[0, 1], [1, 4]]):
                raise RuntimeError("Integrity check accepted impostor matrix")

            self._running = True
            self._initialized = True
            return True
        except Exception as e:
            print(f"HYBA initialization failed: {e}")
            self._running = False
            self._initialized = False
            return False

    def process(self, data: Any, operation: str, **kwargs) -> Any:
        if not self._initialized:
            raise RuntimeError("HYBA infrastructure not initialized")

        if operation == 'fold':
            return self._compute.cortex_fold(data)
        elif operation == 'unfold':
            return self._compute.cortex_unfold(data)
        elif operation == 'compress':
            use_fold = kwargs.get('use_fold', False)
            return self._storage.compress(data, use_fold=use_fold)
        elif operation == 'decompress':
            use_fold = kwargs.get('use_fold', False)
            return self._storage.decompress(data, use_fold=use_fold)
        elif operation == 'precision':
            precision = kwargs.get('precision', 1e-6)
            return self._compute.accel_multiplies(precision)
        elif operation == 'memory_allocate':
            size = kwargs.get('size', 1024)
            alignment = kwargs.get('alignment', None)
            return self._memory.allocate(size, alignment)
        elif operation == 'memory_read':
            return self._memory.read(kwargs.get('address'))
        elif operation == 'memory_write':
            self._memory.write(kwargs.get('address'), kwargs.get('value'))
            return True
        elif operation == 'memory_free':
            self._memory.free(kwargs.get('address'))
            return True
        elif operation == 'memory_stats':
            return self._memory.stats()
        elif operation == 'stats':
            return self._metrics
        else:
            raise ValueError(f"Unknown operation: {operation}")

    def metrics(self) -> Dict[str, float]:
        return {
            'memory_capacity': self._memory.stats().get('total_capacity', 0),
            'memory_slots': self._memory.stats().get('allocated_slots', 0),
            'compute_precision': 12,
            'golden_angle': self._compute.get_stats().get('golden_angle_deg', 137.5),
            'lucas_15': self._compute.get_stats().get('lucas_15', 1364),
            'initialized': 1.0 if self._initialized else 0.0,
        }

    def shutdown(self) -> None:
        self._running = False
        self._initialized = False

    def is_running(self) -> bool:
        return self._running

    def is_initialized(self) -> bool:
        return self._initialized
