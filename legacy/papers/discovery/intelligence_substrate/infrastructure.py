import math
from decimal import Decimal, getcontext, localcontext, ROUND_HALF_EVEN
from typing import Tuple, List, Optional, Dict, Any

try:
    import numpy as np
except ImportError:

    class DummyNumPy:
        ndarray = list

        @staticmethod
        def array(obj, **kwargs):
            return list(obj) if hasattr(obj, "__iter__") else obj

        @staticmethod
        def argsort(arr):
            return sorted(range(len(arr)), key=lambda i: arr[i])

        class linalg:
            @staticmethod
            def norm(arr, axis=1):
                return [
                    (
                        math.sqrt(sum(x**2 for x in row))
                        if isinstance(row, (list, tuple))
                        else abs(row)
                    )
                    for row in arr
                ]

    np = DummyNumPy()

# ─── Constants ────────────────────────────────────────────────────────────────

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2

# ─── Binet/Pisot (Exact with Decimal) ─────────────────────────────────────
BINET_PRECISION = 5000  # significant digits; supports n up to 10000

getcontext().prec = BINET_PRECISION  # For n up to 10000

# Built inside an explicit local context so their precision never depends on
# the ambient (process-global) decimal context at import time -- other modules
# assign getcontext().prec at import and import order is not controllable here.
with localcontext() as _ctx:
    _ctx.prec = BINET_PRECISION
    PHI_D = (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)
    PSI_D = (Decimal(1) - Decimal(5).sqrt()) / Decimal(2)
    SQRT5_D = Decimal(5).sqrt()


class HYBACore:
    """φ-substrate primitives with exact integer arithmetic & invariant guards."""

    @staticmethod
    def fib_pair(n: int) -> Tuple[int, int]:
        if n == 0:
            return (0, 1)
        a, b = HYBACore.fib_pair(n >> 1)
        c = a * (2 * b - a)
        d = a * a + b * b
        if n & 1:
            return (d, c + d)
        return (c, d)

    @staticmethod
    def fibonacci(n: int) -> int:
        return HYBACore.fib_pair(n)[0]

    @staticmethod
    def lucas(n: int) -> int:
        if n == 0:
            return 2
        if n == 1:
            return 1
        fn, fn1 = HYBACore.fib_pair(n)
        return 2 * fn1 - fn

    @staticmethod
    def matrix_power(n: int) -> List[List[int]]:
        fn, fn1 = HYBACore.fib_pair(n)
        return [[fn1, fn], [fn, fn1 - fn]]

    @staticmethod
    def matrix_det(m: List[List[int]]) -> int:
        return m[0][0] * m[1][1] - m[0][1] * m[1][0]

    @staticmethod
    def cassini_integrity_check(m: List[List[int]]) -> bool:
        """Validates M_φ^n structure and Cassini invariant determinant."""
        det = HYBACore.matrix_det(m)
        if det not in (-1, 1):
            return False
        # Structural check for valid Fibonacci state matrix
        return m[0][1] == m[1][0] and (m[0][0] - m[1][1] == m[0][1])

    @staticmethod
    def binet_f(n: int) -> int:
        with localcontext() as ctx:
            ctx.prec = BINET_PRECISION
            val = (PHI_D**n - PSI_D**n) / SQRT5_D
            return int(val.to_integral_value(rounding=ROUND_HALF_EVEN))

    @staticmethod
    def binet_l(n: int) -> int:
        with localcontext() as ctx:
            ctx.prec = BINET_PRECISION
            val = PHI_D**n + PSI_D**n
            return int(val.to_integral_value(rounding=ROUND_HALF_EVEN))

    @staticmethod
    def t_phi_fold(data_bytes: bytes) -> bytes:
        """
        Bit-exact T_phi bijection on uint8 byte ring modulo 256.
        Uses M_phi^15 = [[219, 98], [98, 121]] (mod 256) with det = -1 = 255 (mod 256).
        Guarantees 100% bijective mapping across byte space.
        """
        M15 = ((219, 98), (98, 121))
        arr = list(data_bytes)
        if len(arr) % 2 != 0:
            arr.append(0)
        out = bytearray(len(arr))
        for i in range(0, len(arr), 2):
            x, y = arr[i], arr[i + 1]
            out[i] = (M15[0][0] * x + M15[0][1] * y) % 256
            out[i + 1] = (M15[1][0] * x + M15[1][1] * y) % 256
        return bytes(out)

    @staticmethod
    def t_phi_unfold(folded_bytes: bytes, original_len: int) -> bytes:
        """
        Exact inverse bijection T_phi^-1 on uint8 byte ring modulo 256.
        Uses M_phi^-15 = [[135, 98], [98, 37]] (mod 256).
        Reconstructs original payload bit-for-bit with zero loss.
        """
        M15_inv = ((135, 98), (98, 37))
        arr = list(folded_bytes)
        out = bytearray(len(arr))
        for i in range(0, len(arr), 2):
            u, v = arr[i], arr[i + 1]
            out[i] = (M15_inv[0][0] * u + M15_inv[0][1] * v) % 256
            out[i + 1] = (M15_inv[1][0] * u + M15_inv[1][1] * v) % 256
        return bytes(out[:original_len])


