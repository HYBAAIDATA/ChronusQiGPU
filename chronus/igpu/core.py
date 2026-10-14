"""Unified iGPU compatibility API backed by Chronos exact primitives."""
from __future__ import annotations
from ..lucas_engine import fibonacci_pair, lucas, nth_prime, zeckendorf_decode, zeckendorf_encode

def fib_pair(n: int): return fibonacci_pair(n)
def fib(n: int): return fibonacci_pair(n)[0]
def cassini(n: int) -> int:
    if n < 1: raise ValueError('Cassini requires n >= 1')
    return fib(n-1) * fib(n+1) - fib(n) * fib(n)
def zeckendorf(n: int):
    mask = zeckendorf_encode(n)
    return mask, tuple(i for i in range(mask.bit_length()-1, -1, -1) if mask & (1 << i))
__all__ = ['fib_pair','fib','lucas','cassini','zeckendorf','zeckendorf_decode','nth_prime']
