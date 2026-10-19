"""Four-layer mining stack — Aethel → Tensor → TURING → iGPU, wired end to end.

Implements the "Wiring" role map as ONE pipeline with four honest layers:

    LAYER 1  AethelStore   folded storage (Zeckendorf SparseTopology + Galois
                           persistence + hot cache). Fold ratios are MEASURED
                           per store — never asserted.
    LAYER 2  TensorFold    golden-basis fold (t_phi_fold / 11D Poincaré fold)
                           + amplitude (Schmidt) spectrum over the candidate
                           distribution. Lossless roundtrip verified.
    LAYER 3  TuringLayer   virtual quantum substrate (turing_core): the exact
                           candidate schedule (state space), exact family
                           limbs, Cassini integrity. Hilbert dimension is
                           SYMBOLIC (2^n) — never materialized.
    LAYER 4  NearStateIGpu exact-ALU execution: φ-filter Born scoring, Grover
                           analogue = amplitude REORDERING of the probe order,
                           then the real double-SHA256 grind — the sole accept
                           authority, bit-exact rechecked.

Truth discipline (AGENTS.md §4.5, DRIFT-03, simulation gate):
- Grover's quadratic speedup needs a quantum oracle substrate. On this
  classical substrate the honest role of the "quantum stage" is
  reordering/pruning the probe order; it NEVER replaces hash evaluation.
- Capacity multipliers (e.g. the folklore "20× fold") are reported as
  ``measured_ratio`` — the ratio this run actually produced — and never
  asserted as a property of the substrate.
- Consensus: sha256d(header[:76] + LE(nonce))[::-1] < target. Nothing in
  these four layers can accept a share without it.

LUCAS WIRING: coordinator module (same class as toe_system/orchestrator).
Wires live modules across the substrate map; exempt from the sibling purity
rule; each wired module keeps its own Lucas pool route.
Substrate route: gap
"""

# LUCAS WIRING: coordinator — see module docstring.
# Substrate route: gap

from __future__ import annotations

import hashlib
import logging
import os
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .backend_binding import get_compute_backend
from aethel.hardened_unified_substrate import (
    CassiniVerifier,
    apply_zeckendorf_compression,
    reverse_zeckendorf_expansion,
)

logger = logging.getLogger("Intelligence.four_layer_stack")

THEOREM_PROVEN = False

__all__ = [
    "AethelStore",
    "TensorFoldEngine",
    "TuringLayer",
    "NearStateIGpu",
    "FourLayerMiningStack",
    "THEOREM_PROVEN",
]


