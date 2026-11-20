"""Original exact Cassini partition and L_76 Hendrix stride, sharing installed Fibonacci arithmetic."""
import math
from dataclasses import dataclass
from typing import Iterator, List, Tuple
from chronus.geodesic.scheduler import exact_fibonacci_lucas


def fibonacci(n):
    return exact_fibonacci_lucas(n)[0]


def hendrix_stride(window):
    if type(window) is not int or window < 1:
        raise ValueError("positive integer window required")
    stride = exact_fibonacci_lucas(76)[1] % window or 1
    while math.gcd(stride, window) != 1:
        stride = (stride + 1) % window or 1
    return stride


@dataclass(frozen=True)
class Interval:
    start: int
    stop: int

    @property
    def size(self) -> int:
        return self.stop - self.start


@dataclass(frozen=True)
class CassiniSchedule:
    width: int
    stride: int
    origin: int
    cassini_order: int
    cassini_determinant: int

    def __len__(self) -> int:
        return self.width

    def offset_at(self, position: int) -> int:
        if type(position) is not int:
            raise ValueError("integer schedule position required")
        if position < 0 or position >= self.width:
            raise IndexError("schedule position out of range")
        return (self.origin + position * self.stride) % self.width

    def __iter__(self) -> Iterator[int]:
        for position in range(self.width):
            yield self.offset_at(position)


def partition_interval(start: int, size: int, partitions: int = 32) -> Tuple[Interval, ...]:
    """Partition ``[start, start + size)`` without gaps or overlap."""

    if start < 0 or size < 0:
        raise ValueError("start and size must be non-negative")
    if partitions < 1:
        raise ValueError("partitions must be positive")
    quotient, remainder = divmod(size, partitions)
    cursor = start
    result: List[Interval] = []
    for index in range(partitions):
        width = quotient + (1 if index < remainder else 0)
        result.append(Interval(cursor, cursor + width))
        cursor += width
    if cursor != start + size:
        raise ArithmeticError("partition coverage invariant failed")
    return tuple(result)


def cassini_permutation(width: int, face_id: int, seed: int) -> CassiniSchedule:
    """Return a coverage-complete affine permutation of one shard.

    The Fibonacci companion matrix at ``order`` supplies a Cassini determinant
    of +/-1.  Its adjacent limbs seed an affine stride; the stride is advanced
    until coprime to the shard width, which is the exact condition for a full
    permutation modulo ``width``.
    """

    if width < 1:
        raise ValueError("width must be positive")
    if face_id < 0:
        raise ValueError("face_id must be non-negative")
    order = face_id + 2
    determinant = (
        fibonacci(order + 1) * fibonacci(order - 1)
        - fibonacci(order) ** 2
    )
    if determinant not in (-1, 1):
        raise ArithmeticError("Cassini determinant is not unimodular")

    stride = (fibonacci(order + 1) + fibonacci(order)) % width
    stride = stride or 1
    while math.gcd(stride, width) != 1:
        stride = (stride + 1) % width
        stride = stride or 1
    origin = (int(seed) + fibonacci(order)) % width
    return CassiniSchedule(width, stride, origin, order, determinant)


