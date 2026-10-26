"""Finite cellular transitions and directed graph morphism contracts."""

from typing import Any
import numpy as np
from .geometric import _grid


def _cellular(value):
    if set(value) != {"op", "grid", "birth", "survive", "steps", "boundary"}:
        raise ValueError("cellular requires grid, birth, survive, steps and boundary")
    grid = _grid(value["grid"])
    if np.any(grid > 1):
        raise ValueError("cellular states must be binary")
    for name in ("birth", "survive"):
        rule = value[name]
        if (
            not isinstance(rule, list)
            or len(rule) > 9
            or any(type(n) is not int or not 0 <= n <= 8 for n in rule)
            or len(set(rule)) != len(rule)
        ):
            raise ValueError("cellular rules require distinct neighbour counts 0..8")
    steps = value["steps"]
    if type(steps) is not int or not 0 <= steps <= 256 or steps * grid.size > 1048576:
        raise ValueError("cellular work exceeds budget")
    if value["boundary"] not in ("zero", "wrap"):
        raise ValueError("boundary must be zero or wrap")
    return grid, steps


def _graph(value):
    if not isinstance(value, dict) or set(value) != {"vertices", "edges"}:
        raise ValueError("graph requires vertices and edges")
    n, edges = value["vertices"], value["edges"]
    if type(n) is not int or not 1 <= n <= 256 or not isinstance(edges, list) or len(edges) > 65536:
        raise ValueError("graph exceeds vertex/edge budget")
    if any(
        not isinstance(e, list)
        or len(e) != 2
        or any(type(v) is not int or not 0 <= v < n for v in e)
        for e in edges
    ):
        raise ValueError("invalid graph edge")
    pairs = [tuple(e) for e in edges]
    if len(set(pairs)) != len(pairs):
        raise ValueError("duplicate edge")
    return n, pairs


def _morphism(value):
    if set(value) != {"op", "source", "target", "mapping"}:
        raise ValueError("morphism requires source, target and mapping")
    n, source = _graph(value["source"])
    m, target = _graph(value["target"])
    mapping = value["mapping"]
    if (
        not isinstance(mapping, list)
        or len(mapping) != n
        or any(type(i) is not int or not 0 <= i < m for i in mapping)
    ):
        raise ValueError("mapping must define every source vertex")
    return n, m, source, target, mapping


def execute_topology(value: dict[str, Any]):
    if value.get("op") == "cellular":
        grid, steps = _cellular(value)
        for _ in range(steps):
            padded = np.pad(grid, 1, mode="wrap" if value["boundary"] == "wrap" else "constant")
            h, w = grid.shape
            counts = np.zeros_like(grid)
            for dr in range(3):
                for dc in range(3):
                    if (dr, dc) != (1, 1):
                        counts += padded[dr : dr + h, dc : dc + w]
            grid = np.where(
                grid, np.isin(counts, value["survive"]), np.isin(counts, value["birth"])
            ).astype(np.uint8)
        return {
            "grid": grid.tolist(),
            "cells_updated": int(grid.size) * steps,
            "arithmetic": "exact_integer",
        }
    if value.get("op") == "graph_morphism":
        n, m, source, target, mapping = _morphism(value)
        adjacency = np.zeros((m, m), dtype=bool)
        for a, b in target:
            adjacency[a, b] = True
        missing = [[a, b] for a, b in source if not adjacency[mapping[a], mapping[b]]]
        return {
            "homomorphism": not missing,
            "violating_edges": missing,
            "isomorphism": not missing
            and n == m
            and len(set(mapping)) == n
            and len(source) == len(target),
            "edges_checked": len(source),
            "arithmetic": "exact_integer",
        }
    raise ValueError("unknown topology operation")


def verify_topology(value, output):
    if value.get("op") == "cellular":
        array, steps = _cellular(value)
        grid = array.tolist()
        h, w = array.shape
        for _ in range(steps):
            next_grid = []
            for r in range(h):
                row = []
                for c in range(w):
                    neighbours = 0
                    for dr, dc in (
                        (-1, -1),
                        (-1, 0),
                        (-1, 1),
                        (0, -1),
                        (0, 1),
                        (1, -1),
                        (1, 0),
                        (1, 1),
                    ):
                        nr, nc = r + dr, c + dc
                        if value["boundary"] == "wrap":
                            neighbours += grid[nr % h][nc % w]
                        elif 0 <= nr < h and 0 <= nc < w:
                            neighbours += grid[nr][nc]
                    row.append(int(neighbours in value["survive" if grid[r][c] else "birth"]))
                next_grid.append(row)
            grid = next_grid
        expected = {"grid": grid, "cells_updated": h * w * steps, "arithmetic": "exact_integer"}
    elif value.get("op") == "graph_morphism":
        n, m, source, target, mapping = _morphism(value)
        target = set(target)
        image = {(mapping[a], mapping[b]) for a, b in source}
        missing = [
            list(edge) for edge in source if (mapping[edge[0]], mapping[edge[1]]) not in target
        ]
        expected = {
            "homomorphism": image <= target,
            "violating_edges": missing,
            "isomorphism": n == m and len(set(mapping)) == n and image == target,
            "edges_checked": len(source),
            "arithmetic": "exact_integer",
        }
    else:
        raise ValueError("unknown topology operation")
    return [] if output == expected else ["topological transition oracle mismatch"]