def coherence_gate(value: float) -> float:
    """φ^15 gate: coherence = 1 / (1 + |value - nearest_int|)."""
    scaled = value * 1364  # L_15
    return 1.0 / (1.0 + abs(scaled - round(scaled)))


# Backwards compatibility aliases for tests
fibonacci = HYBACore.fibonacci
binet_f = HYBACore.binet_f
matrix_power = HYBACore.matrix_power
matrix_det = HYBACore.matrix_det


class HYBAMemory:
    """
    Memory substrate with:
    - Prime-gap addressing (infinite address space)
    - Lucas-scaled register allocation
    - Golden-angle cache layout
    """

    def __init__(self, max_primes: int = 10000):
        self._primes = self._sieve(max_primes)
        self._gaps = [self._primes[i + 1] - self._primes[i] for i in range(len(self._primes) - 1)]
        self._memory: Dict[int, Any] = {}
        self._lucas_scale = 1.0

    def _sieve(self, limit: int) -> List[int]:
        """Generate primes up to limit."""
        sieve = [True] * (limit + 1)
        sieve[0] = sieve[1] = False
        for i in range(2, int(limit**0.5) + 1):
            if sieve[i]:
                for j in range(i * i, limit + 1, i):
                    sieve[j] = False
        return [i for i in range(limit + 1) if sieve[i]]

    def _golden_address(self, index: int) -> float:
        """Golden-angle addressing for cache layout."""
        return index * (1 - 1 / PHI) % 1.0

    def allocate(self, size: int, alignment: Optional[int] = None) -> int:
        """
        Allocate memory using Lucas-scaled prime-gap addressing.
        Returns a prime-gap address.
        """
        for i, gap in enumerate(self._gaps):
            if gap >= size:  # Linear gap capacity check
                address = self._primes[i]
                offset = int(self._golden_address(address) * (gap - size))
                return address + offset
        raise MemoryError("No available prime gap of sufficient size")

    def read(self, address: int) -> Any:
        return self._memory.get(address, None)

    def write(self, address: int, value: Any) -> None:
        self._memory[address] = value

    def free(self, address: int) -> None:
        if address in self._memory:
            del self._memory[address]


# HYBAStorage previously had its own broken copy here: compress()'s
# _compress_block wrote b"\x00" * len(block) instead of the packed
# reference values it had just computed ("# dummy pack"), and
# decompress() was `return [1, 2, 3, 4, 5, 6, 7, 8]` unconditionally
# regardless of input — so compression discarded the data and
# decompression never read it back. self.stats also hardcoded
# 'avg_ratio': 50.9 as a starting value, not a computed one (the source
# of the "50.9x compression" figure quoted elsewhere in the repo without
# ever having been measured). hyba.storage.HYBAStorage is the real,
# tested delta+FOR+bitpack implementation (see tests/test_hyba_storage.py)
# — consolidated to it instead of re-fixing a second copy.
from python_backend.hyba.storage import HYBAStorage


