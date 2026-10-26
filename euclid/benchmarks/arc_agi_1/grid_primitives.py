"""Generic grid operator vocabulary for the ARC-AGI-1 task world.

These are *operators*, not solutions. Each one is a task-agnostic,
deterministic grid transformation (geometry, cropping, scaling, tiling,
object selection, gravity, colour mapping). None of them inspects a task
identifier, a filename or a withheld test output. EUCLID's IntegratedAgent
decides which operators to compose and in what order; the world only executes
the programme it is given.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable, Sequence

Grid = list[list[int]]
MAX_SIDE = 30


class OperatorFailed(ValueError):
    """The operator is not defined on this grid."""


def _check(grid: Grid) -> Grid:
    if not grid or not grid[0]:
        raise OperatorFailed("empty grid")
    if len(grid) > MAX_SIDE or len(grid[0]) > MAX_SIDE:
        raise OperatorFailed("grid exceeds 30x30")
    return grid


def background(grid: Grid) -> int:
    """Most frequent colour (ties -> lowest colour)."""
    counts = Counter(c for row in grid for c in row)
    return min(counts, key=lambda c: (-counts[c], c))


def _bbox(grid: Grid, bg: int) -> tuple[int, int, int, int]:
    cells = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != bg]
    if not cells:
        raise OperatorFailed("no foreground")
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return min(rows), max(rows), min(cols), max(cols)


def _components(grid: Grid, bg: int) -> list[list[tuple[int, int]]]:
    """4-connected same-colour foreground components."""
    h, w = len(grid), len(grid[0])
    seen = [[False] * w for _ in range(h)]
    out: list[list[tuple[int, int]]] = []
    for r in range(h):
        for c in range(w):
            if seen[r][c] or grid[r][c] == bg:
                continue
            colour = grid[r][c]
            stack, comp = [(r, c)], []
            seen[r][c] = True
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny][nx] and grid[ny][nx] == colour:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            out.append(comp)
    return out


def _crop_cells(grid: Grid, cells: Sequence[tuple[int, int]], bg: int) -> Grid:
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    keep = set(cells)
    return [[grid[r][c] if (r, c) in keep else bg for c in range(c0, c1 + 1)]
            for r in range(r0, r1 + 1)]


# Geometry
def rot90(g: Grid) -> Grid:
    return [list(row) for row in zip(*g[::-1])]


def rot180(g: Grid) -> Grid:
    return [row[::-1] for row in g[::-1]]


def rot270(g: Grid) -> Grid:
    return [list(row) for row in zip(*g)][::-1]


def flip_h(g: Grid) -> Grid:
    return [row[::-1] for row in g]


def flip_v(g: Grid) -> Grid:
    return [list(row) for row in g[::-1]]


def transpose(g: Grid) -> Grid:
    return [list(row) for row in zip(*g)]


# Cropping
def crop_content(g: Grid) -> Grid:
    bg = background(g)
    r0, r1, c0, c1 = _bbox(g, bg)
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def largest_object(g: Grid) -> Grid:
    bg = background(g)
    comps = _components(g, bg)
    if not comps:
        raise OperatorFailed("no objects")
    return _crop_cells(g, max(comps, key=len), bg)


def smallest_object(g: Grid) -> Grid:
    bg = background(g)
    comps = _components(g, bg)
    if not comps:
        raise OperatorFailed("no objects")
    return _crop_cells(g, min(comps, key=len), bg)


def top_half(g: Grid) -> Grid:
    if len(g) < 2:
        raise OperatorFailed("too short")
    return [list(r) for r in g[: len(g) // 2]]


def bottom_half(g: Grid) -> Grid:
    if len(g) < 2:
        raise OperatorFailed("too short")
    return [list(r) for r in g[(len(g) + 1) // 2:]]


def left_half(g: Grid) -> Grid:
    if len(g[0]) < 2:
        raise OperatorFailed("too narrow")
    return [r[: len(r) // 2] for r in g]


def right_half(g: Grid) -> Grid:
    if len(g[0]) < 2:
        raise OperatorFailed("too narrow")
    return [r[(len(r) + 1) // 2:] for r in g]


# Scale and Tile
def _upscale(g: Grid, k: int) -> Grid:
    return [[v for v in row for _ in range(k)] for row in g for _ in range(k)]


def scale2(g: Grid) -> Grid:
    return _upscale(g, 2)


def scale3(g: Grid) -> Grid:
    return _upscale(g, 3)


def downscale(g: Grid) -> Grid:
    h, w = len(g), len(g[0])
    for k in range(min(h, w), 1, -1):
        if h % k or w % k:
            continue
        ok = all(g[r][c] == g[r - r % k][c - c % k] for r in range(h) for c in range(w))
        if ok:
            return [[g[r][c] for c in range(0, w, k)] for r in range(0, h, k)]
    raise OperatorFailed("no uniform block size")


def tile_2x2(g: Grid) -> Grid:
    return [row + row for row in g] * 2


def tile_h(g: Grid) -> Grid:
    return [row + row for row in g]


def tile_v(g: Grid) -> Grid:
    return [list(r) for r in g] + [list(r) for r in g]


def mirror_h(g: Grid) -> Grid:
    return [row + row[::-1] for row in g]


def mirror_v(g: Grid) -> Grid:
    return [list(r) for r in g] + [list(r) for r in g[::-1]]


def mirror_4(g: Grid) -> Grid:
    return mirror_v(mirror_h(g))


# Physics and Fill
def gravity_down(g: Grid) -> Grid:
    bg = background(g)
    h, w = len(g), len(g[0])
    out = [[bg] * w for _ in range(h)]
    for c in range(w):
        col = [g[r][c] for r in range(h) if g[r][c] != bg]
        for i, v in enumerate(reversed(col)):
            out[h - 1 - i][c] = v
    return out


def fill_enclosed(g: Grid) -> Grid:
    bg = background(g)
    h, w = len(g), len(g[0])
    outside = [[False] * w for _ in range(h)]
    stack = [(r, c) for r in range(h) for c in (0, w - 1) if g[r][c] == bg]
    stack += [(r, c) for c in range(w) for r in (0, h - 1) if g[r][c] == bg]
    for r, c in stack:
        outside[r][c] = True
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not outside[ny][nx] and g[ny][nx] == bg:
                outside[ny][nx] = True
                stack.append((ny, nx))
    enclosed = [(r, c) for r in range(h) for c in range(w) if g[r][c] == bg and not outside[r][c]]
    if not enclosed:
        raise OperatorFailed("nothing enclosed")
    fg = Counter(v for row in g for v in row if v != bg)
    paint = min(fg, key=lambda c: (-fg[c], c))
    out = [list(r) for r in g]
    for r, c in enclosed:
        out[r][c] = paint
    return out


UNARY: dict[str, Callable[[Grid], Grid]] = {
    "rot90": rot90,
    "rot180": rot180,
    "rot270": rot270,
    "flip_h": flip_h,
    "flip_v": flip_v,
    "transpose": transpose,
    "crop_content": crop_content,
    "largest_object": largest_object,
    "smallest_object": smallest_object,
    "top_half": top_half,
    "bottom_half": bottom_half,
    "left_half": left_half,
    "right_half": right_half,
    "scale2": scale2,
    "scale3": scale3,
    "downscale": downscale,
    "tile_2x2": tile_2x2,
    "tile_h": tile_h,
    "tile_v": tile_v,
    "mirror_h": mirror_h,
    "mirror_v": mirror_v,
    "mirror_4": mirror_4,
    "gravity_down": gravity_down,
    "fill_enclosed": fill_enclosed,
}

FITTED = ("recolor_fit", "const_fit")
OPERATOR_NAMES: tuple[str, ...] = tuple(UNARY) + FITTED


def fit_colour_map(pairs: Sequence[tuple[Grid, Grid]]) -> dict[int, int]:
    mapping: dict[int, int] = {}
    usable = False
    for cur, tgt in pairs:
        if len(cur) != len(tgt) or len(cur[0]) != len(tgt[0]):
            continue
        usable = True
        for rc, rt in zip(cur, tgt):
            for a, b in zip(rc, rt):
                if mapping.setdefault(a, b) != b:
                    raise OperatorFailed("colour map inconsistent")
    if not usable:
        raise OperatorFailed("no same-shape pairs to fit")
    return mapping


def fit_constant_output(pairs: Sequence[tuple[Grid, Grid]]) -> Grid:
    targets = [tgt for _, tgt in pairs]
    if not targets or any(t != targets[0] for t in targets):
        raise OperatorFailed("targets differ")
    return [list(r) for r in targets[0]]


def apply_unary(name: str, grid: Grid) -> Grid:
    out = UNARY[name](_check(grid))
    return _check(out)


__all__ = [
    "FITTED",
    "Grid",
    "OPERATOR_NAMES",
    "OperatorFailed",
    "UNARY",
    "apply_unary",
    "background",
    "fit_colour_map",
    "fit_constant_output",
]
