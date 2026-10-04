"""PYTHIA persistent store — run journal, qudit memory traces, self-curation.

Every run is logged to an append-only journal and fed back into PYTHIA's
learning loop, so she accumulates a substantial memory across runs instead
of starting empty each time. Each memory is stored three ways:

1. **Primes** — Zeckendorf/Fibonacci indices (the existing substrate in
   ``pythia_memory`` / ``pythia_learning``).
2. **Qudits** — each memory is also encoded as a quantum state in the
   32-dimensional Hilbert space via ``quantum_tensor.encode_data_to_state``;
   retrieval is by quantum fidelity |<psi|phi>|^2.
3. **Disk** — JSON snapshots under ``artifacts/pythia/`` so memory
   survives process restarts.

Curation is PYTHIA's own decision, not an external rule. The curator
scores every memory's utility from the system's *own* signals —
activation counts, learned confidence, retrieval hits, reward linkage,
graph connectivity, recency — derives its keep/demote/prune cutoffs from
the utility distribution itself (golden-ratio quantiles, modulated by the
emergence signal), and journals every single decision with its reasons.
Nothing is deleted silently; every prune leaves a tombstone in the
journal saying why she decided it wasn't useful.

The module is honest: utility is a heuristic score over real usage
signals, and the journal makes every decision auditable.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .pythia_learning import PythiaLearning
from .pythia_memory import PythiaMemorySystem
from kellogg.quantum_tensor import Complex, QuantumState, encode_data_to_state

logger = logging.getLogger("Intelligence.pythia_store")

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2
INV_PHI = 1.0 / PHI
INV_PHI2 = INV_PHI * INV_PHI  # ~0.382 — the "weak tail" fraction

DEFAULT_STORE_DIR = Path("artifacts") / "pythia"


# ---------------------------------------------------------------------------
# Run journal — append-only log of every run, fed back into the learning loop
# ---------------------------------------------------------------------------


class RunJournal:
    """Append-only JSONL journal. Every run is logged; nothing is lost.

    Each entry records a timestamp, a kind (``teach``, ``consolidate``,
    ``guide_mining``, ``curation``, ``experiment``, ``snapshot`` ...), and
    a JSON-safe payload. The journal is both the audit trail and the
    ingestion source: :meth:`tail_as_patterns` converts recent entries
    into teaching patterns for the learning substrate.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._count = self._count_lines()

    def _count_lines(self) -> int:
        if not self.path.is_file():
            return 0
        with self.path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for line in fh if line.strip())

    def append(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Append one journal entry. Returns the recorded entry."""
        entry = {
            "seq": self._count,
            "ts": time.time(),
            "kind": str(kind),
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")
        self._count += 1
        return entry

    def entries(
        self, limit: Optional[int] = None, kind: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Read journal entries (newest last). Optionally filter by kind."""
        if not self.path.is_file():
            return []
        out: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if kind is not None and rec.get("kind") != kind:
                    continue
                out.append(rec)
        if limit is not None:
            out = out[-limit:]
        return out

    def tail_as_patterns(self, limit: int = 32, n_units: int = 32) -> List[np.ndarray]:
        """Convert recent journal entries into teaching patterns.

        This is the "every run is fed to the AI" half of the journal: each
        entry's payload is hashed into a deterministic real vector the
        learning substrate can ingest.
        """
        patterns: List[np.ndarray] = []
        for rec in self.entries(limit=limit):
            digest = json.dumps(rec.get("payload", {}), sort_keys=True, default=str)
            h = hashlib.sha256(digest.encode()).digest()
            vec = np.array([h[(i * 7) % len(h)] / 255.0 for i in range(n_units)])
            # Mix in a phase so two different payloads decorrelate.
            phase = (rec.get("seq", 0) % 64) / 64.0
            vec = np.cos(vec * math.pi + phase * PHI)
            patterns.append(vec)
        return patterns

    def count(self) -> int:
        return self._count


# ---------------------------------------------------------------------------
# Qudit memory store — memories as quantum states, retrieved by fidelity
# ---------------------------------------------------------------------------


@dataclass
class QuditTrace:
    """One memory's quantum-state trace on the dim-32 qudit."""

    key: str  # e.g. "lt:<pattern_id>", "ep:<event_id>", "sem:<concept>"
    state: QuantumState
    stored_at: float = 0.0


class QuditMemoryStore:
    """Quantum-substrate memory: each memory is a state in the qudit space.

    Encoding is ``encode_data_to_state`` (deterministic, real-amplitude
    map into the 32-dim Hilbert space). Retrieval is by quantum fidelity
    — the Born-rule overlap between the query state and each stored
    trace. This is the "store in qudits" representation: a memory is a
    point on the projective Hilbert sphere, not a row in a table.
    """

    def __init__(self, dim: int = 32) -> None:
        self.dim = dim
        self._traces: Dict[str, QuditTrace] = {}

    def store(self, key: str, data: Any) -> Optional[QuditTrace]:
        """Encode ``data`` into a qudit state and keep it under ``key``.

        A null vector carries no information and cannot be normalised;
        such data is skipped (returns ``None``).
        """
        try:
            state = encode_data_to_state(data, dim=self.dim)
        except ValueError:
            return None
        trace = QuditTrace(key=key, state=state, stored_at=time.time())
        self._traces[key] = trace
        return trace

    def retrieve(
        self, query: Any, top_k: int = 5, min_fidelity: float = 0.0
    ) -> List[Tuple[QuditTrace, float]]:
        """Retrieve the traces most quantum-similar to ``query``.

        Scored by fidelity F = |<query | trace>|^2 in [0, 1].
        """
        if not self._traces:
            return []
        q = encode_data_to_state(query, dim=self.dim)
        scored = [(t, q.fidelity(t.state)) for t in self._traces.values()]
        scored = [s for s in scored if s[1] >= min_fidelity]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def remove(self, keys: set) -> int:
        before = len(self._traces)
        for k in keys:
            self._traces.pop(k, None)
        return before - len(self._traces)

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "dim": self.dim,
            "traces": [
                {
                    "key": t.key,
                    "stored_at": t.stored_at,
                    "amplitudes": [[a.re, a.im] for a in t.state.amplitudes],
                }
                for t in self._traces.values()
            ],
        }

    def load_snapshot(self, snap: Dict[str, Any]) -> None:
        self._traces = {}
        for rec in snap.get("traces", []):
            amps = [Complex(float(re), float(im)) for re, im in rec.get("amplitudes", [])]
            if len(amps) != self.dim:
                continue
            state = QuantumState(self.dim, amps)
            self._traces[str(rec["key"])] = QuditTrace(
                key=str(rec["key"]),
                state=state,
                stored_at=float(rec.get("stored_at", 0.0)),
            )

    def status(self) -> Dict[str, Any]:
        return {"dim": self.dim, "n_traces": len(self._traces)}


