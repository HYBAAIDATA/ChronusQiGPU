"""Hash pipeline: exact M32 ordering plus real sha256d verification.

Geometry changes probe order only. Consensus remains the Bitcoin double-SHA256
target check, and every reported digest is physically computed by the active
hasher backend.
"""

from __future__ import annotations

import hashlib
import hmac
import struct
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

try:
    from Intelligence.unified_punch import UnifiedPunchHost
except ImportError:  # pragma: no cover
    UnifiedPunchHost = None  # type: ignore[assignment]

try:
    from mining.bitcoin_hasher import BitcoinHasher
except ImportError:  # pragma: no cover
    BitcoinHasher = None  # type: ignore[assignment]

GPU_BATCH = 1 << 20  # grind launch window (BitcoinHasher.GRIND_BATCH)


def double_sha256(data: bytes) -> bytes:
    """Real Bitcoin double-SHA256. The ONLY accept/reject rule."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def nonce_order_fingerprint(nonces: List[int]) -> bytes:
    """Hash the exact ordered uint32 nonce sequence used for execution."""
    digest = hashlib.sha256()
    digest.update(b"pythia.nonce-order.v1")
    digest.update(struct.pack("<Q", len(nonces)))
    for raw in nonces:
        nonce = int(raw)
        if not 0 <= nonce <= 0xFFFFFFFF:
            raise ValueError("nonce order contains a value outside uint32")
        digest.update(struct.pack("<I", nonce))
    return digest.digest()


@dataclass
class HashResult:
    winning_nonce: Optional[int]
    winning_hash: Optional[bytes]
    hashes_computed: int
    candidates_scored: int
    candidates_passed_filter: int
    elapsed_seconds: float
    measured_hps: float
    backend: str  # backend that ran the sha256d accept/reject
    device: str  # device that ran the sha256d accept/reject
    scoring_backend: str = "none"  # backend that ran Stage A scoring
    scoring_device: str = "none"  # device that ran Stage A scoring
    scoring_seconds: float = 0.0  # wall time in Stage A score/filter
    hashing_seconds: float = 0.0  # wall time in the sha256d grind

    @property
    def mining_success(self) -> bool:
        return self.winning_nonce is not None


class HashPipeline:
    """End-to-end hash loop: deterministic order plus real sha256d."""

    def __init__(
        self,
        host=None,
        threshold: float = 0.0,
        hasher=None,
        hasher_backend: str = "auto",
    ) -> None:
        if host is None and UnifiedPunchHost is not None:
            host = UnifiedPunchHost()
        self.host = host
        self.threshold = float(threshold)
        self._hasher = hasher
        self._hasher_backend = hasher_backend
        self.scoring_backend = "none"
        self.scoring_device = "none"

    @property
    def hasher(self):
        """Lazily constructed so non-mining use pays no OpenCL init cost."""
        if self._hasher is None:
            if self._hasher_backend == "remote":
                from mining.remote_hasher import hasher_for_env

                self._hasher = hasher_for_env()
            else:
                if BitcoinHasher is None:
                    raise RuntimeError("mining.bitcoin_hasher unavailable")
                self._hasher = BitcoinHasher(backend=self._hasher_backend)
        return self._hasher

    @staticmethod
    def _as_nonce_array(nonces: Sequence[int] | np.ndarray) -> np.ndarray:
        if isinstance(nonces, np.ndarray):
            nonce_array = nonces
        else:
            nonce_array = np.asarray(nonces, dtype=np.uint64)
        if nonce_array.ndim != 1:
            raise ValueError("nonces must be a one-dimensional sequence")
        if nonce_array.size == 0:
            return np.empty(0, dtype=np.uint32)
        nonce64 = nonce_array.astype(np.uint64, copy=False)
        if int(nonce64.max()) > 0xFFFFFFFF or int(nonce64.min()) < 0:
            raise ValueError("nonces must be uint32 integers")
        return nonce64.astype(np.uint32, copy=False)

    def _m32_lane_order(self, base_nonce: int) -> tuple[int, ...]:
        """The 32-entry Turing lane permutation for this window base.

        The canonical M32 solver is owned by ``mining.stratum_bridge`` (the
        declared bridge to the MLA1517 platform); this method delegates so
        the pipeline carries no platform import or ``sys.path`` mutation of
        its own.  The stratum bridge imports this module, so the import is
        deferred to call time.
        """
        from mining.stratum_bridge import _m32_lane_order as _canonical_lane_order

        return _canonical_lane_order(base_nonce)

    @staticmethod
    def _contiguous_m32_window(
        nonce_array: np.ndarray,
    ) -> tuple[int, int] | None:
        if nonce_array.size == 0:
            return None
        base_nonce = int(nonce_array[0])
        count = int(nonce_array.size)
        if base_nonce % 32 or count % 32:
            return None
        if count > 1:
            deltas = (
                nonce_array[1:].astype(np.uint64) - nonce_array[:-1].astype(np.uint64)
            ) & np.uint64(0xFFFFFFFF)
            if not np.all(deltas == np.uint64(1)):
                return None
        return base_nonce, count

    # Stage A amplitude scoring is a pure host-side manifold metric.  The
    # φ-filter formula is the kernel-parity fold x/sqrt(1+Σw·x²) weighted by
    # φ^-(j+1) over the 11-dim feature map — the same closed form the
    # unified-punch .cl kernel implements, evaluated here in float32 without
    # a punch dispatch (phi_filter_score is not a registered punch).
    _SCORE_DIM = 11
    _GOLDEN_ANGLE = 2.39996322972865332

    def score_nonces(self, nonces: List[int]) -> List[float]:
        """Score candidates with the φ-filter manifold metric in [0,1].

        Ordering-only diagnostic — never a consensus predicate.  Returns a
        neutral 0.5 slate for empty input.
        """
        if not nonces:
            self.scoring_backend = "none"
            self.scoring_device = "none"
            return []
        n = len(nonces)
        w32 = np.array(
            [np.float32(1.618033988749895) ** np.float32(-(j + 1)) for j in range(self._SCORE_DIM)],
            dtype=np.float32,
        )
        nonce_arr = np.asarray(nonces, dtype=np.uint64) & np.uint64(0xFFFFFFFF)
        theta = nonce_arr.astype(np.float64) * self._GOLDEN_ANGLE
        in_float = np.empty((n, self._SCORE_DIM), dtype=np.float32)
        np.divide(
            nonce_arr & np.uint64(0xFFFF),
            np.float64(65535.0),
            out=in_float[:, 0],
            casting="same_kind",
        )
        np.divide(
            (nonce_arr >> np.uint64(16)) & np.uint64(0xFFFF),
            np.float64(65535.0),
            out=in_float[:, 1],
            casting="same_kind",
        )
        # Write the cosine block straight into the f32 array — no f64
        # temporaries (they were ~4x28 MB of traffic per 400k window).
        blk = in_float[:, 2:]
        np.add(
            theta[:, None],
            np.arange(2, self._SCORE_DIM, dtype=np.float64)[None, :],
            out=blk,
            casting="same_kind",
        )
        np.cos(blk, out=blk)
        blk *= np.float32(0.5)
        blk += np.float32(0.5)
        norm_sq = (in_float * in_float) @ w32
        denom = np.sqrt(np.float32(1.0) + norm_sq).astype(np.float32)
        f = in_float / denom[:, None]
        scores = np.clip((f * f) @ w32, np.float32(0.0), np.float32(1.0))
        self.scoring_backend = "cpu"
        self.scoring_device = "numpy-phi-filter"
        return scores.tolist()

    def grind_with_chronus_substrate(
        self,
        header80: bytes,
        target_be: bytes,
        nonces: List[int],
        max_hashes: Optional[int] = None,
        *,
        fold_depth: int = 1,
        seed: int = 0,
    ):
        """Order candidates through Chronus, then run canonical SHA-256d.

        The substrate has ORDER_ONLY authority.  The resulting permutation is
        sealed before dispatch, every selected candidate is hashed by the
        configured backend, and ``grind`` retains its independent consensus
        recheck.
        """
        from chronus.mining_bridge import ChronusSubstrateMiningBridge

        scores = self.score_nonces(nonces)
        ordered, evidence = ChronusSubstrateMiningBridge(seed=seed).order(
            nonces,
            scores,
            fold_depth=fold_depth,
        )
        result = self.grind(
            header80,
            target_be,
            ordered,
            max_hashes=max_hashes,
            preordered=True,
            sealed_fingerprint=nonce_order_fingerprint(ordered),
        )
        self.scoring_backend = "chronus-substrate"
        self.scoring_device = "phi-tensor-diffusion"
        result.scoring_backend = self.scoring_backend
        result.scoring_device = self.scoring_device
        return result, evidence

    def grind(
        self,
        header80: bytes,
        target_be: bytes,
        nonces: List[int],
        max_hashes: Optional[int] = None,
        *,
        preordered: bool = False,
        sealed_fingerprint: bytes | str | None = None,
    ) -> HashResult:
        """Grind real sha256d in a deterministic candidate order."""
        t0 = time.perf_counter()
        if len(header80) != 80:
            raise ValueError("header must be 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be 32 bytes")
        nonce_array = self._as_nonce_array(nonces)
        if max_hashes is not None:
            nonce_array = nonce_array[:max_hashes]
        if preordered:
            # The caller owns deterministic ordering, but the order is not
            # trusted merely because a flag says "preordered".  Verify the
            # content seal before any hasher side effect.
            if sealed_fingerprint is None:
                raise ValueError("preordered grind requires sealed_fingerprint")
            expected_seal = nonce_order_fingerprint(nonces)
            if isinstance(sealed_fingerprint, str):
                try:
                    supplied_seal = bytes.fromhex(sealed_fingerprint)
                except ValueError as exc:
                    raise ValueError("sealed_fingerprint must be hexadecimal") from exc
            else:
                supplied_seal = bytes(sealed_fingerprint)
            if not hmac.compare_digest(expected_seal, supplied_seal):
                raise ValueError("sealed nonce order fingerprint mismatch")
            # Do not score a window twice: this is a throughput guard, not a
            # consensus shortcut.
            candidates_scored = len(nonces)
            candidates_passed = int(nonce_array.size)
            self.scoring_backend = "preordered"
            self.scoring_device = "deterministic-schedule"
            scoring_el = 0.0
            winner, win_hash, hashes = self._grind_in_order(header80, target_be, nonce_array)
        else:
            candidates_scored = len(nonces)
            candidates_passed = int(nonce_array.size)
            scoring_el = 0.0
            m32_window = self._contiguous_m32_window(nonce_array)
            if m32_window is not None:
                base_nonce, count = m32_window
                winner, win_hash, hashes = self.hasher.grind_target_m32(
                    header80,
                    target_be,
                    base_nonce,
                    self._m32_lane_order(base_nonce),
                    count,
                )
                self.scoring_backend = "m32-device-order"
                self.scoring_device = "turing-m32-lane-order"
            else:
                winner, win_hash, hashes = self._grind_in_order(header80, target_be, nonce_array)
                self.scoring_backend = "input-order"
                self.scoring_device = "declared-window"

        # Independent consensus recheck at the pipeline boundary.  A backend
        # candidate is never returned merely because it reported a hit.
        if winner is not None:
            reference = double_sha256(header80[:76] + struct.pack("<I", int(winner) & 0xFFFFFFFF))
            if win_hash != reference or reference[::-1] > target_be:
                raise RuntimeError("backend candidate failed independent SHA-256d target recheck")
        el = time.perf_counter() - t0
        return HashResult(
            winner,
            win_hash,
            hashes,
            candidates_scored,
            candidates_passed,
            el,
            hashes / el if el > 0 else 0.0,
            self.hasher.backend,
            self.hasher.device,
            self.scoring_backend,
            self.scoring_device,
            scoring_seconds=scoring_el,
            hashing_seconds=max(0.0, el - scoring_el),
        )

    def grind_m32(
        self,
        header80: bytes,
        target_be: bytes,
        base_nonce: int,
        lane_order,
        count: int,
    ) -> "HashResult":
        """M32/Turing-order grind in one device pass — no host probe list.

        The canonical traversal (``nonce = base + order[step % 32] +
        32*(step / 32)``) runs on-device from a 32-byte lane LUT: no Python
        nonce list, no Stage A scoring pass, no per-window nonce upload.
        Every digest in the window is physically computed and the winning
        candidate is hashlib-rechecked before returning — same consensus
        contract as ``grind``. Requires ``count % 32 == 0``.
        """
        t0 = time.perf_counter()
        if len(header80) != 80:
            raise ValueError("header must be 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be 32 bytes")
        if count % 32 or base_nonce % 32:
            raise ValueError("m32 grind window and base must be multiples of 32")
        winner, win_hash, hashes = self.hasher.grind_target_m32(
            header80, target_be, base_nonce, lane_order, count
        )
        if winner is not None:
            reference = double_sha256(header80[:76] + struct.pack("<I", int(winner) & 0xFFFFFFFF))
            if win_hash != reference or reference[::-1] > target_be:
                raise RuntimeError("backend candidate failed independent SHA-256d target recheck")
        el = time.perf_counter() - t0
        return HashResult(
            winner,
            win_hash,
            hashes,
            hashes,
            hashes,
            el,
            hashes / el if el > 0 else 0.0,
            self.hasher.backend,
            self.hasher.device,
            "m32-device-order",
            "on-device lane LUT",
            scoring_seconds=0.0,
            hashing_seconds=el,
        )

    def _grind_in_order(
        self,
        header80: bytes,
        target_be: bytes,
        probe_nonces: np.ndarray,
    ):
        """Hash a declared nonce order with bounded device-sized chunks."""
        hashes = 0
        for lo in range(0, int(probe_nonces.size), GPU_BATCH):
            chunk = probe_nonces[lo : lo + GPU_BATCH]
            winner, win_hash, n = self.hasher.grind_target_batch(header80, target_be, chunk)
            hashes += n
            if winner is not None:
                return winner, win_hash, hashes
        return None, None, hashes

    def benchmark_hashrate(
        self,
        header80: bytes,
        target_be: bytes,
        nonce_count: int = 20000,
        duration_s: float = 60.0,
        start_nonce: int = 0,
    ) -> Dict[str, Any]:
        """Measured wall-clock H/s through the active hasher. NOT a projection."""
        t0 = time.perf_counter()
        hashes = 0
        start_nonce = int(start_nonce) & 0xFFFFFFFF
        if self.hasher.backend == "cpu":
            nonce = start_nonce
            while time.perf_counter() - t0 < duration_s and hashes < nonce_count:
                blob = header80[:76] + struct.pack("<I", nonce & 0xFFFFFFFF)
                double_sha256(blob)
                hashes += 1
                nonce = (nonce + 1) & 0xFFFFFFFF
        else:
            # The grind path itself: on-device nonce derivation and first-hit
            # reduction when available (4-byte readback), hits-only otherwise.
            # Every digest is physically computed; hashes counts real work.
            range_grind = getattr(self.hasher, "grind_target_range", None)
            while time.perf_counter() - t0 < duration_s and hashes < nonce_count:
                take = min(GPU_BATCH, nonce_count - hashes)
                batch_start = (start_nonce + hashes) & 0xFFFFFFFF
                if range_grind is not None:
                    range_grind(header80, target_be, batch_start, take)
                else:
                    batch = np.arange(batch_start, batch_start + take, dtype=np.uint64)
                    self.hasher.grind_target_batch(header80, target_be, batch)
                hashes += take
        el = time.perf_counter() - t0
        kernel_seconds = float(self.hasher.kernel_ms) / 1000.0
        return {
            "measured_hps": hashes / el if el > 0 else 0.0,
            "hashes": hashes,
            "elapsed_seconds": el,
            "dispatch_overhead_seconds": (
                max(0.0, el - kernel_seconds) if self.hasher.backend.startswith("opencl") else None
            ),
            "backend": self.hasher.backend,
            "kernel_config": {"batch": GPU_BATCH, "backend_request": self._hasher_backend},
            "device": self.hasher.device,
            "scoring_backend": self.scoring_backend,
            "start_nonce": start_nonce,
            "kernel_ms": self.hasher.kernel_ms,
            "launches": self.hasher.launches,
            "truth_class": "measured",
        }

    def _backend(self) -> str:
        try:
            return self.hasher.backend
        except Exception:
            return "cpu"

    def _device(self) -> str:
        try:
            return self.hasher.device
        except Exception:
            return "cpu"


def resubmit_with_jitter(header_seed: bytes, prev_nonce: int, attempt: int) -> int:
    """Seeded jitter for resubmit (workflow 3.04). Deterministic."""
    digest = hashlib.sha256(
        header_seed + struct.pack("<II", prev_nonce & 0xFFFFFFFF, attempt)
    ).digest()
    return int.from_bytes(digest[:4], "little")