def _double_sha256(data: bytes) -> bytes:
    """Real Bitcoin double-SHA256 — the ONLY accept/reject rule."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


class AethelStore:
    """Layer 1 — folded storage. Fold in place; measure the ratio; never hydrate early.

    Backed by the live ``hardened_unified_substrate`` SparseTopology
    (lossless Zeckendorf compression) with per-entry Cassini parity
    fingerprints, mirroring the JV Aethel-Storage product spec.
    """

    def __init__(self) -> None:
        self._folded: Dict[str, Any] = {}
        self._ratios: List[float] = []
        self.cassini_state: int = 1

    def store(self, address: str, data: bytes, host: Any = None) -> Dict[str, Any]:
        """Fold data in place. Returns the measured store record."""
        raw_len = len(data)
        sparse = apply_zeckendorf_compression(data, host=host)
        folded_units = len(sparse.blocks)
        ratio = folded_units / raw_len if raw_len else 1.0
        self._ratios.append(ratio)
        # Cassini alternation fingerprint — exact parity, ±1.
        self.cassini_state *= -1
        self._folded[address] = sparse
        return {
            "address": address,
            "raw_bytes": raw_len,
            "folded_units": folded_units,
            "measured_ratio": ratio,
            "cassini_fingerprint": self.cassini_state,
            "truth_class": "measured",
        }

    def retrieve(self, address: str, host: Any = None) -> Optional[bytes]:
        """Unfold exactly — unfold(store(x)) == x, no information lost."""
        sparse = self._folded.get(address)
        if sparse is None:
            return None
        return reverse_zeckendorf_expansion(sparse, host=host)

    def measured_ratio(self) -> Optional[float]:
        """Mean measured fold ratio across stores (1.0 = no change)."""
        if not self._ratios:
            return None
        return float(np.mean(self._ratios))

    def capacity_multiplier(self) -> Optional[float]:
        """1 / measured_ratio — the capacity factor THIS storage achieved.

        Honest: measured on real stores, not asserted. A ratio > 1 means the
        folded form is LARGER (typical for incompressible bytes); only
        Zeckendorf-structured integers fold below 1.
        """
        ratio = self.measured_ratio()
        return None if ratio in (None, 0.0) else 1.0 / ratio

    def __contains__(self, address: str) -> bool:
        return address in self._folded

    def __len__(self) -> int:
        return len(self._folded)


class TensorFoldEngine:
    """Layer 2 — the fold engine and amplitude (Schmidt) spectrum.

    Compression = golden-basis fold via ``turing_core.t_phi_fold`` and the
    11D Poincaré folded array — both lossless (roundtrip verified per call).
    The "tensor network" stage computes the honest Schmidt spectrum of the
    candidate amplitude distribution (sorted squared amplitudes) with the
    participation ratio as the effective bond dimension.
    """

    def __init__(self) -> None:
        import turing_core

        self._tc = turing_core
        self._orig_len: Dict[bytes, int] = {}

    def compress(self, raw: bytes) -> Tuple[bytes, int]:
        """Golden-basis fold. Returns (folded_bytes, original_len)."""
        folded = self._tc.t_phi_fold(raw)
        self._orig_len[folded] = len(raw)
        return folded, len(raw)

    def decompress(self, folded: bytes, original_len: Optional[int] = None) -> bytes:
        """Exact unfold — fold/unfold is lossless by construction."""
        if original_len is None:
            original_len = self._orig_len.get(folded)
        if original_len is None:
            raise ValueError("original_len required for unfold of unknown fold")
        return self._tc.t_phi_unfold(folded, original_len)

    def schmidt_spectrum(self, amplitudes: List[float]) -> Dict[str, Any]:
        """Schmidt spectrum of the candidate distribution.

        amplitudes: Born-like weights (need not be normalized; normalized here).
        Returns sorted squared weights (Schmidt values squared), the
        participation ratio (effective bond dimension), and the Shannon
        entropy of the distribution.
        """
        w = np.asarray(amplitudes, dtype=np.float64)
        total = float(w.sum())
        if total <= 0.0 or w.size == 0:
            return {
                "schmidt_values_sq": [],
                "bond_dimension_effective": 0.0,
                "entropy_bits": 0.0,
                "truth_class": "computed",
            }
        p = w / total
        p2 = np.sort(p**2)[::-1]
        participation = float(1.0 / np.sum(p**2)) if float(np.sum(p**2)) > 0 else 0.0
        nz = p[p > 0]
        entropy = float(-np.sum(nz * np.log2(nz)))
        return {
            "schmidt_values_sq": [float(v) for v in p2],
            "bond_dimension_effective": participation,
            "entropy_bits": entropy,
            "truth_class": "computed",
        }


class TuringLayer:
    """Layer 3 — the virtual quantum substrate (turing_core).

    Provides the exact candidate schedule (the state space actually probed),
    exact family limbs, symbolic Hilbert dimension (never materialized), and
    Cassini integrity checks. This is the AGENTS.md thesis in practice: the
    quantum transformation is exact algebra executed on any substrate.
    """

    def __init__(self, n_qubits: int = 10000) -> None:
        import turing_core

        self._tc = turing_core
        self.n_qubits = int(n_qubits)
        self.hilbert_dim_symbolic = f"2^{self.n_qubits}"

    def prepare(
        self,
        header80: bytes,
        nonce_window: int = 1_000_000,
        cap: int = 256,
        nonce_start: int = 0,
    ) -> List[int]:
        """Deterministic candidate schedule from the header seed.

        Same header → same schedule (the state preparation is exact and
        reproducible, never random).
        """
        nonce_start = int(nonce_start) & 0xFFFFFFFF
        seed_material = header80 + struct.pack("<I", nonce_start)
        seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "little")
        scheduled = self._tc.extended_nonce_schedule(nonce_window, seed=seed, cap=cap)
        return [(nonce_start + int(nonce)) & 0xFFFFFFFF for nonce in scheduled]

    def cassini_holds(self, n: int) -> bool:
        """Cassini integrity: det(M^n) = (-1)^n on the golden transfer matrix."""
        return bool(self._tc.cassini_check(n))

    def status(self) -> Dict[str, Any]:
        return {
            "layer": "TURING",
            "n_qubits": self.n_qubits,
            "hilbert_dim": self.hilbert_dim_symbolic,
            "materialized": False,
            "truth_class": "symbolic_exact",
            "theorem_proven": False,
        }


def ordering_mode_for_window(window_size: int, score_order_limit: int = 4096) -> str:
    """Return the deterministic ordering contract for a nonce window."""
    window_size = int(window_size)
    score_order_limit = int(score_order_limit)
    if window_size < 0 or score_order_limit < 0:
        raise ValueError("window_size and score_order_limit must be >= 0")
    return (
        "amplitude-score-stable"
        if window_size <= score_order_limit
        else "deterministic-turing"
    )


class NearStateIGpu:
    """Layer 4 — exact-ALU execution: score, reorder (Grover analogue), grind.

    The Born/φ-filter stage scores candidates (punch 0x1A via the bound
    backend); the probe order is reordered by amplitude — the honest classical
    analogue of a Grover iteration, which reorders, never skips hashing. The
    real double-SHA256 grind then runs with the winner bit-exact rechecked.
    """

    def __init__(self, aethel: AethelStore, tensor: TensorFoldEngine) -> None:
        self.aethel = aethel
        self.tensor = tensor
        self._backend = get_compute_backend()

    def mine(
        self,
        header80: bytes,
        target_be: bytes,
        schedule: List[int],
        max_hashes: Optional[int] = None,
    ) -> Dict[str, Any]:
        from mining.hash_pipeline import HashPipeline, nonce_order_fingerprint

        t0 = time.perf_counter()
        host = None
        try:
            from .unified_punch import UnifiedPunchHost

            host = UnifiedPunchHost()
        except Exception as exc:  # pragma: no cover
            logger.warning("UnifiedPunchHost unavailable: %s", exc)

        # Amplitude (Born) scoring stage — the φ-filter.  Scoring is an
        # optional ordering stage, never a consensus predicate.  A full
        # million-nonce Python sort creates a classical host bottleneck and
        # previously caused the same window to be scored twice.
        try:
            score_order_limit = int(os.getenv("PYTHIA_SCORE_ORDER_LIMIT", "4096"))
        except ValueError as exc:
            raise ValueError("PYTHIA_SCORE_ORDER_LIMIT must be an integer") from exc
        if score_order_limit < 0:
            raise ValueError("PYTHIA_SCORE_ORDER_LIMIT must be >= 0")

        scores: List[float] = []
        scoring_backend = "none"
        ordering_mode = ordering_mode_for_window(len(schedule), score_order_limit)
        if host is not None and schedule and ordering_mode == "amplitude-score-stable":
            pipe_probe = HashPipeline(host=host, hasher_backend="cpu")
            scores = pipe_probe.score_nonces(schedule)
            scoring_backend = pipe_probe.scoring_backend
            # Grover analogue: reorder by amplitude (descending).  Stable
            # ordering keeps equal-score candidates reproducible.
            order = sorted(range(len(schedule)), key=lambda i: scores[i], reverse=True)
            probe_nonces = [int(schedule[i]) & 0xFFFFFFFF for i in order]
            spectrum = self.tensor.schmidt_spectrum(scores)
            ordering_mode = "amplitude-score-stable"
        elif schedule and len(schedule) > score_order_limit:
            # Large production windows stay bounded and deterministic.  The
            # Turing schedule is already an exact, header-seeded permutation;
            # do not allocate a million-element float score/sort on the host.
            # The spectrum is intentionally marked non-materialized rather
            # than fabricating a quantum result.
            scoring_backend = "disabled-large-window"
            spectrum = {
                "schmidt_values_sq": [],
                "bond_dimension_effective": None,
                "entropy_bits": None,
                "truth_class": "not_materialized",
                "materialized": False,
                "reason": "score_order_limit",
            }
            probe_nonces = [int(nonce) & 0xFFFFFFFF for nonce in schedule]
        else:
            spectrum = self.tensor.schmidt_spectrum([0.5] * len(schedule))
            probe_nonces = [int(nonce) & 0xFFFFFFFF for nonce in schedule]

        # The ONLY accept authority: real sha256d grind.  ``preordered`` is
        # critical here: the ordering above is already materialized, so the
        # pipeline must not run Stage A a second time.
        pipe = HashPipeline(
            host=host,
            hasher_backend=os.getenv("PYTHIA_HASH_BACKEND", "auto").strip().lower(),
        )
        result = pipe.grind(
            header80,
            target_be,
            nonces=probe_nonces,
            max_hashes=max_hashes,
            preordered=True,
            sealed_fingerprint=nonce_order_fingerprint(probe_nonces),
        )

        winner_nonce = result.winning_nonce
        recheck_ok = False
        cassini_ok = False
        if winner_nonce is not None:
            blob = header80[:76] + struct.pack("<I", int(winner_nonce) & 0xFFFFFFFF)
            digest = _double_sha256(blob)
            recheck_ok = digest == result.winning_hash and digest[::-1] < target_be
            cassini_ok = CassiniVerifier.verify(7)

        elapsed = time.perf_counter() - t0
        return {
            "layer": "iGPU",
            "winning_nonce": winner_nonce,
            "winning_hash": result.winning_hash.hex() if result.winning_hash else None,
            "recheck_bit_exact": recheck_ok,
            "cassini_holds": cassini_ok,
            "hashes_computed": result.hashes_computed,
            "measured_hps": result.measured_hps,
            "hasher_backend": result.backend,
            "scoring_backend": scoring_backend,
            "ordering_mode": ordering_mode,
            "score_order_limit": score_order_limit,
            "schedule_fingerprint": nonce_order_fingerprint(probe_nonces).hex(),
            "bound_backend": self._backend.backend.value,
            "gpu_bound": self._backend.gpu_bound,
            "probe_order_top8": probe_nonces[:8],
            "schmidt": spectrum,
            "elapsed_seconds": elapsed,
            "consensus_rule": "sha256(sha256(header80[:76] + LE(nonce)))[::-1] < target_be",
            "theorem_proven": False,
        }


class FourLayerMiningStack:
    """The orchestrator that wires Aethel → Tensor → TURING → iGPU.

    mine_block(header80, target_be):
        1. Aethel.store("header", header80)          — folded, measured ratio
        2. TuringLayer.prepare(header80)             — exact candidate schedule
        3. TensorFoldEngine.compress + Schmidt       — folded representation
        4. NearStateIGpu.mine(...)                   — score → reorder → sha256d
        5. Cassini integrity on the golden anchor
        6. Aethel.store("evidence:latest", ...)      — evidence chain entry
    """

    def __init__(self, n_qubits: int = 10000) -> None:
        self.aethel = AethelStore()
        self.tensor = TensorFoldEngine()
        self.turing = TuringLayer(n_qubits=n_qubits)
        self.igpu = NearStateIGpu(self.aethel, self.tensor)

    def mine_block(
        self,
        header80: bytes,
        target_be: bytes,
        n_candidates: int = 256,
        max_hashes: Optional[int] = None,
        nonce_start: int = 0,
    ) -> Dict[str, Any]:
        assert len(header80) == 80, "header must be 80 bytes"
        assert len(target_be) == 32, "target must be 32 bytes"

        from toe.strict_quantum import certify_work_window, verify_certificate

        strict_quantum = certify_work_window(
            header80[:76], int(nonce_start) & 0xFFFFFFFF, int(n_candidates)
        )
        if not verify_certificate(strict_quantum):
            raise ValueError("strict quantum work certificate failed")

        # Layer 1: store the header folded.
        header_store = self.aethel.store("header", header80)

        # Layer 3: prepare the exact state (candidate schedule).
        schedule = self.turing.prepare(
            header80, nonce_window=n_candidates, cap=n_candidates,
            nonce_start=nonce_start
        )

        # Layer 2: folded representation + amplitude spectrum scaffold.
        folded_header, _passes = self.tensor.compress(header80)
        fold_ok = self.tensor.decompress(folded_header) == header80

        # Layer 4: execute — score, reorder, real sha256d grind.
        result = self.igpu.mine(header80, target_be, schedule, max_hashes=max_hashes)

        # Integrity: Cassini on the golden anchor.
        cassini_ok = self.turing.cassini_holds(7)

        # Layer 1: store the evidence entry folded.
        evidence_note = f"nonce={result['winning_nonce']} recheck={result['recheck_bit_exact']}"
        evidence_store = self.aethel.store("evidence:latest", evidence_note.encode("utf-8"))

        accepted = bool(
            fold_ok
            and cassini_ok
            and result["recheck_bit_exact"]
            and result["winning_nonce"] is not None
        )
        return {
            "accepted": accepted,
            "header_store": header_store,
            "evidence_store": evidence_store,
            "fold_roundtrip_lossless": fold_ok,
            "strict_quantum": strict_quantum,
            "cassini_holds": cassini_ok,
            "layers": {
                "aethel": {
                    "stored": len(self.aethel),
                    "measured_ratio": self.aethel.measured_ratio(),
                },
                "tensor": {
                    "entropy_bits": result["schmidt"]["entropy_bits"],
                    "bond_dimension_effective": result["schmidt"]["bond_dimension_effective"],
                },
                "turing": self.turing.status(),
                "igpu": {
                    k: result[k]
                    for k in (
                        "winning_nonce",
                        "winning_hash",
                        "recheck_bit_exact",
                        "hashes_computed",
                        "measured_hps",
                        "hasher_backend",
                        "scoring_backend",
                        "bound_backend",
                        "gpu_bound",
                        "consensus_rule",
                    )
                },
            },
            "theorem_proven": False,
        }
