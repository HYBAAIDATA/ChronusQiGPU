"""Bounded software-native SHA-256d candidate search."""

import hashlib
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from chronus.config import runtime_bounds
from chronus.execution.structural import zeckendorf_decode, zeckendorf_encode, zeckendorf_increment

POLYHEDRAL_FACES = 12   # dodecahedron face centroids
POLYHEDRAL_VERTICES = 20  # icosahedron vertices; 12 + 20 = 32 lanes


def polyhedral_lane(lane: int) -> dict[str, Any]:
    """Label a search lane with its polyhedral traversal identity."""
    lanes = _lanes()
    if not isinstance(lane, int) or isinstance(lane, bool) or not 0 <= lane < lanes:
        raise ValueError(f"lane must be an integer in [0, {lanes})")
    if lanes != POLYHEDRAL_FACES + POLYHEDRAL_VERTICES:
        return {"lane": lane, "polyhedral": None}
    if lane < POLYHEDRAL_FACES:
        return {"lane": lane, "polyhedral": "dodecahedron-face", "index": lane}
    return {
        "lane": lane,
        "polyhedral": "icosahedron-vertex",
        "index": lane - POLYHEDRAL_FACES,
    }


def _lanes() -> int:
    return runtime_bounds()["search_lanes"]


def _max_reported() -> int:
    return runtime_bounds()["max_reported_matches"]


def _max_candidates() -> int:
    return runtime_bounds()["max_search_candidates"]


def partition_nonce_range(start: int, stop: int) -> list[tuple[int, int]]:
    """Partition a half-open nonce interval into disjoint contiguous lanes."""
    if not (0 <= start <= stop <= 1 << 32):
        raise ValueError("nonce range must be within [0, 2**32]")
    lanes = _lanes()
    width, remainder = divmod(stop - start, lanes)
    return [
        (
            start + lane * width + min(lane, remainder),
            start + (lane + 1) * width + min(lane + 1, remainder),
        )
        for lane in range(lanes)
    ]


def _search_lane(args: tuple[bytes, int, int, int, str, int]) -> dict[str, Any]:
    header, start, stop, target, step_order, lane = args
    prefix = hashlib.sha256(header[:64])
    suffix = header[64:76]
    matches = []
    match_count = 0
    if step_order == "zeckendorf":
        # Carry-free traversal: every candidate visited exactly once via the
        # canonical fold rule; the binary value is decoded only for hashing.
        indices = zeckendorf_encode(start)
        candidate = start
        while candidate < stop:
            nonce = candidate
            assert zeckendorf_decode(indices) == nonce  # traversal invariant
            inner = prefix.copy()
            inner.update(suffix + nonce.to_bytes(4, "little"))
            digest = hashlib.sha256(inner.digest()).digest()
            if int.from_bytes(digest, "little") <= target:
                match_count += 1
                if len(matches) < _max_reported():
                    matches.append({"nonce": nonce, "hash": digest[::-1].hex()})
            indices = zeckendorf_increment(indices)
            candidate = zeckendorf_decode(indices)
    else:
        for nonce in range(start, stop):
            inner = prefix.copy()
            inner.update(suffix + nonce.to_bytes(4, "little"))
            digest = hashlib.sha256(inner.digest()).digest()
            if int.from_bytes(digest, "little") <= target:
                match_count += 1
                if len(matches) < _max_reported():
                    matches.append({"nonce": nonce, "hash": digest[::-1].hex()})
    result = {"start": start, "stop": stop, "tested": stop - start,
              "match_count": match_count, "matches": matches,
              "step_order": step_order}
    result.update(polyhedral_lane(lane))
    return result


def search_nonce_range(
    header: bytes, start: int, stop: int, target: int, workers: int = 1,
    step_order: str = "binary",
) -> dict[str, Any]:
    """Hash each nonce once; target is interpreted as Bitcoin's little-endian uint256."""
    if step_order not in ("binary", "zeckendorf"):
        raise ValueError("step_order must be 'binary' or 'zeckendorf'")
    if not isinstance(header, bytes) or len(header) != 80:
        raise ValueError("header must be exactly 80 bytes")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in (start, stop, target, workers)):
        raise ValueError("start, stop, target and workers must be integers")
    lanes = partition_nonce_range(start, stop)
    max_candidates = _max_candidates()
    if stop == start or stop - start > max_candidates:
        raise ValueError(f"range must contain between 1 and {max_candidates} candidates")
    if not 0 <= target < 1 << 256:
        raise ValueError("target must be an unsigned 256-bit integer")
    if not 1 <= workers <= _lanes():
        raise ValueError(f"workers must be between 1 and {_lanes()}")
    jobs = [
        (header, lane_start, lane_stop, target, step_order, lane_index)
        for lane_index, (lane_start, lane_stop) in enumerate(lanes)
    ]
    processes = min(workers, os.cpu_count() or 1)
    if processes == 1:
        results = list(map(_search_lane, jobs))
    else:
        with ProcessPoolExecutor(max_workers=processes) as pool:
            results = list(pool.map(_search_lane, jobs))
    match_count = sum(lane["match_count"] for lane in results)
    matches = [
        match for lane in results for match in lane["matches"]
    ][:_max_reported()]
    return {
        "algorithm": "SHA-256d",
        "execution_mode": "SOFTWARE_EXECUTION",
        "step_order": step_order,
        "lanes": [
            {key: value for key, value in lane.items() if key != "matches"}
            for lane in results
        ],
        "workers": processes,
        "tested": sum(lane["tested"] for lane in results),
        "match_count": match_count,
        "matches": matches,
        "matches_truncated": match_count > len(matches),
    }
