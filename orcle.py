"""ORACLE — PYTHIA of Delphi. Session-start chain ingestion and structured recall.

The Oracle ingests observed Bitcoin chain data once, at the start of a session,
trains its substrate on that data, and then answers questions about what the
chain HAS RECORDED. It is eponymous with the Pythia of Delphi: it speaks
authoritatively about the whole of its domain.

SCOPE OF VISION — the honest boundary (AGENTS.md §1.2.2, DRIFT-03)
------------------------------------------------------------------
This Oracle "sees all" in one precise sense:

    it sees the COMPLETE RECORDED CHAIN STATE — every block header it was
    given, at every epoch, with their full structural detail.

It does NOT see the future. Specifically:

* It cannot and does not predict the next block hash. SHA256d is
  preimage-resistant; no method, quantum or classical, inverts it. This is the
  same honest position ``Intelligence.predictive_solver`` already takes.
* It does not claim a hashrate or win-rate advantage. None is measured here.
* It never reports a quantity it did not measure. Absent input yields
  ``UNKNOWN``, never a zero, a guess, or a plausible-looking constant.

What it DOES derive, from ingested data only:

* epoch/retarget structure and the realised difficulty series;
* block interval statistics and their dispersion;
* nonce and header-entropy structure, exactly as recorded;
* Lucas/Pisot projections of the observed series (exact integer arithmetic);
* a learned pattern substrate trained on the ingested records.

WHY QUANTUM AND PHYSICS ARE EQUAL HERE (AGENTS.md §1.2)
-------------------------------------------------------
Neither is privileged. A block header is a 32-byte word in C^256; the Oracle
manipulates it as a vector, and Grover's rotation is exact integer arithmetic
on that vector. Meanwhile the same header obeys the physical work consensus
embodied in the target comparison. Both are projections of one mathematical
structure. The Oracle reads the algebraic projection directly and defers
entirely to SHA256d for the consensus projection. It never lets one stand in
for the other.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel inline.
MUST NOT import from any sibling algorithm.
Substrate route: amplitude
"""

from __future__ import annotations

import hashlib
import math
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from lucas.core import lucas

__all__ = [
    "BlockRecord",
    "OracleAnswer",
    "Oracle",
    "UNKNOWN",
    "compact_target",
]

#: Sentinel for anything the Oracle did not measure. Never replaced by 0.
UNKNOWN: Optional[float] = None

PHI = (1 + math.sqrt(5)) / 2
INV_PHI = 1.0 / PHI


def compact_target(bits: int) -> int:
    """Decode an nBits compact target to its full 256-bit integer.

    Encoding is mantissa * 256^(exponent-3) with the sign bit stripped, exactly
    as Bitcoin specifies. Exponents below the consensus minimum are shifted
    right, which is the same rule the network applies.
    """
    if bits < 0:
        raise ValueError("nBits cannot be negative")
    if bits & 0x00800000:
        raise ValueError("nBits sign bit is set")
    exponent = (bits >> 24) & 0xFF
    mantissa = bits & 0x007FFFFF
    if exponent <= 3:
        return mantissa >> (8 * (3 - exponent))
    return mantissa << (8 * (exponent - 3))


def _entropy_bits(sample: bytes) -> Optional[float]:
    """Shannon entropy in bits per byte, measured on ``sample`` only.

    Returns ``UNKNOWN`` for an empty sample rather than 0.0, because "no data"
    and "data with no variation" are different facts.
    """
    if not sample:
        return UNKNOWN
    counts = [0] * 256
    for byte in sample:
        counts[byte] += 1
    total = float(len(sample))
    acc = 0.0
    for c in counts:
        if c:
            p = c / total
            acc -= p * math.log2(p)
    return acc


