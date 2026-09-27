"""Mining search — Grover-style search, Merkle verifier, preimage work.

Three search primitives, all deterministic and all routed through the
Lucas pool:

- ``GroverStyleSearch`` — walk-based search over the nonce graph. The
  Grover iteration count k* = floor(pi/4 * sqrt(N)) is exact algebraic
  work; candidate probing uses real double-SHA256 against the target.
  Route: ``path_kernel``.
- ``MerklePathVerifier`` — folds a coinbase hash up its branch path
  with double-SHA256 and compares against the block's Merkle root.
  Route: ``path_kernel``.
- ``PreimageSearch`` — scans an ordered nonce schedule for a hash under
  target (the preimage core of proof-of-work). Route: ``mining_kernel``.
"""

# LUCAS WIRING: draws from lucas/ (pool) and the canonical turing_core
# substrate. MUST NOT import from any sibling algorithm.
# Substrate routes: path (search walk, merkle), mining (preimage).

from __future__ import annotations

import math
import struct
from typing import Any, Dict, List

import numpy as np

import turing_core

THEOREM_PROVEN = False

# Canonical 2-node search graph: probe <-> accept. Walk counts are the
# path quantity the path_kernel bounds.
_SEARCH_GRAPH = np.array([[0, 1], [1, 0]], dtype=np.int64)
_NONCE_STRUCT = struct.Struct("<I")


def double_sha256(data: bytes) -> bytes:
    return turing_core.PythiaMiningEngine.double_sha256(data)


def _pack_nonce(blob: bytearray, nonce: int) -> None:
    offset = 76 if len(blob) >= 80 else len(blob)
    _NONCE_STRUCT.pack_into(blob, offset, nonce & 0xFFFFFFFF)


def _target_int(target: Any) -> int:
    """Normalize int/bytes/hex-string targets to the canonical integer form."""
    if isinstance(target, int):
        return target
    if isinstance(target, bytes):
        return int.from_bytes(target, byteorder="big")
    if isinstance(target, str):
        return int(target.replace("0x", "").strip().zfill(64), 16)
    return int(target)


class GroverStyleSearch:
    """Grover-style amplitude-amplification search over the nonce schedule.

    For N candidates the exact Grover iteration count is
    k* = floor(pi/4 * sqrt(N)); the schedule order determines which
    candidate each iteration probes. Verification is real double-SHA256
    against the consensus target — amplitude math orders the search, it
    never replaces the consensus check.
    """

    def __init__(self) -> None:
        self._searches = 0

    @staticmethod
    def optimal_iterations(n_candidates: int) -> int:
        """Exact Grover iteration count k* for N candidates."""
        return max(1, int(math.floor(math.pi / 4.0 * math.sqrt(max(n_candidates, 1)))))

    def kernel_check(self, n: int = 10) -> Dict[str, Any]:
        from lucas.pool import get as _lucas_get

        result = _lucas_get("path_kernel")(_SEARCH_GRAPH, n)
        result["module"] = __name__
        return result

    def search(
        self,
        header: bytes,
        schedule: List[int],
        target: Any,
    ) -> Dict[str, Any]:
        """Probe the schedule in Grover order; return the winner if any."""
        self._searches += 1
        size = len(schedule)
        if size == 0:
            return {
                "candidates": 0,
                "grover_k_star": 0,
                "probed": 0,
                "winner_nonce": -1,
                "mining_success": False,
                "kernel": "path_kernel",
                "theorem_proven": False,
            }
        k_star = self.optimal_iterations(size)
        target_int = _target_int(target)
        visited = np.zeros(size, dtype=bool)
        next_unseen = 0
        idx = 0
        winner = -1
        probed = 0
        blob = bytearray(header)
        if len(blob) < 80:
            blob.extend(b"\x00" * (80 - len(blob)))
        view = memoryview(blob)
        while probed < size:
            if not visited[idx]:
                visited[idx] = True
                probed += 1
                nonce = int(schedule[idx]) & 0xFFFFFFFF
                _pack_nonce(blob, nonce)
                if turing_core.hash_meets_target(
                    double_sha256(view), target_int
                ):
                    winner = nonce
                    break
            idx = (idx + k_star) % size
            if visited[idx]:
                while next_unseen < size and visited[next_unseen]:
                    next_unseen += 1
                if next_unseen >= size:
                    break
                idx = next_unseen
        return {
            "candidates": size,
            "grover_k_star": k_star,
            "probed": probed,
            "winner_nonce": winner,
            "mining_success": winner >= 0,
            "kernel": "path_kernel",
            "theorem_proven": False,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "searches": self._searches,
            "kernel": "path_kernel",
            "theorem_proven": False,
        }


class MerklePathVerifier:
    """Verifies block inclusion by folding the Merkle branch path."""

    def __init__(self) -> None:
        self._verified = 0

    def kernel_check(self, branch_len: int, n: int = 10) -> Dict[str, Any]:
        from lucas.pool import get as _lucas_get

        result = _lucas_get("path_kernel")(_SEARCH_GRAPH, n)
        result["branch_length"] = branch_len
        result["module"] = __name__
        return result

    def verify(
        self,
        leaf_hash: bytes,
        branches: List[bytes],
        expected_root: bytes,
    ) -> Dict[str, Any]:
        """Fold leaf + branches with double-SHA256; compare to root."""
        self._verified += 1
        root = turing_core.PythiaMiningEngine.compute_merkle_root(leaf_hash, branches)
        return {
            "branch_length": len(branches),
            "computed_root": root.hex(),
            "expected_root": expected_root.hex(),
            "included": root == expected_root,
            "kernel": "path_kernel",
            "theorem_proven": False,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "verifications": self._verified,
            "kernel": "path_kernel",
            "theorem_proven": False,
        }


class PreimageSearch:
    """Hash preimage search — the proof-of-work core scan."""

    def __init__(self) -> None:
        self._scans = 0

    def kernel_check(self, nonce_space: int, n: int = 10) -> Dict[str, Any]:
        from lucas.pool import get as _lucas_get

        result = _lucas_get("mining_kernel")(nonce_space, n)
        result["module"] = __name__
        return result

    def scan(
        self,
        header: bytes,
        nonces: List[int],
        target: Any,
    ) -> Dict[str, Any]:
        """Scan ordered nonces for sha256d(header|nonce) meets_target."""
        self._scans += 1
        winner = -1
        for nonce in nonces:
            n32 = int(nonce) & 0xFFFFFFFF
            blob = header + struct.pack("<I", n32)
            if turing_core.hash_meets_target(double_sha256(blob), _target_int(target)):
                winner = n32
                break
        return {
            "scanned": len(nonces),
            "winner_nonce": winner,
            "mining_success": winner >= 0,
            "kernel": "mining_kernel",
            "theorem_proven": False,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "scans": self._scans,
            "kernel": "mining_kernel",
            "theorem_proven": False,
        }


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas routes against the shared pool."""
    from lucas.pool import get as _lucas_get

    result = _lucas_get("path_kernel")(_SEARCH_GRAPH, n)
    result["module"] = __name__
    return result
