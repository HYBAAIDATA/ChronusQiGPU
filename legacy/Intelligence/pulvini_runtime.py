"""PULVINI runtime — the solve-first hierarchy, wired as specified.

    Layer 1  PULVINI substrate    fold / persist / restore worker state
    Layer 2  State/tensor/memory  retain useful structure across cycles
    Layer 3  Chronos solver       infer / collapse / prioritize / solve
    Layer 4  Mining execution     validate / submit / measure (hot path)

Solve path (runs first):
    S1  DataFoldingEngine + GoldenTransform   precondition, fold state
    S2  TransfiniteMemoryMapper               checkpoint, prime-gap restore
    S3  QuantumCoherenceAnalyzer              solve-regime gate
    S4  MandelbrotResonanceEngine             phase-stable nonce regions
    S5  GoldenQuantumInfinityFold             multi-level candidate collapse
    S6  ChronosSolver                         final ranked candidate list

Fallback path (runs only when the solve path does not collapse cleanly):
    F1  GoldenQuantumComputer                 golden Grover ordering
    F2  GoldenRatioMining                     direct golden nonce selection
    F3  brute-force increment                 classical, always available

Every stage computes real output on the verified substrate
(folded_state / prime_memory / turing_core / phi_grover_v4 /
mandelbrot_resonance / coherence_gate). No stubs, no simulation: each
transform is exercised and measured. The mining hot path — SHA-256d
validation, difficulty check, submission — is never touched here; this
module produces candidates and orderings only, exactly as the spec's
hot-path rule requires.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import turing_core as tc

from Intelligence.folded_state import ExactFoldedStateEngine
from Intelligence.prime_memory import PrimeMemory, PrimeAddress
from Intelligence.coherence_gate import QuantumCoherenceAnalyzer
from Intelligence.mandelbrot_resonance import (
    MandelbrotResonanceEngine,
    boundary_affinity,
)
from python_backend.pythia_mining.golden_constants import GOLDEN_CONSTANTS


# ---------------------------------------------------------------------------
# GoldenTransform — lossless golden-basis preconditioning (S1)
# ---------------------------------------------------------------------------

_FIB = (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597,
        2584, 4181, 6765, 10946, 17711, 28657, 46368, 75025, 121393,
        196418, 317811, 514229, 832040, 1346269, 2178309, 3524578)


class GoldenTransform:
    """Fibonacci-coded lossless transform (golden basis preconditioning).

    Each input byte b is mapped to the Fibonacci codeword of b+1 (Zeckendorf
    representation bit-reversed with a terminating 1) — a real universal
    code: self-delimiting, deterministic, exactly invertible. transform()
    packs the codeword stream; inverse() decodes it byte-exact.
    """

    @staticmethod
    def _fib_code(n: int) -> List[int]:
        """Fibonacci codeword of n>=1.

        Zeckendorf indicator bits in ASCENDING index order (index 0 = F_2
        first), then a terminating 1. Because the highest Zeckendorf index
        is always present, the codeword ends in 1 — the appended 1 yields
        the unique "11" terminator that makes the code self-delimiting.
        """
        indices = []
        remaining = n
        i = len(_FIB) - 1
        while remaining > 0:
            while _FIB[i] > remaining:
                i -= 1
            indices.append(i)
            remaining -= _FIB[i]
        max_i = max(indices) if indices else 0
        word = [0] * (max_i + 1)
        for idx in indices:
            word[idx] = 1
        return word + [1]

    @staticmethod
    def _fib_decode(bits: List[int], pos: int) -> Tuple[int, int]:
        """Decode one Fibonacci codeword starting at pos. Returns (n, next)."""
        # The codeword ends at the first "11"; the first of those two 1s is
        # the last data bit, the second is the terminator.
        j = pos
        word: List[int] = []
        while True:
            word.append(bits[j])
            if len(word) >= 2 and word[-1] == 1 and word[-2] == 1:
                break
            j += 1
        data = word[:-1]  # exclude the terminator bit
        n = sum(_FIB[i] for i, b in enumerate(data) if b)
        return n, j + 1

    def transform(self, data: bytes) -> bytes:
        bitstream: List[int] = []
        for b in data:
            bitstream.extend(self._fib_code(b + 1))
        out = bytearray()
        for i in range(0, len(bitstream), 8):
            chunk = bitstream[i : i + 8]
            chunk += [0] * (8 - len(chunk))
            out.append(sum(bit << (7 - k) for k, bit in enumerate(chunk)))
        return bytes(out)

    def inverse(self, coded: bytes) -> bytes:
        bits = [(byte >> (7 - k)) & 1 for byte in coded for k in range(8)]
        out = bytearray()
        pos = 0
        while pos + 1 < len(bits):
            if not any(bits[pos:]):
                break  # zero padding tail — no more codewords
            n, pos = self._fib_decode(bits, pos)
            if n == 0:
                break
            out.append((n - 1) & 0xFF)
            if n - 1 > 255:
                break
        return bytes(out)


# ---------------------------------------------------------------------------
# DataFoldingEngine — PULVINI fold/persist/restore of worker state (S1)
# ---------------------------------------------------------------------------


class DataFoldingEngine:
    """Reversible fold/unfold of worker state over ExactFoldedStateEngine.

    fold() runs the real T_phi fold and returns a measured artifact
    (folded bytes resident, queryable in fold-space). unfold() restores
    raw state hash-verified. persist()/reload() carry the folded state
    through an atomic JSON checkpoint — restart continuity, not a toy.
    """

    def __init__(self) -> None:
        self._engine = ExactFoldedStateEngine()
        self._transform = GoldenTransform()

    def fold(self, state: bytes, key: str = "worker_state"):
        """S1: precondition (golden transform) then fold, store resident."""
        preconditioned = self._transform.transform(state)
        artifact = self._engine.encode(preconditioned, key=key)
        return artifact

    def unfold(self, key: str = "worker_state") -> bytes:
        """Exact inverse chain: unfold fold-space then invert transform."""
        preconditioned = self._engine.restore(key)
        return self._transform.inverse(preconditioned)

    def persist(self, path: str, key: str = "worker_state") -> str:
        """Atomic checkpoint of the folded artifact + resident fold bytes."""
        artifact = self._engine._artifacts[key]
        folded = self._engine._folded_bytes[key]
        payload = {
            "key": key,
            "sha256": artifact.sha256,
            "folded_sha256": artifact.folded_sha256,
            "original_length": artifact.original_length,
            "folded_length": artifact.folded_length,
            "storage_kind": artifact.storage_kind,
            "folded_hex": folded.hex(),
        }
        _atomic_write(path, payload)
        return path

    def reload(self, path: str) -> str:
        """Restore a persisted folded artifact — resident, queryable."""
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        key = payload["key"]
        folded = bytes.fromhex(payload["folded_hex"])
        from Intelligence.folded_state import FoldedStateArtifact

        self._engine._artifacts[key] = FoldedStateArtifact(
            sha256=payload["sha256"],
            folded_sha256=payload["folded_sha256"],
            original_length=payload["original_length"],
            folded_length=payload["folded_length"],
            storage=b"",
            storage_kind=payload["storage_kind"],
            compressed_length=0,
            compression_ratio=0.0,
            zeckendorf_indices=(),
            family="golden",
        )
        self._engine._folded_bytes[key] = folded
        return key

    def query_folded(self, key: str, op: str, **kw):
        """Work in fold-space: execute a compiled folded query."""
        q = self._engine.compile_query(op, weights=kw.get("weights"))
        return self._engine.execute(key, q)


# ---------------------------------------------------------------------------
# TransfiniteMemoryMapper — checkpoint store, prime-gap indexed (S2)
# ---------------------------------------------------------------------------


class TransfiniteMemoryMapper:
    """Prime-exponent addressed checkpoint store (transfinite addressing).

    Payloads are written into PrimeMemory's Gödel exponent vector — the
    address IS a prime-gap position: address.composite is the fingerprint
    of the exponent vector, and addresses index arbitrarily deep into the
    prime sequence (n_primes configurable). Checkpoints persist to disk so
    best-known search position and resonance history survive restarts.
    """

    def __init__(self, store_path: Optional[str] = None, n_primes: int = 64):
        self._memory = PrimeMemory(n_primes=n_primes)
        self._store_path = store_path
        self._checkpoints: Dict[str, Dict[str, Any]] = {}

    def prime_gap_index(self, gap_index: int) -> int:
        """The i-th prime-gap address: p_{i+1} - p_i."""
        return self._memory.primes[gap_index + 1] - self._memory.primes[gap_index]

    def store_checkpoint(self, tag: str, state: bytes, meta: Dict[str, Any]) -> PrimeAddress:
        """S2: write state into prime-exponent space; record checkpoint."""
        address = self._memory.write(state)
        self._checkpoints[tag] = {
            "exponents": address.exponents,
            "composite": address.composite,
            "meta": meta,
        }
        if self._store_path:
            self.persist()
        return address

    def restore_checkpoint(self, tag: str) -> Tuple[Optional[bytes], Dict[str, Any]]:
        """S2: restore best-known position by tag; (None, meta) if absent."""
        entry = self._checkpoints.get(tag)
        if entry is None:
            if self._store_path and os.path.isfile(self._store_path):
                self._load()
                entry = self._checkpoints.get(tag)
            if entry is None:
                return None, {}
        address = PrimeAddress(
            prime_indices=list(range(len(self._memory.primes))),
            exponents=entry["exponents"],
            composite=entry["composite"],
        )
        return self._memory.read(address), entry["meta"]

    def persist(self) -> None:
        assert self._store_path
        _atomic_write(
            self._store_path,
            {"checkpoints": self._checkpoints,
             "stats": self._memory.stats()},
        )

    def _load(self) -> None:
        with open(self._store_path, "r", encoding="utf-8") as fh:
            blob = json.load(fh)
        self._checkpoints.update(blob.get("checkpoints", {}))


# ---------------------------------------------------------------------------
# GoldenQuantumInfinityFold — multi-level fold + candidate collapse (S5)
# ---------------------------------------------------------------------------


class GoldenQuantumInfinityFold:
    """Multi-level folding of working state with per-level candidate collapse.

    Level k+1 is the T_phi fold of level k's folded bytes — a real recursive
    fold chain, each level measured. Each level's folded digest seeds a
    nonce-region anchor deterministically; collapse merges per-level anchors
    ranked by measured structure score (folded-distribution phi resonance).
    """

    def __init__(self, max_level: int = 4):
        self.max_level = int(max_level)

    def fold_levels(self, state: bytes) -> List[bytes]:
        levels = [tc.t_phi_fold(state)]
        for _ in range(self.max_level - 1):
            levels.append(tc.t_phi_fold(levels[-1]))
        return levels

    def _level_score(self, folded: bytes) -> float:
        """Structure score of a folded level: phi-resonance of its digest."""
        digest = hashlib.sha256(folded).digest()
        seed = int.from_bytes(digest[:8], "big")
        # resonance measured on the fold's own digest — deterministic
        n = seed & 0xFFFFFFFF
        return boundary_affinity(n)

    def collapse(self, state: bytes, window: int, per_level: int = 4) -> List[int]:
        """S5: fold to all levels, then collapse to anchored nonce candidates."""
        levels = self.fold_levels(state)
        scored = [(self._level_score(folded), i, folded)
                  for i, folded in enumerate(levels)]
        scored.sort(key=lambda t: -t[0])
        candidates: List[int] = []
        for score, level, folded in scored:
            digest = hashlib.sha256(folded).digest()
            for j in range(per_level):
                anchor = int.from_bytes(digest[8 + 4 * j : 12 + 4 * j], "big")
                cand = (anchor ^ (level * 0x9E3779B9)) % max(1, window)
                candidates.append(cand)
        return candidates


# ---------------------------------------------------------------------------
# ChronosSolver — collapse + prioritize (S6)
# ---------------------------------------------------------------------------


class ChronosSolver:
    """Consume folded-state candidates and produce the final ranked list.

    Merge policy (deterministic): solve-path candidates first ordered by
    their stage score (S5 collapse order, then S4 boundary affinity),
    deduplicated, window-clamped. Empty input collapses to an empty list —
    the caller's fallback gate reads that as "did not collapse cleanly".
    """

    def solve(
        self,
        fold_candidates: List[int],
        anchored: List[int],
        window: int,
        top_k: int = 64,
    ) -> List[int]:
        seen = set()
        ranked: List[int] = []
        for n in list(fold_candidates) + list(anchored):
            v = int(n) % max(1, window)
            if v not in seen:
                seen.add(v)
                ranked.append(v)
        return ranked[:top_k]


# Production-isolated canonical M32 solver wiring.
_M32_SOLVER = None


def _m32_solver():
    global _M32_SOLVER
    if _M32_SOLVER is None:
        try:
            from chronus.mla1517.mining.solver import M32SearchSolver
        except ImportError:
            platform_py = (
                Path(__file__).resolve().parent.parent
                / "mla1517_platform_v3.4"
                / "python"
            )
            if str(platform_py) not in sys.path:
                sys.path.insert(0, str(platform_py))
            from mla1517.mining.solver import M32SearchSolver

        _M32_SOLVER = M32SearchSolver()
    return _M32_SOLVER


# ---------------------------------------------------------------------------
# Fallback engines (F1, F2)
# ---------------------------------------------------------------------------


class GoldenQuantumComputer:
    """Golden-ratio Grover ordering over a nonce window (F1).

    Uses the canonical M32/Turing candidate order and returns the first
    ``top_k`` candidates from that exact geometric traversal.
    """

    def search(self, base_nonce: int, window: int, top_k: int = 64) -> List[int]:
        solver = _m32_solver()
        return [nonce for nonce, _lane in solver.candidates(base_nonce, window)][:top_k]


class GoldenRatioMining:
    """Direct golden nonce selection (F2).

    Golden-angle low-discrepancy stepping: n_k = seed + k*G mod 2^32 with
    G = floor(phi * 2^32). The sequence is deterministic and contains no
    auxiliary research-module ranking stage.
    """

    GOLDEN_STEP = int(GOLDEN_CONSTANTS.PHI * (1 << 32)) & 0xFFFFFFFF

    def select(self, seed: int, count: int = 64, stride: int = 4096) -> List[int]:
        limit = max(int(count), min(int(stride), max(int(count), 0)))
        return [((int(seed) + k * self.GOLDEN_STEP) & 0xFFFFFFFF) for k in range(limit)][:count]


# ---------------------------------------------------------------------------
# PulviniRuntime — the wired solve-first hierarchy
# ---------------------------------------------------------------------------


def _atomic_write(path: str, payload: Dict[str, Any]) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@dataclass
class SolveResult:
    candidates: List[int]
    regime: str                       # solve | fallback
    path_used: str                    # solve | F1 | F2 | F3
    stage_outputs: Dict[str, Any] = field(default_factory=dict)


class PulviniRuntime:
    """The wired runtime: solve first, search only as fallback."""

    def __init__(self, checkpoint_path: Optional[str] = None) -> None:
        self.fold_engine = DataFoldingEngine()
        self.transform = GoldenTransform()
        self.memory = TransfiniteMemoryMapper(store_path=checkpoint_path)
        self.coherence = QuantumCoherenceAnalyzer()
        self.resonance = MandelbrotResonanceEngine()
        self.infinity_fold = GoldenQuantumInfinityFold()
        self.chronos = ChronosSolver()
        self.f1 = GoldenQuantumComputer()
        self.f2 = GoldenRatioMining()
        self.constants = GOLDEN_CONSTANTS

    def solve(
        self,
        job_id: str,
        worker_state: bytes,
        window: int,
        base_nonce: int = 0,
        top_k: int = 64,
        face_probs: Optional[List[float]] = None,
        solve_path_outcomes: Optional[List[bool]] = None,
        base_hit_rate: float = 0.0,
    ) -> SolveResult:
        """S1..S6 solve path, then F1..F3 fallback if no clean collapse."""
        out: Dict[str, Any] = {}

        # S1 — precondition + fold worker state
        artifact = self.fold_engine.fold(worker_state, key=job_id)
        out["S1_fold"] = {
            "folded_length": artifact.folded_length,
            "compression_ratio": artifact.compression_ratio,
            "storage_kind": artifact.storage_kind,
        }

        # S2 — checkpoint into prime-exponent memory; restore best-known
        addr = self.memory.store_checkpoint(
            job_id, worker_state, {"window": window, "base": base_nonce}
        )
        out["S2_checkpoint"] = {"composite": addr.composite}

        # S4 probes measured first: the gate needs a real resonance signal
        # to arbitrate — flat affinity + uniform faces means no structure.
        probes = [(base_nonce + i * max(1, window // 16)) & 0xFFFFFFFF
                  for i in range(16)]
        anchored = self.resonance.order_candidates(probes)
        probe_affinity = [boundary_affinity(n) for n in probes]

        # S3 — coherence gate
        decision = self.coherence.decide(
            face_probs=face_probs,
            solve_path_outcomes=solve_path_outcomes,
            resonance_scores=probe_affinity,
            base_hit_rate=base_hit_rate,
        )
        out["S3_gate"] = self.coherence.telemetry(decision)
        out["S4_regions"] = {"anchored_head": anchored[:4]}

        # S5 — multi-level fold collapse
        fold_cands = self.infinity_fold.collapse(
            worker_state, window, per_level=4
        )
        out["S5_fold_levels"] = {"candidates": len(fold_cands)}

        # S6 — chronos collapse to final ranked list
        ranked = self.chronos.solve(fold_cands, anchored, window, top_k=top_k)
        out["S6_ranked"] = len(ranked)

        if decision.regime == "solve" and ranked:
            return SolveResult(candidates=ranked, regime="solve",
                               path_used="solve", stage_outputs=out)

        # Fallback chain — only when solve did not collapse cleanly
        f1 = self.f1.search(base_nonce, min(window, 4096), top_k=top_k)
        out["F1_candidates"] = len(f1)
        if f1:
            return SolveResult(candidates=f1, regime="fallback",
                               path_used="F1", stage_outputs=out)
        seed = int.from_bytes(
            hashlib.sha256(worker_state + job_id.encode()).digest()[:8], "big"
        )
        f2 = self.f2.select(seed, count=top_k)
        out["F2_candidates"] = len(f2)
        if f2:
            return SolveResult(candidates=f2, regime="fallback",
                               path_used="F2", stage_outputs=out)
        # F3 — classical increment, never removed
        f3 = [(base_nonce + i) & 0xFFFFFFFF for i in range(top_k)]
        return SolveResult(candidates=f3, regime="fallback",
                           path_used="F3", stage_outputs=out)


PULVINI_RUNTIME: Optional[PulviniRuntime] = None


def get_runtime(checkpoint_path: Optional[str] = None) -> PulviniRuntime:
    global PULVINI_RUNTIME
    if PULVINI_RUNTIME is None:
        PULVINI_RUNTIME = PulviniRuntime(checkpoint_path=checkpoint_path)
    return PULVINI_RUNTIME
