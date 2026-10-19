"""
HYBA Memory — φ-Scaled Memory Substrate (Corrected)

Bug 4 fix: Allocation uses gap >= size (not gap² >= size).
This ensures offset = gap - size >= 0 (no buffer underflow).
"""

from typing import Dict, Any, Optional, List
import math


class HYBAMemory:
    """
    HYBA Memory Substrate (Corrected)

    Provides:
    - Prime-gap addressing (infinite address space)
    - Lucas-scaled register allocation
    - Golden-angle cache layout
    """

    def __init__(self, max_primes: int = 10000):
        self.max_primes = max_primes
        self._primes = self._sieve(max_primes)
        self._gaps = [self._primes[i+1] - self._primes[i]
                      for i in range(len(self._primes)-1)]
        self._memory: Dict[int, Any] = {}
        self._allocated: Dict[int, int] = {}
        self._phi = (1 + math.sqrt(5)) / 2

    def _sieve(self, limit: int) -> List[int]:
        if limit < 2:
            return []
        sieve = [True] * (limit + 1)
        sieve[0] = sieve[1] = False
        for i in range(2, int(limit ** 0.5) + 1):
            if sieve[i]:
                for j in range(i * i, limit + 1, i):
                    sieve[j] = False
        return [i for i in range(limit + 1) if sieve[i]]

    def _golden_address(self, index: int) -> float:
        return (index * (1 - 1 / self._phi)) % 1.0

    def _lucas_scale(self, index: int) -> int:
        from python_backend.hyba.core import HYBACore
        core = HYBACore()
        return core.lucas(index % 20 + 1)

    def allocate(self, size: int, alignment: Optional[int] = None) -> int:
        """
        Allocate memory using Lucas-scaled prime-gap addressing.
        CORRECTED: Uses gap >= size instead of gap² >= size.

        Bug 4 fix: The original gap² capacity check allowed gap=5, size=10
        (25 >= 10) but produced offset = gap - size = -5 (underflow).
        Now: allocation only accepted when gap >= size, ensuring offset >= 0.
        """
        if size <= 0:
            raise ValueError("Allocation size must be positive")

        for i, gap in enumerate(self._gaps):
            # Bug 4 fix: gap >= size (not gap² >= size)
            if gap >= size:
                address = self._primes[i]
                lucas_scale = self._lucas_scale(i)
                offset = int(self._golden_address(address) * (gap - size))
                # offset is now guaranteed >= 0 since gap >= size
                if alignment:
                    offset = (offset // alignment) * alignment
                final_address = address + offset
                self._allocated[final_address] = size
                return final_address

        raise MemoryError(f"No available prime gap of sufficient size for {size} bytes")

    def read(self, address: int) -> Optional[Any]:
        return self._memory.get(address, None)

    def write(self, address: int, value: Any) -> None:
        if address not in self._allocated:
            raise KeyError(f"Address {address} not allocated")
        self._memory[address] = value

    def free(self, address: int) -> None:
        if address in self._allocated:
            del self._allocated[address]
        if address in self._memory:
            del self._memory[address]

    def stats(self) -> Dict[str, Any]:
        return {
            'total_primes': len(self._primes),
            'total_gaps': len(self._gaps),
            'allocated_slots': len(self._allocated),
            'memory_entries': len(self._memory),
            'total_capacity': sum(g for g in self._gaps[:100]),  # Bug 4 fix: sum of gaps, not gap²
        }

    def is_allocated(self, address: int) -> bool:
        return address in self._allocated