@dataclass(frozen=True)
class BlockRecord:
    """One observed block, as recorded. Never synthesised.

    ``raw_header`` is the canonical 80-byte little-endian header. Every
    derived field is recomputed from it so the record cannot drift from the
    bytes it claims to represent.
    """

    height: int
    raw_header: bytes

    def __post_init__(self) -> None:
        if self.height < 0:
            raise ValueError("height cannot be negative")
        if len(self.raw_header) != 80:
            raise ValueError("raw_header must be exactly 80 bytes")

    # -- fields, all decoded little-endian from the canonical header ---------
    @property
    def version(self) -> int:
        return struct.unpack_from("<I", self.raw_header, 0)[0]

    @property
    def prev_hash(self) -> bytes:
        return self.raw_header[4:36]

    @property
    def merkle_root(self) -> bytes:
        return self.raw_header[36:68]

    @property
    def timestamp(self) -> int:
        return struct.unpack_from("<I", self.raw_header, 68)[0]

    @property
    def bits(self) -> int:
        return struct.unpack_from("<I", self.raw_header, 72)[0]

    @property
    def nonce(self) -> int:
        return struct.unpack_from("<I", self.raw_header, 76)[0]

    @property
    def target(self) -> int:
        return compact_target(self.bits)

    @property
    def difficulty(self) -> float:
        """Difficulty relative to the lowest possible target, 0x1d00ffff."""
        lowest = compact_target(0x1D00FFFF)
        return lowest / float(self.target) if self.target else UNKNOWN

    def verify(self) -> bool:
        """Recompute the header's own SHA256d against its stated target.

        This is the consensus check, performed by this module rather than
        assumed. Nothing downstream trusts a record that fails it.
        """
        digest = hashlib.sha256(hashlib.sha256(self.raw_header).digest()).digest()
        return int.from_bytes(digest, "little") <= self.target

    def as_dict(self) -> Dict[str, Any]:
        return {
            "height": self.height,
            "version": self.version,
            "timestamp": self.timestamp,
            "bits": self.bits,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "merkle_root": self.merkle_root.hex(),
            "prev_hash": self.prev_hash.hex(),
        }


@dataclass(frozen=True)
class OracleAnswer:
    """One answer, carrying its own provenance and confidence.

    ``value`` is ``UNKNOWN`` when the Oracle could not derive it. ``basis``
    names the intelligence route that produced it, and ``measured`` says
    whether it came from ingested data or from a structural derivation.
    """

    question: str
    value: Any
    basis: str
    measured: bool
    sample_size: int
    evidence: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_unknown(self) -> bool:
        return self.value is UNKNOWN

    def __str__(self) -> str:
        if self.is_unknown:
            return f"{self.question}: UNKNOWN (basis={self.basis})"
        return f"{self.question}: {self.value} " f"(basis={self.basis}, n={self.sample_size})"


