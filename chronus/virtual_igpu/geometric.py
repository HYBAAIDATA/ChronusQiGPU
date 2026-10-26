"""Exact, bounded grid and upper-half-plane operators for Chronus.

Rational geometry stays rational throughout. Grid kernels use integer NumPy
views and publish ordinary JSON integers. Neither operator decides search
success, ARC answers, consensus, or fleet authority.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping

import numpy as np

D4 = ("identity", "rot90", "rot180", "rot270", "flip_h", "flip_v", "transpose", "anti_transpose")
MAX_SIDE = 256
MAX_RATIONAL_BITS = 4096


def _grid(value: Any) -> np.ndarray:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SIDE:
        raise ValueError("grid must have 1..256 rows")
    if not isinstance(value[0], list) or not 1 <= len(value[0]) <= MAX_SIDE:
        raise ValueError("grid must have 1..256 columns")
    width = len(value[0])
    if any(not isinstance(row, list) or len(row) != width for row in value):
        raise ValueError("grid must be rectangular")
    if any(type(c) is not int or not 0 <= c <= 255 for row in value for c in row):
        raise ValueError("grid cells must be integers in 0..255")
    return np.asarray(value, dtype=np.uint8)


def execute_grid(value: Mapping[str, Any]) -> dict[str, Any]:
    """Execute all eight D4 actions as vector views, or connected components."""
    if set(value) != {"grid", "op"}:
        raise ValueError("grid_geometry requires grid and op")
    grid = _grid(value["grid"])
    op = value["op"]
    if op == "d4":
        transforms = (
            grid,
            np.rot90(grid, -1),
            np.rot90(grid, 2),
            np.rot90(grid),
            grid[:, ::-1],
            grid[::-1, :],
            grid.T,
            grid[::-1, ::-1].T,
        )
        return {
            "transforms": {name: item.tolist() for name, item in zip(D4, transforms)},
            "cells_processed": int(grid.size),
            "arithmetic": "exact_integer",
        }
    if op != "components":
        raise ValueError("grid op must be d4 or components")
    # Four-connected same-colour components; all colours, including zero.
    h, w = grid.shape
    seen: set[tuple[int, int]] = set()
    components = []
    for row in range(h):
        for col in range(w):
            if (row, col) in seen:
                continue
            colour = int(grid[row, col])
            cells, pending = [], [(row, col)]
            seen.add((row, col))
            while pending:
                r, c = pending.pop()
                cells.append([r, c])
                for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                    if (
                        0 <= nr < h
                        and 0 <= nc < w
                        and (nr, nc) not in seen
                        and int(grid[nr, nc]) == colour
                    ):
                        seen.add((nr, nc))
                        pending.append((nr, nc))
            components.append({"colour": colour, "cells": sorted(cells)})
    return {
        "components": components,
        "cells_processed": int(grid.size),
        "arithmetic": "exact_integer",
    }


def verify_grid(value: Mapping[str, Any], output: Mapping[str, Any]) -> list[str]:
    """Independent coordinate oracle for D4; partition/connectivity checks otherwise."""
    if set(value) != {"grid", "op"} or value["op"] not in ("d4", "components"):
        raise ValueError("invalid grid geometry request")
    grid = _grid(value["grid"])
    h, w = grid.shape
    if value["op"] == "d4":
        maps = {
            "identity": (h, w, lambda r, c: (r, c)),
            "rot90": (w, h, lambda r, c: (h - c - 1, r)),
            "rot180": (h, w, lambda r, c: (h - r - 1, w - c - 1)),
            "rot270": (w, h, lambda r, c: (c, w - r - 1)),
            "flip_h": (h, w, lambda r, c: (r, w - c - 1)),
            "flip_v": (h, w, lambda r, c: (h - r - 1, c)),
            "transpose": (w, h, lambda r, c: (c, r)),
            "anti_transpose": (w, h, lambda r, c: (h - c - 1, w - r - 1)),
        }
        expected = {}
        for name, (rows, cols, source) in maps.items():
            expected[name] = [[int(grid[source(r, c)]) for c in range(cols)] for r in range(rows)]
        valid = output == {
            "transforms": expected,
            "cells_processed": h * w,
            "arithmetic": "exact_integer",
        }
        return [] if valid else ["D4 coordinate oracle mismatch"]
    # A separate flood-fill oracle also verifies ordering of component output.
    remaining = {(r, c) for r in range(h) for c in range(w)}
    components = []
    for row in range(h):
        for col in range(w):
            first = (row, col)
            if first not in remaining:
                continue
            colour = int(grid[first])
            group, frontier = {first}, {first}
            remaining.remove(first)
            while frontier:
                adjacent = {
                    (r + dr, c + dc)
                    for r, c in frontier
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
                }
                frontier = {p for p in adjacent & remaining if int(grid[p]) == colour}
                remaining -= frontier
                group |= frontier
            components.append({"colour": colour, "cells": [list(p) for p in sorted(group)]})
    valid = output == {
        "components": components,
        "cells_processed": h * w,
        "arithmetic": "exact_integer",
    }
    return [] if valid else ["component partition oracle mismatch"]


def _rational(value: Any) -> Fraction:
    coordinates = value if isinstance(value, list) else [value]
    if any(type(x) is int and x.bit_length() > MAX_RATIONAL_BITS for x in coordinates):
        raise ValueError("rational coordinate exceeds bit budget")
    if type(value) is int:
        result = Fraction(value)
    elif (
        isinstance(value, list)
        and len(value) == 2
        and all(type(x) is int for x in value)
        and value[1] != 0
    ):
        result = Fraction(*value)
    else:
        raise ValueError("rational coordinates require an integer or [numerator, denominator]")
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > MAX_RATIONAL_BITS:
        raise ValueError("rational coordinate exceeds bit budget")
    return result


def _pair(value: Fraction) -> list[int]:
    _rational([value.numerator, value.denominator])
    return [value.numerator, value.denominator]


def _modular_request(value: Mapping[str, Any]) -> tuple[Fraction, Fraction, list[int]]:
    if set(value) != {"x", "y", "matrix"}:
        raise ValueError("modular_geometry requires x, y and matrix")
    x, y = _rational(value["x"]), _rational(value["y"])
    matrix = value["matrix"]
    if (
        not isinstance(matrix, list)
        or len(matrix) != 4
        or any(type(v) is not int or v.bit_length() > 64 for v in matrix)
    ):
        raise ValueError("matrix requires four signed integers of at most 64 bits")
    a, b, c, d = matrix
    if y <= 0 or a * d - b * c != 1:
        raise ValueError("positive y and determinant-one matrix required")
    return x, y, matrix


def execute_modular(value: Mapping[str, Any]) -> dict[str, Any]:
    """Apply a PSL(2,Z) isometry to z=x+iy, y>0, in exact Q(i).

    The imaginary part identity y' = y / |cz+d|^2 is the upper-half-plane
    metric invariant. No floating-point complex numbers or log evaluation.
    """
    x, y, (a, b, c, d) = _modular_request(value)
    denominator = (c * x + d) ** 2 + (c * y) ** 2
    real = ((a * x + b) * (c * x + d) + a * c * y * y) / denominator
    imag = y / denominator
    return {
        "x": _pair(real),
        "y": _pair(imag),
        "metric_scale": _pair(1 / denominator),
        "arithmetic": "exact_rational",
    }


def verify_modular(value: Mapping[str, Any], output: Mapping[str, Any]) -> list[str]:
    """Check the defining complex cross-product equation and metric factor."""
    x, y, (a, b, c, d) = _modular_request(value)
    if set(output) != {"x", "y", "metric_scale", "arithmetic"}:
        return ["invalid modular geometry output schema"]
    u, v = _rational(output["x"]), _rational(output["y"])
    scale = _rational(output["metric_scale"])
    valid = (
        a * d - b * c == 1
        and y > 0
        and v > 0
        and u * (c * x + d) - v * c * y == a * x + b
        and u * c * y + v * (c * x + d) == a * y
        and v == y * scale
        and output.get("arithmetic") == "exact_rational"
    )
    return [] if valid else ["PSL(2,Z) cross-product/metric invariant mismatch"]
