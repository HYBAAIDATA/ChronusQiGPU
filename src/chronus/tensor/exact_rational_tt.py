"""Bounded exact tensor-train factorisation recovered from the July PULVINI TT contract.

The July artifact's TT-SVD casts complex values to float and truncates small
singular values. This integer/rational-only route instead uses exact rank-one
elimination, so independent reconstruction is equality, not a tolerance check.
No physical compression, accelerator, speedup, or quantum-computation claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from typing import Sequence

MAX_ELEMENTS = 1024
MAX_SITES = 8


def _product(values: Sequence[int]) -> int:
    result = 1
    for value in values:
        result *= value
    return result


def _rational(value: object) -> Fraction:
    if type(value) is int:
        return Fraction(value)
    if type(value) is Fraction:
        return value
    raise TypeError("exact tensor cores accept only integers and rational Fractions")


def _factor(matrix: list[list[Fraction]]) -> tuple[list[list[Fraction]], list[list[Fraction]]]:
    """Pivoted exact rank-one elimination A=U V over Q, including zero rank."""
    height, width = len(matrix), len(matrix[0])
    residual = [row[:] for row in matrix]
    columns: list[list[Fraction]] = []
    rows: list[list[Fraction]] = []
    while True:
        pivot = next(((i, j) for i in range(height) for j in range(width)
                      if residual[i][j] != 0), None)
        if pivot is None:
            break
        i, j = pivot
        denominator = residual[i][j]
        column = [residual[k][j] for k in range(height)]
        row = [v / denominator for v in residual[i]]
        columns.append(column)
        rows.append(row)
        for x in range(height):
            for y in range(width):
                residual[x][y] -= column[x] * row[y]
    rank = len(rows)
    return [[columns[k][i] for k in range(rank)] for i in range(height)], rows


@dataclass(frozen=True)
class ExactRationalTensorTrain:
    """Exact Q-valued TT with immutable source shape and a replayable digest."""

    shape: tuple[int, ...]
    cores: tuple[tuple[tuple[tuple[Fraction, ...], ...], ...], ...]
    digest: str

    @classmethod
    def factor(cls, shape: Sequence[int], values: Sequence[object]) -> "ExactRationalTensorTrain":
        dims = tuple(shape)
        if (not 1 <= len(dims) <= MAX_SITES or
                any(type(n) is not int or n < 1 for n in dims) or
                _product(dims) > MAX_ELEMENTS):
            raise ValueError("tensor dimensions exceed exact reference policy")
        data = tuple(_rational(v) for v in values)
        if len(data) != _product(dims):
            raise ValueError("flat tensor data do not match declared shape")
        cores = []
        previous = 1
        current = list(data)
        for k, dim in enumerate(dims[:-1]):
            columns = _product(dims[k + 1:])
            matrix = [current[i * columns:(i + 1) * columns]
                      for i in range(previous * dim)]
            left, right = _factor(matrix)
            rank = len(right)
            if rank == 0:
                # Zero matrix must still have one bond for exact reconstruction.
                rank = 1
                left = [[Fraction(0)] for _ in range(previous * dim)]
                right = [[Fraction(0)] * columns]
            core = tuple(tuple(tuple(left[l * dim + j][r] for r in range(rank))
                                    for j in range(dim)) for l in range(previous))
            cores.append(core)
            current = [v for row in right for v in row]
            previous = rank
        last = dims[-1]
        final = tuple(tuple((current[l * last + j],) for j in range(last))
                      for l in range(previous))
        cores.append(final)
        result = cls(dims, tuple(cores), "")
        result.verify()
        payload = json.dumps({"shape": dims, "cores": [[[[str(v) for v in bond]
                      for bond in physical] for physical in core] for core in result.cores]},
                      sort_keys=True, separators=(",", ":"))
        return cls(dims, tuple(cores), sha256(payload.encode()).hexdigest())

    def reconstruct(self) -> tuple[Fraction, ...]:
        # Row-major contraction with explicit bond indices, never a dense 2^n statevector.
        partial = [[Fraction(1)]]
        for site in self.cores:
            next_partial = []
            for vector in partial:
                for physical in range(len(site[0])):
                    next_partial.append([sum(vector[l] * site[l][physical][r]
                                             for l in range(len(site)))
                                         for r in range(len(site[0][physical]))])
            partial = next_partial
        if any(len(row) != 1 for row in partial):
            raise ValueError("tensor train has invalid terminal bond")
        return tuple(row[0] for row in partial)

    def verify(self) -> None:
        if len(self.cores) != len(self.shape):
            raise ValueError("tensor train rank/shape mismatch")
        previous = 1
        for dim, core in zip(self.shape, self.cores):
            if len(core) != previous or any(len(part) != dim for part in core):
                raise ValueError("tensor train bond or physical dimension mismatch")
            rank = len(core[0][0])
            if rank == 0 or any(len(site) != rank for part in core for site in part):
                raise ValueError("tensor train ragged right bond")
            if any(type(v) is not Fraction for part in core for site in part for v in site):
                raise TypeError("tensor train core outside exact rational field")
            previous = rank
        if previous != 1:
            raise ValueError("terminal tensor train bond must be one")
        if self.digest:
            payload = json.dumps({"shape": self.shape, "cores": [[[[str(v) for v in bond]
                      for bond in physical] for physical in core] for core in self.cores]},
                      sort_keys=True, separators=(",", ":"))
            if sha256(payload.encode()).hexdigest() != self.digest:
                raise ValueError("tensor train core digest mismatch")

    @property
    def bond_dimensions(self) -> tuple[int, ...]:
        return (1,) + tuple(len(site[0][0]) for site in self.cores)

    @property
    def evidence_class(self) -> str:
        return "EXACT_RATIONAL_SOFTWARE_REFERENCE"