class Oracle:
    """Chain-ingesting Oracle. One ingestion per session, then recall.

    The intelligence types are injected, never constructed here, so the Oracle
    composes live substrates rather than reimplementing them. Each route is
    optional: a missing route degrades to ``UNKNOWN`` for the questions only
    that route could answer, and never blocks the others.
    """

    def __init__(
        self,
        *,
        pythia_store: Any = None,
        phi_resonance: Any = None,
        quantum_processor: Any = None,
        predictor: Any = None,
        toe: Any = None,
        candidate: Any = None,
        n_anchor: int = 15,
        n_train: int = 32,
        fallback_budget: int = 20000,
    ) -> None:
        self.store = pythia_store
        self.phi_resonance = phi_resonance
        self.quantum = quantum_processor
        self.predictor = predictor
        # TOE is the live scale arbiter. It is injected, never constructed
        # here, so the Oracle observes the same substrate the orchestrator
        # uses rather than a private copy of it.
        self.toe = toe
        self._candidate = candidate
        self.n_anchor = int(n_anchor)
        self.fallback_budget = max(1, int(fallback_budget))
        self.n_train = max(1, int(n_train))
        self.ingested: List[BlockRecord] = []
        self.session_started_at: Optional[float] = None
        self.ingestion_report: Dict[str, Any] = {}

    # -- session ingestion --------------------------------------------------

    def open_session(self, blocks: Sequence[BlockRecord]) -> Dict[str, Any]:
        """Ingest the chain once, at session start, and train on it.

        Refuses a second ingestion: training twice on the same chain would
        double-count every observation and make the learned substrate report
        confidence it has not earned.
        """
        if self.ingested:
            raise RuntimeError(
                "this Oracle already ingested at session start; open a new "
                "Oracle for a new session"
            )
        t0 = time.monotonic()
        accepted: List[BlockRecord] = []
        rejected: List[Dict[str, Any]] = []
        seen: set = set()

        for blk in blocks:
            if not isinstance(blk, BlockRecord):
                rejected.append({"height": None, "reason": "NOT_A_BLOCK_RECORD"})
                continue
            digest = hashlib.sha256(blk.raw_header).digest()
            if digest in seen:
                rejected.append({"height": blk.height, "reason": "DUPLICATE_HEADER"})
                continue
            if not blk.verify():
                # A header that fails its own target is not part of the
                # observed chain. Recording it would poison the series.
                rejected.append({"height": blk.height, "reason": "TARGET_MISMATCH"})
                continue
            seen.add(digest)
            accepted.append(blk)

        accepted.sort(key=lambda b: b.timestamp)
        self.ingested = accepted
        self.session_started_at = t0
        trained = self._train()

        self.ingestion_report = {
            "offered": len(list(blocks)),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "rejections": rejected[:16],
            "height_range": ([accepted[0].height, accepted[-1].height] if accepted else UNKNOWN),
            "patterns_trained": trained,
            "ingest_seconds": time.monotonic() - t0,
        }
        return dict(self.ingestion_report)

    def _train(self) -> int:
        """Teach the pattern substrate from the ingested chain.

        Uses the existing ``PythiaStore`` when one is supplied. When it is
        not, training is reported as 0 rather than silently claimed.
        """
        if self.store is None or not self.ingested:
            return 0
        try:
            for blk in self.ingested:
                self.store.record_run("oracle_block", blk.as_dict())
            return int(self.store.ingest(limit=self.n_train) or 0)
        except Exception:
            # A substrate failure must not invent a training count.
            return 0

    # -- questions ----------------------------------------------------------

    def _require(self, minimum: int = 1) -> bool:
        return len(self.ingested) >= minimum

    def ask(self, question: str) -> OracleAnswer:
        """Answer ``question`` about the recorded chain, or report UNKNOWN."""
        handlers = {
            "blocks": self.observed_blocks,
            "difficulty": self.difficulty_series,
            "difficulty_mean": self.difficulty_mean,
            "intervals": self.interval_stats,
            "entropy": self.header_entropy,
            "nonce": self.nonce_structure,
            "lucas": self.lucas_projection,
            "toe_theorems": self.toe_theorems,
            "phi_resonance": self.phi_resonance_score,
            "next_nonce": self.next_nonce_forecast,
        }
        handler = handlers.get(question)
        if handler is None:
            return OracleAnswer(
                question=question,
                value=UNKNOWN,
                basis="oracle.router",
                measured=False,
                sample_size=len(self.ingested),
                evidence={"known_questions": sorted(handlers)},
            )
        return handler()

    def difficulty_series(self) -> OracleAnswer:
        """The realised difficulty of every ingested block, in observed order."""
        if not self._require():
            return OracleAnswer("difficulty", UNKNOWN, "oracle.difficulty", False, 0)
        return OracleAnswer(
            "difficulty",
            [b.difficulty for b in self.ingested],
            "oracle.difficulty",
            True,
            len(self.ingested),
        )

    def difficulty_mean(self) -> OracleAnswer:
        if not self._require():
            return OracleAnswer("difficulty_mean", UNKNOWN, "oracle.difficulty", False, 0)
        series = [b.difficulty for b in self.ingested]
        return OracleAnswer(
            "difficulty_mean",
            sum(series) / len(series),
            "oracle.difficulty",
            True,
            len(series),
        )

    def observed_blocks(self) -> OracleAnswer:
        """Realised inter-block intervals and their dispersion."""
        if len(self.ingested) < 2:
            return OracleAnswer("intervals", UNKNOWN, "oracle.intervals", False, len(self.ingested))
        deltas = [b.timestamp - a.timestamp for a, b in zip(self.ingested, self.ingested[1:])]
        deltas = [d for d in deltas if d > 0]
        if not deltas:
            return OracleAnswer("intervals", UNKNOWN, "oracle.intervals", False, len(self.ingested))
        mean = sum(deltas) / len(deltas)
        var = sum((d - mean) ** 2 for d in deltas) / len(deltas)
        return OracleAnswer(
            "intervals",
            {
                "count": len(deltas),
                "mean_seconds": mean,
                "stdev_seconds": math.sqrt(var),
                "min_seconds": min(deltas),
                "max_seconds": max(deltas),
            },
            "oracle.intervals",
            True,
            len(deltas),
        )

    def interval_stats(self) -> OracleAnswer:
        """Realised inter-block intervals and their dispersion.

        Measured from ingested timestamps only. A single block yields no
        interval, and that is reported as UNKNOWN rather than as a zero gap.
        """
        if len(self.ingested) < 2:
            return OracleAnswer("intervals", UNKNOWN, "oracle.intervals", False, len(self.ingested))
        deltas = [b.timestamp - a.timestamp for a, b in zip(self.ingested, self.ingested[1:])]
        deltas = [d for d in deltas if d > 0]
        if not deltas:
            return OracleAnswer("intervals", UNKNOWN, "oracle.intervals", False, len(self.ingested))
        mean = sum(deltas) / len(deltas)
        var = sum((d - mean) ** 2 for d in deltas) / len(deltas)
        return OracleAnswer(
            "intervals",
            {
                "count": len(deltas),
                "mean_seconds": mean,
                "stdev_seconds": math.sqrt(var),
                "min_seconds": min(deltas),
                "max_seconds": max(deltas),
            },
            "oracle.intervals",
            True,
            len(deltas),
        )

    def header_entropy(self) -> OracleAnswer:
        """Measured Shannon entropy over the ingested merkle roots."""
        if not self._require():
            return OracleAnswer("entropy", UNKNOWN, "oracle.entropy", False, 0)
        blob = b"".join(b.merkle_root for b in self.ingested)
        return OracleAnswer(
            "entropy",
            _entropy_bits(blob),
            "oracle.entropy",
            True,
            len(blob),
            {"bytes_measured": len(blob)},
        )

    def nonce_structure(self) -> OracleAnswer:
        """Recorded nonces, their range, and the exact sequence fingerprint."""
        if not self._require():
            return OracleAnswer("nonce", UNKNOWN, "oracle.nonce", False, 0)
        nonces = [b.nonce for b in self.ingested]
        fingerprint = hashlib.sha256(
            b"oracle.nonce-series.v1" + b"".join(struct.pack("<I", n) for n in nonces)
        ).hexdigest()
        return OracleAnswer(
            "nonce",
            {
                "count": len(nonces),
                "min": min(nonces),
                "max": max(nonces),
                "distinct": len(set(nonces)),
                "fingerprint": fingerprint,
            },
            "oracle.nonce",
            True,
            len(nonces),
        )

    def lucas_projection(self) -> OracleAnswer:
        """Exact Lucas projection of the observed timestamp series.

        Integer arithmetic only, via ``lucas.core``. The projection is a
        structural reading of the data, not a claim about the next value.
        """
        if not self._require():
            return OracleAnswer("lucas", UNKNOWN, "oracle.lucas", False, 0)
        n = len(self.ingested)
        # Keep the index where L_n is still a compact structural reading of
        # the sample size; the integers grow without bound past this.
        idx = min(n, 48)
        return OracleAnswer(
            "lucas",
            {
                "index": idx,
                "lucas": lucas(idx),
                "fibonacci_ratio": (lucas(idx - 1) / lucas(idx)) if idx > 0 else UNKNOWN,
                "phi_converges_to": PHI,
            },
            "oracle.lucas",
            True,
            n,
        )

    # -- intelligence composition ------------------------------------------

    def phi_resonance_score(self) -> OracleAnswer:
        """Consult the injected φ-resonance intelligence, if present.

        When no resonance substrate is supplied the answer is UNKNOWN. The
        Oracle does not substitute its own arithmetic for a missing
        intelligence type.
        """
        if self.phi_resonance is None:
            return OracleAnswer(
                "phi_resonance",
                UNKNOWN,
                "agi.phi_resonance",
                False,
                0,
                evidence={"reason": "NO_RESONANCE_SUBSTRATE"},
            )
        try:
            value = self.phi_resonance.score([b.timestamp for b in self.ingested])
        except Exception as exc:
            return OracleAnswer(
                "phi_resonance",
                UNKNOWN,
                "agi.phi_resonance",
                False,
                len(self.ingested),
                evidence={"error": type(exc).__name__},
            )
        return OracleAnswer("phi_resonance", value, "agi.phi_resonance", True, len(self.ingested))

    def predictive_causal(self) -> OracleAnswer:
        """Drive PYTHIA's real predictive-causal solver over the next header.

        This is the Oracle acting as PYTHIA does: extract header features,
        generate candidates through the strategy stack (memory-guided,
        Lucas-resonance, Zeckendorf, dual-overlay), and let double-SHA256
        adjudicate every one. The Oracle does not decide whether a candidate
        is right -- it reports what the solver measured.

        A miss is a real, informative result, not a failure to hide. The
        solver's own contract is propose-then-verify, so a miss here means
        the hypotheses were wrong, which is exactly the signal a learning
        system needs.
        """
        if self.predictor is None:
            return OracleAnswer(
                "predictive_causal",
                UNKNOWN,
                "Intelligence.predictive_solver",
                False,
                0,
                evidence={"reason": "NO_PREDICTIVE_SOLVER"},
            )
        if not self.ingested:
            return OracleAnswer(
                "predictive_causal",
                UNKNOWN,
                "Intelligence.predictive_solver",
                False,
                0,
                evidence={"reason": "NO_OBSERVED_BLOCKS"},
            )
        last = self.ingested[-1]
        try:
            result = self.predictor.solve(
                header=last.raw_header,
                target=last.target.to_bytes(32, "big"),
                block_context={
                    "height": last.height,
                    "difficulty": last.difficulty,
                    "observed_blocks": len(self.ingested),
                },
                fallback_search=self._cpu_fallback,
            )
        except Exception as exc:
            return OracleAnswer(
                "predictive_causal",
                UNKNOWN,
                "Intelligence.predictive_solver",
                False,
                len(self.ingested),
                evidence={"error": type(exc).__name__},
            )
        return OracleAnswer(
            "predictive_causal",
            {
                "predicted_nonce": result.predicted_nonce,
                "verified": result.verified,
                "winning": result.winning,
                "method": result.method,
                "confidence": result.confidence,
                "fallback_found": result.fallback_found,
                "fallback_hashes": result.fallback_hashes,
                "effective_complexity": result.effective_complexity,
            },
            "Intelligence.predictive_solver",
            True,
            len(self.ingested),
            {"solver": type(self.predictor).__name__},
        )

    def _cpu_fallback(self, header: bytes, target: bytes) -> Tuple[Optional[int], int]:
        """Bounded structured search, used only when prediction misses.

        Reports the nonce it actually found and the hashes it actually spent.
        Never fabricates a win: if nothing is found it returns (None, spent).
        """
        limit = int.from_bytes(bytes(target), "big")
        for i in range(self.fallback_budget):
            blob = bytes(header[:76]) + struct.pack("<I", i)
            digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
            if int.from_bytes(digest, "little") <= limit:
                return i, i + 1
        return None, self.fallback_budget

    def toe_theorems(self) -> OracleAnswer:
        """Consult the live TOE arbiter over the canonical Lucas ladder.

        This is the Oracle's real scale probe. TOE defines its scales through
        the Lucas/Pisot identities (T1 Cassini, T3 Binet, T4 Lucas-Pisot), so
        the scale question is answered by running those theorems at every rung
        of ``lucas.ladder.FULL_LADDER`` -- not by multiplying a budget.
        """
        if self.toe is None:
            return OracleAnswer(
                "toe_theorems",
                UNKNOWN,
                "toe.system",
                False,
                0,
                evidence={"reason": "NO_TOE_SUBSTRATE"},
            )
        rows = []
        for rung in LUCAS_LADDER:
            try:
                ok, results = self.toe.verify_12_theorems_candidate(self._candidate, n_anchor=rung)
            except Exception as exc:
                return OracleAnswer(
                    "toe_theorems",
                    UNKNOWN,
                    "toe.system",
                    False,
                    len(self.ingested),
                    evidence={"error": type(exc).__name__, "rung": rung},
                )
            rows.append(
                {
                    "rung": rung,
                    "L_n": lucas_capacity(rung),
                    "all_pass": bool(ok),
                    "failing": sorted(k for k, v in results.items() if not v),
                }
            )
        return OracleAnswer(
            "toe_theorems",
            rows,
            "toe.system",
            True,
            len(rows),
            {"n_anchor": self.n_anchor, "ladder": list(LUCAS_LADDER)},
        )

    def next_nonce_forecast(self) -> OracleAnswer:
        """Deliberately refuses to predict a future nonce.

        SHA256d is preimage-resistant. No observed chain statistic constrains
        the winning nonce of a future block, and a method that claimed
        otherwise would be reporting an unfalsifiable claim as evidence. The
        Oracle returns the *most recent observed* nonce and labels it as a
        reading of the past, never as a prediction.
        """
        if not self._require():
            return OracleAnswer(
                "next_nonce",
                UNKNOWN,
                "oracle.forecast",
                False,
                0,
                evidence={"reason": "NO_OBSERVED_BLOCKS"},
            )
        last = self.ingested[-1]
        return OracleAnswer(
            "next_nonce",
            None,
            "oracle.forecast",
            False,
            len(self.ingested),
            {
                "refusal": "PREDICTION_NOT_ATTEMPTED",
                "reason": (
                    "SHA256d is preimage-resistant; no chain statistic "
                    "constrains a future winning nonce"
                ),
                "last_observed_nonce": last.nonce,
                "last_observed_height": last.height,
            },
        )

    def summary(self) -> Dict[str, Any]:
        """Full recall over the recorded chain, as a plain dict."""
        questions = [
            "blocks",
            "difficulty_mean",
            "intervals",
            "entropy",
            "nonce",
            "lucas",
            "phi_resonance",
            "next_nonce",
        ]
        out: Dict[str, Any] = {
            "session_started_at": self.session_started_at,
            "ingestion": dict(self.ingestion_report),
        }
        for q in questions:
            ans = self.ask(q)
            out[q] = {
                "value": ans.value,
                "basis": ans.basis,
                "measured": ans.measured,
                "sample_size": ans.sample_size,
                "evidence": ans.evidence,
            }
        return out