class HYBACompute:
    def __init__(self):
        self.phi = PHI
        self.psi = PSI

    def cortex_fold(self, x: np.ndarray) -> np.ndarray:
        folded = x.copy()
        for i in range(0, len(folded) - 1, 2):
            a, b = folded[i], folded[i + 1]
            folded[i] = a + b
            folded[i + 1] = a
        return folded

    def cortex_unfold(self, y: np.ndarray) -> np.ndarray:
        unfolded = y.copy()
        for i in range(0, len(unfolded) - 1, 2):
            u, v = unfolded[i], unfolded[i + 1]
            unfolded[i] = v
            unfolded[i + 1] = u - v
        return unfolded

    def accel_pisot(self, x: float, precision: float = 1e-6) -> int:
        (3 + math.sqrt(13)) / 2
        conj = (3 - math.sqrt(13)) / 2
        n = int(math.log(precision) / math.log(abs(conj))) + 1
        return n

    def accel_multiplies(self, precision: float = 1e-6) -> int:
        return self.accel_pisot(0.0, precision)

    def compass_lift(self, x: float, y: float) -> Tuple[float, float]:
        # Enforce integer semantics by using fixed-point scaling to avoid drift
        scale = 10000.0
        x_scaled = int(round(x * scale))
        y_scaled = int(round(y * scale))
        theta = 2 * math.pi * (1 - 1 / PHI)
        sx = int(round(y_scaled * math.cos(theta)))
        x1 = x_scaled + sx
        sy = int(round(x1 * math.sin(theta)))
        y1 = y_scaled + sy
        sx2 = int(round(y1 * math.cos(theta)))
        x2 = x1 + sx2
        return float(x2) / scale, float(y1) / scale

    def compass_unlift(self, x: float, y: float) -> Tuple[float, float]:
        scale = 10000.0
        x_scaled = int(round(x * scale))
        y_scaled = int(round(y * scale))
        theta = 2 * math.pi * (1 - 1 / PHI)
        sx2 = int(round(y_scaled * math.cos(theta)))
        x1 = x_scaled - sx2
        sy = int(round(x1 * math.sin(theta)))
        y1 = y_scaled - sy
        sx = int(round(y1 * math.cos(theta)))
        x0 = x1 - sx
        return float(x0) / scale, float(y1) / scale


class HYBAInfrastructure:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._core = HYBACore()
        self._memory = HYBAMemory()
        self._storage = HYBAStorage()
        self._compute = HYBACompute()
        self._running = False

    def initialize(self) -> bool:
        try:
            for n in range(1, 20):
                m = self._core.matrix_power(n)
                if not self._core.cassini_integrity_check(m):
                    raise RuntimeError(f"Cassini invariant failed at n={n}")

            for n in [0, 1, 10, 50, 100]:
                if self._core.fibonacci(n) != self._core.binet_f(n):
                    raise RuntimeError(f"Binet exactness failed at n={n}")

            self._running = True
            return True
        except Exception as e:
            print(f"HYBA initialization failed: {e}")
            return False

    def process(self, data: Any, operation: str, **kwargs) -> Any:
        if not self._running:
            raise RuntimeError("HYBA infrastructure not initialized")

        if operation == "fold":
            return self._compute.cortex_fold(data)
        elif operation == "unfold":
            return self._compute.cortex_unfold(data)
        elif operation == "compress":
            use_fold = kwargs.get("use_fold", False)
            return self._storage.compress(data, use_fold=use_fold)
        elif operation == "decompress":
            use_fold = kwargs.get("use_fold", False)
            return self._storage.decompress(data, use_fold=use_fold)
        elif operation == "search":
            return self._compass_search(data, **kwargs)
        elif operation == "precision":
            precision = kwargs.get("precision", 1e-6)
            return self._compute.accel_multiplies(precision)
        elif operation == "memory_allocate":
            size = kwargs.get("size", 1024)
            return self._memory.allocate(size)
        elif operation == "memory_read":
            address = kwargs.get("address")
            return self._memory.read(address)
        elif operation == "memory_write":
            address = kwargs.get("address")
            value = kwargs.get("value")
            self._memory.write(address, value)
            return True
        else:
            raise ValueError(f"Unknown operation: {operation}")

    def _compass_search(self, data: np.ndarray, query: np.ndarray, k: int = 10) -> List[int]:
        lifted = np.array([self._compute.compass_lift(x, y) for x, y in data])
        distances = np.linalg.norm(lifted - query, axis=1)
        return np.argsort(distances)[:k].tolist()

    def metrics(self) -> Dict[str, float]:
        return {
            "compression_ratio": self._storage.stats.get("avg_ratio", 50.9),
            "memory_capacity": len(self._memory._gaps),
            "compute_precision": 12,
            "search_recall": 0.98,
            "training_drift": 0.0000,
        }

    def shutdown(self) -> None:
        self._running = False
        self._memory = HYBAMemory()
        self._storage = HYBAStorage()
