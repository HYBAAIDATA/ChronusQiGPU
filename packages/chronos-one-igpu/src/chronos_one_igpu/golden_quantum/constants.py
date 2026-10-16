"""Finite numerical configuration; exact integer sequences reuse Chronos."""
import math
from dataclasses import dataclass
from ..lucas_engine import fibonacci_pair, lucas, nth_prime
@dataclass(frozen=True)
class GoldenConstants:
    phi: float = (1 + math.sqrt(5)) / 2
    golden_angle: float = math.pi * (3 - math.sqrt(5))
    @staticmethod
    def fibonacci(n): return fibonacci_pair(n)[0]
    @staticmethod
    def lucas(n): return lucas(n)
    @staticmethod
    def prime(n): return nth_prime(n)