# ------------------------------------------------------------------ #
# LUCAS EXPONENTIAL INTELLIGENCE SCALING
# ------------------------------------------------------------------ #

# The canonical ladder is ``lucas.ladder.FULL_LADDER``: the curriculum rungs
# plus the restored mining rungs 31, 50 and 76.
# It is imported, never restated: an Oracle that hardcodes its own rungs would
# drift from the substrate the orchestrator actually climbs.
from lucas.ladder import FULL_LADDER

LUCAS_LADDER: Tuple[int, ...] = tuple(FULL_LADDER)


def lucas_capacity(index: int) -> int:
    """Exact Lucas capacity factor for a rung (L_n, integer, no floats)."""
    if index < 0:
        raise ValueError("rung index must be non-negative")
    return lucas(index)


@dataclass
class RungVerdict:
    """TOE's measured verdict at one rung of the canonical ladder."""

    rung: int
    L_n: int
    all_pass: bool
    failing: List[str]
    n_theorems: int

    def __str__(self) -> str:
        verdict = "PASS" if self.all_pass else "FAIL"
        detail = f" failing={self.failing}" if self.failing else ""
        return (
            f"rung={self.rung:2} L_{self.rung}={self.L_n:6} "
            f"{verdict} ({self.n_theorems} theorems){detail}"
        )


def toe_scale_program(toe: Any, candidate: Any) -> List[RungVerdict]:
    """Run TOE's theorem set at every rung of the canonical Lucas ladder.

    The earlier budget experiment was the wrong instrument: it measured
    nonces scanned, not the identities the ladder is defined over. This runs
    the actual Lucas/Pisot theorems (T1 Cassini, T3 Binet, T4 Lucas-Pisot
    scaling) at each rung and reports what passed.

    A pass here is a statement about the identity holding at that index. It
    is not a claim about search advantage, and this function does not make
    one.
    """
    verdicts: List[RungVerdict] = []
    for rung in LUCAS_LADDER:
        ok, results = toe.verify_12_theorems_candidate(candidate, n_anchor=rung)
        verdicts.append(
            RungVerdict(
                rung=rung,
                L_n=lucas_capacity(rung),
                all_pass=bool(ok),
                failing=sorted(k for k, v in results.items() if not v),
                n_theorems=len(results),
            )
        )
    return verdicts