# ---------------------------------------------------------------------------
# Curator — PYTHIA decides what to keep, demote, and prune
# ---------------------------------------------------------------------------


@dataclass
class CurationDecision:
    """One keep/demote/prune decision, with the reason she made it."""

    tier: str  # episodic | semantic | archival | long_term
    item_id: str
    action: str  # keep | demote | prune
    utility: float
    reasons: List[str] = field(default_factory=list)


class PythiaCurator:
    """Autonomous memory curation — she decides what's useful and what isn't.

    Utility model (all signals are ones the system already tracks):

    ``u = w_act * a + w_conf * c + w_use * r + w_rec * recency + w_net * degree``

    where ``a`` is normalised activation, ``c`` learned confidence, ``r``
    retrieval hits, ``recency`` a Pisot decay on time-since-last-access,
    and ``degree`` graph connectivity (semantic tier). The weights are
    golden-ratio distributed and *shift with the emergence signal*: when
    emergence is low she favours recency (exploration); when high, she
    favours confidence (consolidation of what works).

    Cutoffs are self-derived from the utility distribution:

    - prune everything below ``min(phi^2-quantile, 0.5)`` — the weak tail,
      but never anything that is objectively decent;
    - demote (episodic/pattern -> archival) the band between the prune
      cutoff and ``min(phi-quantile, 0.7)``;
    - keep the rest.

    Vetoes (her own judgement calls):
    - germ-line patterns are kept unless utility < prune_cutoff * 1/phi
      (i.e. unless the memory has truly collapsed);
    - seeded knowledge (provenance set) is always kept — it's her
      bootstrap education;
    - error/unexpected episodes get a salience bonus — failures are
      informative even when unpleasant.

    Every decision is journaled. ``audit()`` returns the reasons.
    """

    def __init__(
        self,
        memory: PythiaMemorySystem,
        pythia: PythiaLearning,
        qudits: QuditMemoryStore,
        journal: RunJournal,
    ) -> None:
        self.memory = memory
        self.pythia = pythia
        self.qudits = qudits
        self.journal = journal
        self._history: List[Dict[str, Any]] = []

    # -- utility signals ---------------------------------------------------

    @staticmethod
    def _recency(last_accessed: float, written_ts: float, now: float) -> float:
        if last_accessed:
            return math.exp(-0.01 * max(0.0, now - last_accessed))
        # Never retrieved: half-credit decayed from write time — she has
        # not found it useful yet, so it earns no full freshness bonus.
        if written_ts:
            return 0.5 * math.exp(-0.01 * max(0.0, now - written_ts))
        return 0.0

    def _utility(
        self,
        activation: int,
        confidence: float,
        accesses: int,
        last_accessed: float,
        written_ts: float,
        degree: int = 0,
        germ_line: bool = False,
        salient: bool = False,
        emergence: float = 0.0,
    ) -> Tuple[float, List[str]]:
        """Score one memory and report which signals drove the score."""
        now = time.time()
        a = min(1.0, activation / 8.0)
        r = min(1.0, accesses / 4.0)
        rec = self._recency(last_accessed, written_ts, now)
        net = min(1.0, degree / 8.0)
        # Golden-ratio weights, self-modulated by the emergence signal:
        # low emergence -> explore (recency up); high -> exploit (confidence up).
        w_act = INV_PHI * (1.0 + 0.25 * emergence)
        w_conf = INV_PHI2 * (1.0 + 0.5 * emergence)
        w_use = INV_PHI * INV_PHI2
        w_rec = INV_PHI2 * (1.0 + 0.5 * (1.0 - emergence))
        w_net = INV_PHI * INV_PHI2
        u = w_act * a + w_conf * confidence + w_use * r + w_rec * rec + w_net * net
        reasons = []
        if a >= 0.5:
            reasons.append(f"activated {activation}x")
        if confidence >= 0.6:
            reasons.append(f"confidence {confidence:.2f}")
        if accesses:
            reasons.append(f"retrieved {accesses}x")
        if rec >= 0.8:
            reasons.append("recently used")
        elif rec <= 0.2:
            reasons.append("stale")
        if degree:
            reasons.append(f"{degree} associations")
        if germ_line:
            u += 0.15
            reasons.append("germ-line (success-linked)")
        if salient:
            u += 0.1
            reasons.append("salient (error/surprise)")
        return u, reasons

    @staticmethod
    def _quantile(values: List[float], q: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        idx = min(len(s) - 1, max(0, int(len(s) * q)))
        return s[idx]

    # -- per-tier evaluation ------------------------------------------------

    def _evaluate(self, emergence: float) -> Tuple[List[CurationDecision], Dict[str, float]]:
        decisions: List[CurationDecision] = []
        utils: Dict[str, float] = {}

        # Episodic events.
        for e in self.memory.episodic.events():
            u, reasons = self._utility(
                activation=1,
                confidence=0.5 + min(0.5, e.reward * 0.5),
                accesses=e.access_count,
                last_accessed=e.last_accessed,
                written_ts=e.timestamp,
                salient=e.error_state or e.unexpected,
                emergence=emergence,
            )
            utils[f"ep:{e.event_id}"] = u
            decisions.append(CurationDecision("episodic", str(e.event_id), "keep", u, reasons))
        # Semantic concepts.
        for n in self.memory.semantic.nodes():
            degree = len(n.associations)
            u, reasons = self._utility(
                activation=n.activation_count,
                confidence=n.confidence,
                accesses=n.activation_count,
                last_accessed=n.last_accessed,
                written_ts=0.0,  # concepts have no write ts; access governs
                degree=degree,
                emergence=emergence,
            )
            if n.provenance:
                reasons.append("seeded knowledge")
            utils[f"sem:{n.concept}"] = u
            decisions.append(CurationDecision("semantic", n.concept, "keep", u, reasons))
        # Archival entries.
        for e in self.memory.archival.entries():
            u, reasons = self._utility(
                activation=1,
                confidence=0.5 + min(0.5, float(e.metadata.get("reward", 0.0)) * 0.5),
                accesses=e.access_count,
                last_accessed=e.last_accessed,
                written_ts=0.0,  # no write timestamp; access history governs
                emergence=emergence,
            )
            utils[f"arc:{e.entry_id}"] = u
            decisions.append(CurationDecision("archival", str(e.entry_id), "keep", u, reasons))
        # Consolidated learning patterns.
        for m in self.pythia.patterns():
            u, reasons = self._utility(
                activation=m.activation_count,
                confidence=m.confidence,
                accesses=m.activation_count,
                last_accessed=m.last_accessed,
                written_ts=0.0,  # no write timestamp; access history governs
                germ_line=m.cell_fate == "germ_line",
                emergence=emergence,
            )
            utils[f"lt:{m.pattern_id}"] = u
            decisions.append(CurationDecision("long_term", str(m.pattern_id), "keep", u, reasons))

        return decisions, utils

    # -- the decision ------------------------------------------------------

    def curate(self, emergence_signal: float = 0.0) -> Dict[str, Any]:
        """Run one curation pass. Returns the decision report.

        PYTHIA evaluates every memory, derives her cutoffs from the
        utility distribution, applies her vetoes, executes the decisions,
        and journals the whole thing.
        """
        decisions, utils = self._evaluate(emergence_signal)
        values = list(utils.values())
        prune_cut = min(self._quantile(values, INV_PHI2), 0.5)
        keep_cut = max(prune_cut, min(self._quantile(values, INV_PHI), 0.7))

        ep_prune: set = set()
        ep_demote: List[Any] = []
        sem_prune: set = set()
        arc_prune: set = set()
        lt_prune: set = set()
        lt_demote: List[Any] = []
        qudit_prune: set = set()

        for d in decisions:
            # Resolve the item's utility under its store key.
            if d.tier == "episodic":
                u = utils.get(f"ep:{d.item_id}", d.utility)
            elif d.tier == "semantic":
                u = utils.get(f"sem:{d.item_id}", d.utility)
            elif d.tier == "archival":
                u = utils.get(f"arc:{d.item_id}", d.utility)
            elif d.tier == "long_term":
                u = utils.get(f"lt:{d.item_id}", d.utility)
            d.utility = u

            if d.tier == "semantic":
                node = next(
                    (n for n in self.memory.semantic.nodes() if n.concept == d.item_id), None
                )
                if node is not None and node.provenance:
                    d.action = "keep"
                    if "seeded knowledge" not in d.reasons:
                        d.reasons.append("seeded knowledge")
                    continue
                if u < prune_cut:
                    d.action = "prune"
                    sem_prune.add(d.item_id)
                    qudit_prune.add(f"sem:{d.item_id}")
                continue

            if d.tier == "long_term":
                pat = next(
                    (m for m in self.pythia.patterns() if str(m.pattern_id) == d.item_id), None
                )
                germ = pat is not None and pat.cell_fate == "germ_line"
                if germ and u >= prune_cut * INV_PHI:
                    d.action = "keep"  # germ-line veto
                    continue
                if u < prune_cut:
                    d.action = "prune"
                    lt_prune.add(pat.pattern_id if pat else int(d.item_id))
                    qudit_prune.add(f"lt:{d.item_id}")
                elif u < keep_cut:
                    d.action = "demote"
                    if pat is not None:
                        lt_demote.append(pat)
                        qudit_prune.add(f"lt:{d.item_id}")
                continue

            if d.tier == "episodic":
                if u < prune_cut:
                    d.action = "prune"
                    ep_prune.add(int(d.item_id))
                    qudit_prune.add(f"ep:{d.item_id}")
                elif u < keep_cut:
                    d.action = "demote"
                    ev = next(
                        (e for e in self.memory.episodic.events() if e.event_id == int(d.item_id)),
                        None,
                    )
                    if ev is not None:
                        ep_demote.append(ev)
                        qudit_prune.add(f"ep:{d.item_id}")
                continue

            if d.tier == "archival":
                if u < prune_cut:
                    d.action = "prune"
                    arc_prune.add(int(d.item_id))
                    qudit_prune.add(f"arc:{d.item_id}")
                continue

        # Execute: demotions fold the item into archival (cold storage)
        # before removal from the hot tier.
        for ev in ep_demote:
            self.memory.archival.store(
                ev.embedding,
                metadata={
                    "demoted_from": "episodic",
                    "event_id": ev.event_id,
                    "trigger": ev.trigger,
                    "reward": ev.reward,
                    "outcome_digest": str(ev.outcome)[:200],
                },
            )
        if ep_demote:
            self.memory.episodic.remove({e.event_id for e in ep_demote})
        for pat in lt_demote:
            unfolded = np.frombuffer(pat.folded_data, dtype=float)
            self.memory.archival.store(
                unfolded,
                metadata={
                    "demoted_from": "long_term",
                    "pattern_id": pat.pattern_id,
                    "cell_fate": pat.cell_fate,
                    "confidence": pat.confidence,
                },
            )
        if lt_demote:
            self.pythia.prune({p.pattern_id for p in lt_demote})
        if ep_prune:
            self.memory.episodic.remove(ep_prune)
        if sem_prune:
            self.memory.semantic.remove(sem_prune)
        if arc_prune:
            self.memory.archival.remove(arc_prune)
        if lt_prune:
            self.pythia.prune(lt_prune)
        if qudit_prune:
            self.qudits.remove(qudit_prune)

        report = {
            "ts": time.time(),
            "emergence_signal": emergence_signal,
            "prune_cutoff": round(prune_cut, 4),
            "keep_cutoff": round(keep_cut, 4),
            "n_evaluated": len(decisions),
            "kept": sum(1 for d in decisions if d.action == "keep"),
            "demoted": sum(1 for d in decisions if d.action == "demote"),
            "pruned": sum(1 for d in decisions if d.action == "prune"),
            "decisions": [
                {
                    "tier": d.tier,
                    "item": d.item_id,
                    "action": d.action,
                    "utility": round(d.utility, 4),
                    "reasons": d.reasons,
                }
                for d in decisions
            ],
        }
        self._history.append(report)
        # Every decision is journaled — her reasoning is auditable.
        self.journal.append("curation", report)
        return report

    def audit(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Recent curation reports — what she decided and why."""
        return list(self._history[-limit:])


# ---------------------------------------------------------------------------
# PythiaStore — journal + qudits + snapshots + curator, one object
# ---------------------------------------------------------------------------


class PythiaStore:
    """Persistent backing store for PYTHIA's memory.

    - ``record_run`` appends to the journal (every run is logged).
    - ``ingest`` feeds journal entries back into the learning substrate
      (every run is fed to the AI).
    - ``save`` / ``load`` persist the memory tiers, learning substrate,
      and qudit traces to disk (memory survives restarts).
    - ``curate`` lets PYTHIA prune what she no longer finds useful.
    """

    def __init__(
        self,
        memory: PythiaMemorySystem,
        pythia: PythiaLearning,
        store_dir: Optional[Path] = None,
        qudit_dim: int = 32,
        autosave_every: int = 10,
    ) -> None:
        self.dir = Path(store_dir) if store_dir is not None else DEFAULT_STORE_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.memory = memory
        self.pythia = pythia
        self.journal = RunJournal(self.dir / "journal.jsonl")
        self.qudits = QuditMemoryStore(dim=qudit_dim)
        self.curator = PythiaCurator(memory, pythia, self.qudits, self.journal)
        self.autosave_every = max(1, int(autosave_every))
        self._since_save = 0

    # -- journal + feed-back ------------------------------------------------

    @property
    def snapshot_path(self) -> Path:
        return self.dir / "memory_snapshot.json"

    def record_run(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Log a run and schedule an autosave."""
        entry = self.journal.append(kind, payload)
        self._since_save += 1
        if self._since_save >= self.autosave_every:
            self.save()
        return entry

    def ingest(self, limit: int = 32, mining_success: bool = False) -> int:
        """Feed recent journal entries into the learning substrate.

        Returns the number of patterns taught.
        """
        patterns = self.journal.tail_as_patterns(limit=limit, n_units=self.pythia.n)
        if patterns:
            self.pythia.learning_step(patterns, [mining_success] * len(patterns))
        return len(patterns)

    # -- persistence --------------------------------------------------------

    def _refresh_qudits(self) -> None:
        """Re-encode current memories into qudit traces."""
        for e in self.memory.episodic.events():
            self.qudits.store(f"ep:{e.event_id}", e.embedding)
        for n in self.memory.semantic.nodes():
            self.qudits.store(
                f"sem:{n.concept}",
                [n.confidence, n.activation_count, len(n.associations)],
            )
        for e in self.memory.archival.entries():
            self.qudits.store(f"arc:{e.entry_id}", np.frombuffer(e.folded_data, dtype=float))
        for m in self.pythia.patterns():
            self.qudits.store(f"lt:{m.pattern_id}", np.frombuffer(m.folded_data, dtype=float))

    def save(self) -> Path:
        """Persist memory tiers + learning substrate + qudit traces."""
        self._refresh_qudits()
        snap = {
            "version": 1,
            "saved_at": time.time(),
            "journal_entries": self.journal.count(),
            "memory": self.memory.to_snapshot(),
            "learning": self.pythia.to_snapshot(),
            "qudits": self.qudits.to_snapshot(),
        }
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.snapshot_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(snap, default=str), encoding="utf-8")
        os.replace(tmp, self.snapshot_path)
        self._since_save = 0
        logger.info("PYTHIA store saved: %s", self.snapshot_path)
        return self.snapshot_path

    def load(self) -> bool:
        """Restore persisted memory. Returns True if a snapshot was loaded."""
        if not self.snapshot_path.is_file():
            return False
        try:
            snap = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            self.memory.load_snapshot(snap.get("memory", {}))
            self.pythia.load_snapshot(snap.get("learning", {}))
            self.qudits.load_snapshot(snap.get("qudits", {}))
            logger.info(
                "PYTHIA store loaded: %d journal entries, memory restored from %s",
                snap.get("journal_entries", 0),
                self.snapshot_path,
            )
            return True
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Failed to load PYTHIA store snapshot: %s", e)
            return False

    # -- curation -----------------------------------------------------------

    def curate(self, emergence_signal: Optional[float] = None) -> Dict[str, Any]:
        """Let PYTHIA decide what to keep, demote, and prune."""
        if emergence_signal is None:
            emergence_signal = float(self.pythia.status().get("emergence_signal", 0.0))
        report = self.curator.curate(emergence_signal)
        self.save()
        return report

    def status(self) -> Dict[str, Any]:
        return {
            "store_dir": str(self.dir),
            "journal_entries": self.journal.count(),
            "qudits": self.qudits.status(),
            "snapshot_exists": self.snapshot_path.is_file(),
            "autosave_every": self.autosave_every,
        }


__all__ = [
    "RunJournal",
    "QuditTrace",
    "QuditMemoryStore",
    "CurationDecision",
    "PythiaCurator",
    "PythiaStore",
    "DEFAULT_STORE_DIR",
]
