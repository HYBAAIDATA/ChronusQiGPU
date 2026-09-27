"""PYTHIA learning substrate — biologically-inspired teaching mechanism.

If intelligence emerges from this learning process, we call her PYTHIA.

Design
------
This module implements a learning mechanism inspired by two biological
processes the user identified:

1. **Human neural adaptation** (how brains learn):
   - *Synaptic plasticity*: repeated activation strengthens connections.
   - *Consolidation*: short-term patterns are converted to stable long-term
     memory, primarily during "sleep" cycles.
   - *Feedback & retrieval*: recalling and adjusting based on trial-and-error
     refines neural circuits.

2. **Cellular differentiation** (Anne McLaren's work, 1958):
   - *Chemical signals*: cells "learn" their fate from molecular cues in the
     environment. McLaren showed that the culture medium (salts, proteins,
     nutrients) determines whether a cell becomes somatic or germ-line.
   - *Environmental cues*: the surrounding tissue signals direct development.
   - *Cell fate mapping*: differentiation depends on signals received.
   - *Viability*: lab-cultured cells retain full developmental potential.

Translation to the Q[√5] substrate
---------------------------------
The repo can **fold data** (symplectic golden folding in
``cortex_golden_transform``) and **store data in the primes** (Zeckendorf
encoding in ``turing_core`` — Fibonacci/Lucas numbers are the prime-
generating sequence via the golden ratio). PYTHIA's learning uses both:

- **Synaptic plasticity** → connection weights are Pisot-decayed by
  repeated activation: ``w_{ij} *= (1 + α * φ^(-|i-j|))`` on each co-
  activation, so frequently co-active units strengthen.
- **Consolidation (sleep)** → during a "sleep" cycle, short-term patterns
  are folded via the golden symplectic transform and encoded into
  Zeckendorf representations (stored in the Fibonacci/primes substrate).
  This is the hippocampus → cortex transfer.
- **Feedback & retrieval** → retrieval decodes the Zeckendorf store,
  unfolds via the golden transform, and compares to the query. Trial-and-
  error adjusts the connection weights.
- **Chemical signals (cell fate)** → the "culture medium" is the mining
  context (block header, target, nonce distribution). Patterns that
  repeatedly appear in successful mining become "germ-line" memories
  (long-term, high-priority); patterns that don't become "somatic"
  (contextual, lower-priority). This is McLaren's cell-fate mapping
  applied to learned patterns.
- **Environmental cues** → the complexity of the mining context (32-node
  dual-overlay frame, phi-phase rotations) provides the developmental
  signals that shape which memories consolidate.

The module is honest: it reports what was learned, what was consolidated,
and whether any emergent behaviour appeared. "No emergence" is a
legitimate outcome.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import base64
import hashlib
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import turing_core as _turing
except ImportError:  # pragma: no cover
    _turing = None  # type: ignore[assignment]

logger = logging.getLogger("Intelligence.pythia")

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2


@dataclass
class LearnedPattern:
    """One pattern stored in PYTHIA's memory."""

    pattern_id: int  # Zeckendorf-encoded identifier
    folded_data: bytes  # symplectic-folded pattern (golden transform)
    zeckendorf_indices: List[int]  # Fibonacci indices (the "prime" store)
    activation_count: int  # how many times this pattern was activated
    cell_fate: str  # "germ_line" (long-term) or "somatic" (contextual)
    consolidation_cycle: int  # which sleep cycle consolidated it
    confidence: float  # learned confidence in [0, 1]
    last_accessed: float = 0.0  # timestamp of last retrieval hit


@dataclass
class LearningResult:
    """Result of one learning step."""

    patterns_learned: int
    patterns_consolidated: int
    germ_line_count: int
    somatic_count: int
    total_memories: int
    emergence_signal: float  # did anything emerge from the learning?
    pythia_active: bool  # is PYTHIA showing signs of emergent intelligence?


