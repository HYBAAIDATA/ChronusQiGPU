#!/usr/bin/env python3
"""Scale ladder: arithmetic growth and a constant quantum-pass count.

Lucas L(n) grows as phi**n, so an index ladder is a growth test with a
known closed form. Each rung verifies L(n) twice, exactly and without
floats:

    L(n) == F(n-1) + F(n+1)
    L(n)**2 - 5*F(n)**2 == 4 * (-1)**n

The second is the Lucas analogue of Cassini and is the real identity
check. The arithmetic pass and the quantum pass are timed separately so
the two curves stay distinguishable.

Recorded fact, asserted below: the shipped ladder tops out at 53 bits and
never crosses int64. INT64_CROSSING is index 91.

The quantum pass does not evolve a state. `amplitude_updates` is the
declared size of one fixed workload (rows × 2^qubits × iterations). The
timer repeats one XOR per row, so `quantum_ms` stays flat while the
arithmetic index grows. At 11 qubits the count is still a classical
workload size. It is not a measurement of quantum advantage, and it is
not the console check at index 10, which only returns L(10) = 123.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

LOG = logging.getLogger("ladder")

LUCAS_LADDER: tuple[int, ...] = (7, 10, 12, 15, 18, 20, 50, 76)
INT64_LIMIT = 2**63
INT64_CROSSING = 91


def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def lucas(n: int) -> int:
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def verify(n: int) -> int:
    """Exact double identity. Returns L(n); raises if either half fails."""
    value, neighbour = lucas(n), fib(n)
    if value != fib(n - 1) + fib(n + 1):
        raise AssertionError(f"additive identity failed at {n}")
    if value**2 - 5 * neighbour**2 != 4 * (-1) ** n:
        raise AssertionError(f"cassini analogue failed at {n}")
    return value


@dataclass(frozen=True)
class QuantumPass:
    """A fixed quantum workload size. Held constant across the ladder."""

    qubits: int = 11
    iterations: int = 100
    rows: int = 10_000

    @property
    def amplitude_updates(self) -> int:
        return self.rows * (1 << self.qubits) * self.iterations


@dataclass(frozen=True)
class Rung:
    index: int
    value: int
    bits: int
    arithmetic_ms: float
    quantum_ms: float
    crossed_int64: bool


def run(pass_: QuantumPass = QuantumPass()) -> list[Rung]:
    """Measure both passes per rung. The quantum pass is identical each time."""
    rungs: list[Rung] = []
    for index in LUCAS_LADDER:
        start = time.perf_counter()
        value = verify(index)
        arithmetic_ms = (time.perf_counter() - start) * 1e3

        start = time.perf_counter()
        total = 0
        for _ in range(pass_.rows):
            total ^= 1 << (pass_.qubits - 1)
        quantum_ms = (time.perf_counter() - start) * 1e3

        rungs.append(
            Rung(
                index=index,
                value=value,
                bits=value.bit_length(),
                arithmetic_ms=round(arithmetic_ms, 4),
                quantum_ms=round(quantum_ms, 4),
                crossed_int64=value >= INT64_LIMIT,
            )
        )
        del total
    return rungs


def _self_test() -> None:
    assert LUCAS_LADDER == tuple(sorted(LUCAS_LADDER)), "ladder must ascend"
    assert all(verify(n) for n in LUCAS_LADDER)
    assert lucas(10) == 123, "console value"

    span = verify(LUCAS_LADDER[-1]).bit_length() - verify(LUCAS_LADDER[0]).bit_length()
    assert span == 48, f"ladder spans {span} bits, expected 48"

    assert not any(verify(n) >= INT64_LIMIT for n in LUCAS_LADDER), (
        "shipped ladder is under int64; no bigint path is exercised"
    )
    assert verify(INT64_CROSSING - 1) < INT64_LIMIT < verify(INT64_CROSSING)
    assert verify(INT64_CROSSING).bit_length() == 64

    workload = QuantumPass()
    assert workload.amplitude_updates == (
        workload.rows * (1 << workload.qubits) * workload.iterations
    )
    # 10_000 rows × 2^11 amplitudes × 100 iterations.
    assert workload.amplitude_updates == 2_048_000_000
    LOG.info("ladder self test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _self_test()
    for rung in run():
        flag = "  INT64" if rung.crossed_int64 else ""
        print(
            f"L({rung.index:>2}) {rung.bits:>2} bits  "
            f"arith {rung.arithmetic_ms:>8.4f} ms  "
            f"quantum {rung.quantum_ms:>7.3f} ms{flag}"
        )
    for index in (91, 96, 100):
        value = verify(index)
        print(f"L({index}) {value.bit_length()} bits  {value}")
