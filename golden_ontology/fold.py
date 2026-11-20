"""Canonical modular Q-fold; no input coercion."""
from collections.abc import Sequence
from .substrate import fib_pair,pisano_period_pow2

class RangeError(ValueError):
    pass

class PeriodError(ValueError):
    pass

def _apply(words,steps,bits,expected_period,inverse):
    if type(bits) is not int or bits<1:
        raise ValueError("width must be a positive integer")
    if type(steps) is not int or steps<0:
        raise ValueError("nonnegative integer steps required")
    if not isinstance(words,Sequence) or isinstance(words,str) or len(words)%2:
        raise ValueError("even word sequence required")
    words=list(words)
    m=1<<bits
    if any(type(v) is not int or not 0<=v<m for v in words):
        raise RangeError("noncanonical unsigned word")
    period=pisano_period_pow2(bits)
    if expected_period is not None and (
        type(expected_period) is not int or expected_period!=period):
        raise PeriodError("incorrect Pisano period")
    n=(-steps if inverse else steps)%period
    f,g=fib_pair(n,m)
    h=(g-f)%m
    if (g*h-f*f)%m!=(-1 if n%2 else 1)%m:
        raise ArithmeticError("Cassini invariant failed")
    return [v for x,y in zip(words[::2],words[1::2])
            for v in ((g*x+f*y)%m,(f*x+h*y)%m)]

def fold_words(words,steps,bits=64,expected_period=None):
    return _apply(words,steps,bits,expected_period,False)

def unfold_words(words,steps,bits=64,expected_period=None):
    return _apply(words,steps,bits,expected_period,True)