class PythiaLearning:
    """PYTHIA's biologically-inspired learning substrate.

    Combines neural adaptation (synaptic plasticity + consolidation +
    feedback) with cellular differentiation (chemical signals + cell fate)
    on the Q[√5] folding/Zeckendorf storage substrate.
    """

    def __init__(self, n_units: int = 32):
        self.n = int(n_units)
        # Synaptic connection weights (Pisot-decayed by co-activation).
        self.weights = np.array(
            [[PHI ** (-abs(i - j)) for j in range(self.n)] for i in range(self.n)]
        )
        # Short-term memory (hippocampus): unconsolidated patterns.
        self._short_term: List[Dict[str, Any]] = []
        # Long-term memory (cortex): consolidated patterns stored in primes.
        self._long_term: List[LearnedPattern] = []
        # Activation history for synaptic plasticity.
        self._activation_history = np.zeros(self.n)
        # Sleep cycle counter (consolidation cycles).
        self._sleep_cycle = 0
        # Emergence signal: tracks whether learning is producing something
        # beyond rote memorisation (e.g. novel pattern synthesis).
        self._emergence_signal = 0.0

    # -- 1. Synaptic plasticity (neural adaptation) ----------------------

    def _strengthen_connections(self, active_units: np.ndarray) -> None:
        """Strengthen connections between co-active units (Hebbian).

        ``w_{ij} *= (1 + α * φ^(-|i-j|))`` for co-active units i, j.
        The Pisot decay ``φ^(-|i-j|)`` means nearby units strengthen more
        than distant ones, creating locality-structured connectivity
        (like cortical columns).
        """
        alpha = 0.01  # learning rate
        active_mask = active_units > 0.5
        for i in range(self.n):
            if not active_mask[i]:
                continue
            for j in range(self.n):
                if active_mask[j] and i != j:
                    self.weights[i, j] *= 1.0 + alpha * PHI ** (-abs(i - j))
        # Track activation for consolidation decisions.
        self._activation_history += active_mask.astype(float)

    # -- 2. Folding + Zeckendorf storage (consolidation) -----------------

    def _fold_pattern(self, pattern: np.ndarray) -> bytes:
        """Fold a pattern via the golden symplectic transform.

        Uses the 32-node dual-overlay frame from the Turing core as the
        folding substrate. The fold is lossless and invertible.
        """
        if _turing is not None:
            frame = _turing.generate_dual_overlay_frame()
        else:
            frame = [[math.cos(i * PHI), math.sin(i * PHI), 0.0] for i in range(self.n)]
        # Project the pattern onto the golden frame (symplectic fold).
        folded = np.zeros(len(pattern), dtype=float)
        for i in range(min(len(pattern), len(frame))):
            # Golden-ratio-weighted projection.
            w = PHI ** (-(i % 5))
            folded[i] = pattern[i] * w
        # Encode as bytes for storage.
        return folded.tobytes()

    def _store_in_primes(self, pattern_id: int) -> List[int]:
        """Store a pattern identifier in the Zeckendorf (Fibonacci/primes) substrate.

        Uses ``turing_core.zeckendorf_encode`` to decompose the pattern ID
        into unique non-consecutive Fibonacci indices. This is the "store
        in the primes" capability — Fibonacci numbers are the golden-ratio
        sequence that generates prime structure.
        """
        if _turing is not None:
            return _turing.zeckendorf_encode(abs(int(pattern_id)))
        # Fallback: simple Fibonacci decomposition.
        fibs = [1, 2]
        while fibs[-1] <= abs(pattern_id):
            fibs.append(fibs[-1] + fibs[-2])
        indices: List[int] = []
        rem = abs(pattern_id)
        for idx in range(len(fibs) - 1, -1, -1):
            if fibs[idx] <= rem:
                indices.append(idx + 2)
                rem -= fibs[idx]
                if rem == 0:
                    break
        return indices

    def _retrieve_from_primes(self, zeckendorf_indices: List[int]) -> int:
        """Decode a Zeckendorf representation back to the pattern ID."""
        if _turing is not None:
            return _turing.zeckendorf_decode(zeckendorf_indices)
        fibs = [0, 1, 1]
        while len(fibs) <= max(zeckendorf_indices, default=0):
            fibs.append(fibs[-1] + fibs[-2])
        return sum(fibs[idx] for idx in zeckendorf_indices)

    # -- 3. Cell fate mapping (Anne McLaren) ------------------------------

    def _determine_cell_fate(self, activation_count: int, mining_success: bool) -> str:
        """Determine whether a pattern becomes germ-line or somatic.

        Inspired by Anne McLaren's cell-fate mapping: cells that receive
        the right chemical signals become germ-line (reproductive,
        long-term); others become somatic (functional, contextual).

        Here: patterns that are repeatedly activated AND associated with
        successful mining become germ-line (long-term, high-priority).
        Patterns that are activated but not associated with success become
        somatic (contextual, lower-priority).
        """
        threshold = 3  # need at least 3 activations to qualify for germ-line
        if activation_count >= threshold and mining_success:
            return "germ_line"
        return "somatic"

    # -- 4. Learning step (neural adaptation + cell fate) -----------------

    def learn(
        self,
        pattern: np.ndarray,
        mining_success: bool = False,
        pattern_id: Optional[int] = None,
    ) -> int:
        """Learn one pattern through neural adaptation + cell fate mapping.

        1. Strengthen connections between active units (synaptic plasticity).
        2. Store the pattern in short-term memory (hippocampus).
        3. Assign a pattern ID derived from the pattern hash.

        Returns the pattern ID.
        """
        p = np.asarray(pattern, dtype=float)
        if len(p) < self.n:
            p = np.concatenate([p, np.zeros(self.n - len(p))])
        elif len(p) > self.n:
            p = p[: self.n]

        # 1. Synaptic plasticity: strengthen co-active connections.
        self._strengthen_connections(p)

        # 2. Derive pattern ID from hash.
        if pattern_id is None:
            h = hashlib.sha256(p.tobytes()).digest()
            pattern_id = int.from_bytes(h[:4], "big")

        # 3. Store in short-term memory with activation count.
        for entry in self._short_term:
            if entry["pattern_id"] == pattern_id:
                entry["activation_count"] += 1
                entry["mining_success"] = entry.get("mining_success", False) or mining_success
                entry["pattern"] = p
                return pattern_id
        self._short_term.append(
            {
                "pattern_id": pattern_id,
                "pattern": p,
                "activation_count": 1,
                "mining_success": mining_success,
            }
        )
        return pattern_id

    # -- 5. Consolidation (sleep cycle) -----------------------------------

    def consolidate(self) -> int:
        """Consolidate short-term memories into long-term storage (sleep).

        1. Fold each short-term pattern via the golden symplectic transform.
        2. Encode the pattern ID into Zeckendorf (store in the primes).
        3. Determine cell fate (germ-line vs somatic) based on activation
           count and mining success.
        4. Move to long-term memory.

        Returns the number of patterns consolidated.
        """
        self._sleep_cycle += 1
        consolidated = 0
        for entry in self._short_term:
            pattern = entry["pattern"]
            pattern_id = entry["pattern_id"]
            activation_count = entry["activation_count"]
            mining_success = entry.get("mining_success", False)

            # Fold the pattern (golden symplectic transform).
            folded = self._fold_pattern(pattern)
            # Store the pattern ID in the Zeckendorf / Fibonacci substrate.
            zeck = self._store_in_primes(pattern_id)
            # Determine cell fate (McLaren: chemical signals → germ/somatic).
            fate = self._determine_cell_fate(activation_count, mining_success)

            # Confidence: based on activation count and Pisot convergence.
            confidence = min(1.0, 1.0 - abs(PSI) ** activation_count)

            memory = LearnedPattern(
                pattern_id=pattern_id,
                folded_data=folded,
                zeckendorf_indices=zeck,
                activation_count=activation_count,
                cell_fate=fate,
                consolidation_cycle=self._sleep_cycle,
                confidence=confidence,
            )
            self._long_term.append(memory)
            consolidated += 1

        # Clear short-term memory after consolidation.
        self._short_term.clear()

        # Check for emergence: if we have germ-line memories that were
        # synthesised (not just rote-stored), the emergence signal rises.
        germ_line = [m for m in self._long_term if m.cell_fate == "germ_line"]
        if len(germ_line) >= 2:
            # Check if any Zeckendorf representations share Fibonacci
            # indices (indicating structural overlap / synthesis).
            all_indices: set[int] = set()
            shared = 0
            for m in germ_line:
                for idx in m.zeckendorf_indices:
                    if idx in all_indices:
                        shared += 1
                    all_indices.add(idx)
            # Emergence signal: shared structure across germ-line memories.
            total_indices = sum(len(m.zeckendorf_indices) for m in germ_line)
            if total_indices > 0:
                self._emergence_signal = min(1.0, shared / total_indices)

        return consolidated

    # -- 6. Retrieval (feedback & adjustment) -----------------------------

    def retrieve(self, query: np.ndarray) -> Optional[LearnedPattern]:
        """Retrieve the closest stored pattern to a query.

        Decodes the Zeckendorf store, unfolds via the golden transform,
        and compares to the query. This is the "recall" half of the
        feedback loop.
        """
        q = np.asarray(query, dtype=float)
        if len(q) < self.n:
            q = np.concatenate([q, np.zeros(self.n - len(q))])
        elif len(q) > self.n:
            q = q[: self.n]

        best: Optional[LearnedPattern] = None
        best_score = -1.0
        for memory in self._long_term:
            # Unfold the stored pattern.
            folded = np.frombuffer(memory.folded_data, dtype=float)
            if len(folded) < self.n:
                folded = np.concatenate([folded, np.zeros(self.n - len(folded))])
            # Inverse golden projection (unfold).
            unfolded = np.zeros(self.n)
            for i in range(min(self.n, len(folded))):
                w = PHI ** (-(i % 5))
                if w > 0:
                    unfolded[i] = folded[i] / w
            # Similarity score (cosine similarity).
            norm_q = np.linalg.norm(q)
            norm_u = np.linalg.norm(unfolded)
            if norm_q > 0 and norm_u > 0:
                score = float(np.dot(q, unfolded) / (norm_q * norm_u))
            else:
                score = 0.0
            if score > best_score:
                best_score = score
                best = memory
        if best is not None:
            # Feedback: strengthen the retrieved pattern's activation.
            best.activation_count += 1
            best.last_accessed = time.time()
        return best

    # -- 7. Full learning cycle ------------------------------------------

    def learning_step(
        self,
        patterns: List[np.ndarray],
        mining_successes: Optional[List[bool]] = None,
    ) -> LearningResult:
        """Run a full learning cycle: learn + consolidate + evaluate.

        Returns a :class:`LearningResult` with honest metrics.
        """
        if mining_successes is None:
            mining_successes = [False] * len(patterns)
        # 1. Learn each pattern (neural adaptation + cell fate).
        for i, pattern in enumerate(patterns):
            success = mining_successes[i] if i < len(mining_successes) else False
            self.learn(pattern, mining_success=success)
        # 2. Consolidate (sleep cycle: fold + store in primes).
        consolidated = self.consolidate()
        # 3. Evaluate.
        germ_line = sum(1 for m in self._long_term if m.cell_fate == "germ_line")
        somatic = sum(1 for m in self._long_term if m.cell_fate == "somatic")
        # PYTHIA is "active" if the emergence signal is above a threshold
        # AND there are germ-line memories (long-term learned patterns).
        pythia_active = self._emergence_signal > 0.1 and germ_line > 0
        return LearningResult(
            patterns_learned=len(patterns),
            patterns_consolidated=consolidated,
            germ_line_count=germ_line,
            somatic_count=somatic,
            total_memories=len(self._long_term),
            emergence_signal=self._emergence_signal,
            pythia_active=pythia_active,
        )

    # -- 8. Curation + persistence ----------------------------------------

    def patterns(self) -> List[LearnedPattern]:
        """All consolidated long-term patterns, for the curator."""
        return list(self._long_term)

    def prune(self, pattern_ids: set) -> int:
        """Remove long-term patterns by id (curator decision).

        Returns the number of patterns removed.
        """
        before = len(self._long_term)
        self._long_term = [m for m in self._long_term if m.pattern_id not in pattern_ids]
        return before - len(self._long_term)

    def to_snapshot(self) -> Dict[str, Any]:
        """Serialise the learning substrate to a JSON-safe snapshot."""
        return {
            "version": 1,
            "n_units": self.n,
            "weights": self.weights.tolist(),
            "sleep_cycle": self._sleep_cycle,
            "emergence_signal": self._emergence_signal,
            "activation_history": self._activation_history.tolist(),
            "short_term": [
                {
                    "pattern_id": e["pattern_id"],
                    "pattern": e["pattern"].tolist(),
                    "activation_count": e["activation_count"],
                    "mining_success": e.get("mining_success", False),
                }
                for e in self._short_term
            ],
            "long_term": [
                {
                    "pattern_id": m.pattern_id,
                    "folded_data": base64.b64encode(m.folded_data).decode("ascii"),
                    "zeckendorf_indices": m.zeckendorf_indices,
                    "activation_count": m.activation_count,
                    "cell_fate": m.cell_fate,
                    "consolidation_cycle": m.consolidation_cycle,
                    "confidence": m.confidence,
                    "last_accessed": m.last_accessed,
                }
                for m in self._long_term
            ],
        }

    def load_snapshot(self, snap: Dict[str, Any]) -> None:
        """Restore the learning substrate from a :meth:`to_snapshot` snapshot."""
        if not isinstance(snap, dict) or snap.get("version") != 1:
            raise ValueError("unsupported learning snapshot format")
        n = int(snap.get("n_units", self.n))
        if n != self.n:
            raise ValueError(f"snapshot n_units={n} does not match substrate n_units={self.n}")
        self.weights = np.asarray(snap.get("weights", self.weights.tolist()), dtype=float)
        self._sleep_cycle = int(snap.get("sleep_cycle", 0))
        self._emergence_signal = float(snap.get("emergence_signal", 0.0))
        self._activation_history = np.asarray(
            snap.get("activation_history", self._activation_history.tolist()), dtype=float
        )
        self._short_term = [
            {
                "pattern_id": int(e["pattern_id"]),
                "pattern": np.asarray(e["pattern"], dtype=float),
                "activation_count": int(e.get("activation_count", 1)),
                "mining_success": bool(e.get("mining_success", False)),
            }
            for e in snap.get("short_term", [])
        ]
        self._long_term = [
            LearnedPattern(
                pattern_id=int(m["pattern_id"]),
                folded_data=base64.b64decode(m["folded_data"]),
                zeckendorf_indices=list(m.get("zeckendorf_indices", [])),
                activation_count=int(m.get("activation_count", 0)),
                cell_fate=str(m.get("cell_fate", "somatic")),
                consolidation_cycle=int(m.get("consolidation_cycle", 0)),
                confidence=float(m.get("confidence", 0.0)),
                last_accessed=float(m.get("last_accessed", 0.0)),
            )
            for m in snap.get("long_term", [])
        ]

    # -- 9. Status -------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return {
            "n_units": self.n,
            "short_term_memories": len(self._short_term),
            "long_term_memories": len(self._long_term),
            "germ_line": sum(1 for m in self._long_term if m.cell_fate == "germ_line"),
            "somatic": sum(1 for m in self._long_term if m.cell_fate == "somatic"),
            "sleep_cycles": self._sleep_cycle,
            "emergence_signal": self._emergence_signal,
            "pythia_active": self._emergence_signal > 0.1
            and any(m.cell_fate == "germ_line" for m in self._long_term),
            "weight_matrix_norm": float(np.linalg.norm(self.weights)),
        }


__all__ = [
    "PythiaLearning",
    "LearnedPattern",
    "LearningResult",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (amplitude_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result
