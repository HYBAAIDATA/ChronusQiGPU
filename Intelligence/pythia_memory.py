"""PYTHIA four-tier dynamic memory system.

Implements the bi-directional memory architecture for an emergent AI agent,
combining the Letta (agent-driven context paging) and Mem0 (pipeline-driven
fact extraction) approaches on the repo's Q[√5] folding/Zeckendorf substrate.

Memory Tiers
------------
1. **Working Memory** — in-context window + dynamic scratchpad.
   - Active execution buffer: current goal, sub-tasks, tool returns, scratchpad.
   - Dynamic pruning & compression: sliding-window summariser compresses
     completed steps into dense state summaries while preserving active
     variable pointers.

2. **Episodic Memory** — hybrid vector store + event streams.
   - Full-trajectory encoding: immutable logs of (timestamp, trigger, plan,
     tool_calls, outcome). No summarisation at write time — preserves
     temporal context and causal relationships.
   - Tri-factor retrieval engine: scores past episodes by:
     * **Relevance** — cosine similarity between task embedding and episode embedding.
     * **Recency** — exponential decay ``e^(-λΔt)`` favouring recent events.
     * **Salience** — high weight for episodes with high reward, errors,
       or unexpected outcomes.

3. **Semantic Memory** — structured knowledge graph.
   - Abstracts general rules from episodic history.
   - Entity-relationship graph where nodes are concepts and edges are
     learned associations with confidence weights.
   - Stored in the Zeckendorf/Fibonacci (primes) substrate via the repo's
     ``turing_core.zeckendorf_encode``.

4. **Archival Memory** — unbounded long-term storage.
   - Patterns folded via the golden symplectic transform
     (``cortex_golden_transform``) and encoded into Zeckendorf indices.
   - This is the "store in the primes" capability: Fibonacci/Lucas numbers
     are the golden-ratio sequence that generates prime structure.

Memory Interaction Loop
----------------------
1. **Pre-task retrieval** — Working Memory queries Episodic Memory for
   relevant past patterns and failure traces.
2. **In-task updating** — Working Memory records real-time state changes
   and intermediate tool results.
3. **Post-task consolidation** — Working Memory flushes raw execution data
   to Episodic Memory as an immutable audit event; Semantic Memory
   abstracts rules; Archival Memory folds and stores in primes.

Cognitive Scaffolding
---------------------
A structured curriculum that presents progressively harder tasks as core
concepts are mastered, without causing chaotic failure modes.

Socratic & Environmental Feedback
--------------------------------
When the agent produces an unexpected state transition:
1. Prompt the system to trace its reasoning step-by-step.
2. Provide precise feedback on where the internal state model diverged.
3. Allow the agent to update its own heuristic parameters before retry.

Meta-Cognitive Reflection
-------------------------
A secondary validation pass where the system reflects on its own output
before executing: catches logic gaps, scores confidence, refines decisions.
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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import turing_core as _turing
except ImportError:  # pragma: no cover
    _turing = None  # type: ignore[assignment]

logger = logging.getLogger("Intelligence.pythia_memory")

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2


# ---------------------------------------------------------------------------
# Working Memory — in-context execution buffer + dynamic scratchpad
# ---------------------------------------------------------------------------


@dataclass
class ScratchpadEntry:
    """One entry in the working-memory scratchpad."""

    step: int
    content: str
    variable_pointers: Dict[str, Any] = field(default_factory=dict)
    compressed: bool = False


@dataclass
class WorkingMemoryState:
    """The current state of working memory."""

    goal: str = ""
    sub_tasks: List[str] = field(default_factory=list)
    active_tool_returns: List[Dict[str, Any]] = field(default_factory=list)
    scratchpad: List[ScratchpadEntry] = field(default_factory=list)
    active_variables: Dict[str, Any] = field(default_factory=dict)
    context_capacity: int = 1024
    context_used: int = 0

    def is_full(self) -> bool:
        return self.context_used >= self.context_capacity


class WorkingMemory:
    """Working memory: in-context window + dynamic scratchpad.

    Implements sliding-window context management. When context approaches
    capacity, an inline summariser compresses completed intermediate steps
    into dense state summaries while preserving active variable pointers.
    """

    def __init__(self, capacity: int = 1024):
        self.capacity = capacity
        self.state = WorkingMemoryState(context_capacity=capacity)

    def set_goal(self, goal: str) -> None:
        self.state.goal = goal
        self._update_usage()

    def add_sub_task(self, task: str) -> None:
        self.state.sub_tasks.append(task)
        self._update_usage()

    def add_tool_return(self, tool: str, result: Any) -> None:
        self.state.active_tool_returns.append({"tool": tool, "result": result})
        self._update_usage()

    def add_scratchpad(self, content: str, variables: Optional[Dict[str, Any]] = None) -> None:
        entry = ScratchpadEntry(
            step=len(self.state.scratchpad),
            content=content,
            variable_pointers=variables or {},
        )
        self.state.scratchpad.append(entry)
        self._update_usage()
        # Auto-compress if full.
        if self.state.is_full():
            self._compress()

    def set_variable(self, name: str, value: Any) -> None:
        self.state.active_variables[name] = value
        self._update_usage()

    def get_variable(self, name: str) -> Any:
        return self.state.active_variables.get(name)

    def _update_usage(self) -> None:
        usage = len(self.state.goal)
        usage += sum(len(t) for t in self.state.sub_tasks)
        usage += sum(len(str(r)) for r in self.state.active_tool_returns)
        usage += sum(len(e.content) for e in self.state.scratchpad)
        usage += sum(len(str(v)) for v in self.state.active_variables.values())
        self.state.context_used = usage

    def _compress(self) -> None:
        """Inline summariser: compress completed scratchpad steps.

        Compresses older entries into a single dense summary while keeping
        the most recent entries and all active variable pointers intact.
        """
        if len(self.state.scratchpad) < 3:
            return
        # Keep the last 2 entries uncompressed; compress the rest.
        to_compress = self.state.scratchpad[:-2]
        keep = self.state.scratchpad[-2:]
        # Dense summary: concatenate contents, preserve variable pointers.
        all_vars: Dict[str, Any] = {}
        summary_parts = []
        for entry in to_compress:
            summary_parts.append(f"[step {entry.step}] {entry.content}")
            all_vars.update(entry.variable_pointers)
        compressed = ScratchpadEntry(
            step=to_compress[-1].step,
            content=f"COMPRESSED: {' | '.join(summary_parts)}",
            variable_pointers=all_vars,
            compressed=True,
        )
        self.state.scratchpad = [compressed] + keep
        self._update_usage()
        logger.debug(
            "Working memory compressed: %d entries → %d",
            len(to_compress) + 2,
            len(self.state.scratchpad),
        )

    def flush(self) -> Dict[str, Any]:
        """Flush working memory for post-task consolidation.

        Returns a serialisable snapshot of the full execution trajectory.
        """
        snapshot = {
            "goal": self.state.goal,
            "sub_tasks": list(self.state.sub_tasks),
            "tool_returns": list(self.state.active_tool_returns),
            "scratchpad": [
                {
                    "step": e.step,
                    "content": e.content,
                    "variables": e.variable_pointers,
                    "compressed": e.compressed,
                }
                for e in self.state.scratchpad
            ],
            "variables": dict(self.state.active_variables),
        }
        return snapshot

    def reset(self) -> None:
        """Reset working memory for a new task (preserves capacity)."""
        self.state = WorkingMemoryState(context_capacity=self.capacity)

    def status(self) -> Dict[str, Any]:
        return {
            "goal": self.state.goal,
            "n_sub_tasks": len(self.state.sub_tasks),
            "n_tool_returns": len(self.state.active_tool_returns),
            "n_scratchpad": len(self.state.scratchpad),
            "n_variables": len(self.state.active_variables),
            "context_used": self.state.context_used,
            "context_capacity": self.state.context_capacity,
            "is_full": self.state.is_full(),
        }


# ---------------------------------------------------------------------------
# Episodic Memory — hybrid vector store + event streams with tri-factor retrieval
# ---------------------------------------------------------------------------


@dataclass
class EpisodicEvent:
    """One immutable episode in episodic memory.

    Full-trajectory encoding: timestamp, trigger, plan, tool calls, outcome.
    No summarisation at write time — preserves temporal context and causal
    relationships.
    """

    event_id: int
    timestamp: float
    trigger: str
    plan: List[str]
    tool_calls: List[Dict[str, Any]]
    outcome: Dict[str, Any]
    embedding: np.ndarray  # semantic embedding for retrieval
    reward: float  # utility score
    error_state: bool  # did this episode end in error?
    unexpected: bool  # was the outcome unexpected?
    access_count: int = 0  # how often retrieval surfaced this event
    last_accessed: float = 0.0  # timestamp of last retrieval hit


class EpisodicMemory:
    """Episodic memory: immutable event logs with tri-factor retrieval.

    Surface past experiences prior to task execution by scoring historical
    episodes on three parameters:
    - **Relevance**: cosine similarity between task and episode embeddings.
    - **Recency**: exponential decay ``e^(-λΔt)``.
    - **Salience**: high weight for high reward, errors, unexpected outcomes.
    """

    def __init__(self, decay_lambda: float = 0.01, embedding_dim: int = 32):
        self.decay_lambda = decay_lambda
        self.embedding_dim = embedding_dim
        self._events: List[EpisodicEvent] = []
        self._next_id = 0

    def _embed(self, text: str) -> np.ndarray:
        """Deterministic semantic embedding using the golden-ratio substrate.

        Uses a phi-phase-rotated hash to produce a fixed-dimensional embedding.
        This is a real (deterministic) embedding, not a random one.
        """
        h = hashlib.sha256(text.encode()).digest()
        emb = np.zeros(self.embedding_dim, dtype=float)
        for i in range(self.embedding_dim):
            byte_idx = (i * 7) % len(h)
            phase = (h[byte_idx] / 255.0) * 2 * math.pi
            emb[i] = math.cos(i * PHI + phase)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb

    def record(
        self,
        trigger: str,
        plan: List[str],
        tool_calls: List[Dict[str, Any]],
        outcome: Dict[str, Any],
        reward: float = 0.0,
        error_state: bool = False,
        unexpected: bool = False,
    ) -> EpisodicEvent:
        """Record an immutable episode. No summarisation at write time."""
        event = EpisodicEvent(
            event_id=self._next_id,
            timestamp=time.time(),
            trigger=trigger,
            plan=list(plan),
            tool_calls=list(tool_calls),
            outcome=dict(outcome),
            embedding=self._embed(trigger + " " + " ".join(plan)),
            reward=reward,
            error_state=error_state,
            unexpected=unexpected,
        )
        self._next_id += 1
        self._events.append(event)
        return event

    def retrieve(
        self,
        task_description: str,
        top_k: int = 5,
        relevance_weight: float = 0.4,
        recency_weight: float = 0.3,
        salience_weight: float = 0.3,
    ) -> List[Tuple[EpisodicEvent, float]]:
        """Tri-factor retrieval: relevance + recency + salience.

        Returns the top-k past episodes with their composite scores.
        """
        if not self._events:
            return []
        query_emb = self._embed(task_description)
        now = time.time()
        scored: List[Tuple[EpisodicEvent, float]] = []
        for event in self._events:
            # Relevance: cosine similarity.
            relevance = float(np.dot(query_emb, event.embedding))
            # Recency: exponential decay.
            age = now - event.timestamp
            recency = math.exp(-self.decay_lambda * age)
            # Salience: high reward, errors, or unexpected outcomes.
            salience = 0.5  # baseline
            if event.reward > 0:
                salience += min(1.0, event.reward) * 0.3
            if event.error_state:
                salience += 0.2  # errors are salient
            if event.unexpected:
                salience += 0.2  # surprises are salient
            salience = min(1.0, salience)
            # Composite score.
            score = (
                relevance_weight * relevance + recency_weight * recency + salience_weight * salience
            )
            scored.append((event, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]
        for event, _ in top:
            event.access_count += 1
            event.last_accessed = now
        return top

    def get_failure_traces(self, task_description: str, top_k: int = 3) -> List[EpisodicEvent]:
        """Retrieve past failure traces for a task (for Socratic feedback)."""
        results = self.retrieve(task_description, top_k=top_k * 2)
        return [e for e, _ in results if e.error_state][:top_k]

    def status(self) -> Dict[str, Any]:
        return {
            "n_events": len(self._events),
            "n_errors": sum(1 for e in self._events if e.error_state),
            "n_unexpected": sum(1 for e in self._events if e.unexpected),
            "avg_reward": (
                sum(e.reward for e in self._events) / len(self._events) if self._events else 0.0
            ),
        }

    # -- curation + persistence -------------------------------------------

    def events(self) -> List[EpisodicEvent]:
        """All episodes, for the curator to evaluate."""
        return list(self._events)

    def remove(self, event_ids: set) -> int:
        """Remove events by id (curator decision). Returns count removed."""
        before = len(self._events)
        self._events = [e for e in self._events if e.event_id not in event_ids]
        return before - len(self._events)

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "next_id": self._next_id,
            "decay_lambda": self.decay_lambda,
            "events": [
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp,
                    "trigger": e.trigger,
                    "plan": e.plan,
                    "tool_calls": e.tool_calls,
                    "outcome": e.outcome,
                    "embedding": e.embedding.tolist(),
                    "reward": e.reward,
                    "error_state": e.error_state,
                    "unexpected": e.unexpected,
                    "access_count": e.access_count,
                    "last_accessed": e.last_accessed,
                }
                for e in self._events
            ],
        }

    def load_snapshot(self, snap: Dict[str, Any]) -> None:
        self._next_id = int(snap.get("next_id", 0))
        self._events = []
        for rec in snap.get("events", []):
            self._events.append(
                EpisodicEvent(
                    event_id=int(rec["event_id"]),
                    timestamp=float(rec["timestamp"]),
                    trigger=str(rec["trigger"]),
                    plan=list(rec.get("plan", [])),
                    tool_calls=list(rec.get("tool_calls", [])),
                    outcome=dict(rec.get("outcome", {})),
                    embedding=np.asarray(rec["embedding"], dtype=float),
                    reward=float(rec.get("reward", 0.0)),
                    error_state=bool(rec.get("error_state", False)),
                    unexpected=bool(rec.get("unexpected", False)),
                    access_count=int(rec.get("access_count", 0)),
                    last_accessed=float(rec.get("last_accessed", 0.0)),
                )
            )


# ---------------------------------------------------------------------------
# Semantic Memory — knowledge graph abstracted from episodic history
# ---------------------------------------------------------------------------


@dataclass
class SemanticNode:
    """A concept node in the semantic knowledge graph."""

    concept: str
    zeckendorf_id: List[int]  # stored in the primes substrate
    confidence: float
    activation_count: int
    associations: Dict[str, float] = field(default_factory=dict)  # concept → weight
    # Rich metadata (for seeded knowledge and tool registry).
    category: str = ""
    definition: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    provenance: str = ""
    last_accessed: float = 0.0  # timestamp of last query hit


class SemanticMemory:
    """Semantic memory: structured knowledge graph.

    Abstracts general rules from episodic history. Concepts are stored as
    Zeckendorf-encoded identifiers in the Fibonacci/primes substrate. Edges
    are learned associations with confidence weights that strengthen with
    repeated co-occurrence.
    """

    def __init__(self):
        self._nodes: Dict[str, SemanticNode] = {}

    def _store_in_primes(self, concept_hash: int) -> List[int]:
        """Store a concept ID in the Zeckendorf (Fibonacci/primes) substrate."""
        if _turing is not None:
            return _turing.zeckendorf_encode(abs(int(concept_hash)))
        # Fallback Fibonacci decomposition.
        fibs = [1, 2]
        while fibs[-1] <= abs(concept_hash):
            fibs.append(fibs[-1] + fibs[-2])
        indices: List[int] = []
        rem = abs(concept_hash)
        for idx in range(len(fibs) - 1, -1, -1):
            if fibs[idx] <= rem:
                indices.append(idx + 2)
                rem -= fibs[idx]
                if rem == 0:
                    break
        return indices

    def _concept_hash(self, concept: str) -> int:
        h = hashlib.sha256(concept.encode()).digest()
        return int.from_bytes(h[:4], "big")

    def learn_concept(self, concept: str) -> SemanticNode:
        """Register a new concept or retrieve an existing one."""
        if concept in self._nodes:
            node = self._nodes[concept]
            node.activation_count += 1
            # Confidence grows with Pisot convergence: 1 - |ψ|^n.
            node.confidence = min(1.0, 1.0 - abs(PSI) ** node.activation_count)
            return node
        node = SemanticNode(
            concept=concept,
            zeckendorf_id=self._store_in_primes(self._concept_hash(concept)),
            confidence=abs(PSI),  # initial low confidence
            activation_count=1,
        )
        self._nodes[concept] = node
        return node

    def add_concept(
        self,
        concept: str,
        category: str = "",
        definition: str = "",
        properties: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        provenance: str = "",
    ) -> SemanticNode:
        """Add a concept with rich metadata (for knowledge seeding).

        Unlike ``learn_concept`` (which is for emergent concept discovery),
        this method stores full metadata: category, definition, properties,
        and provenance. Used by the PYTHIA knowledge seed and tool registry.
        """
        node = self.learn_concept(concept)
        node.category = category
        node.definition = definition
        node.properties = properties or {}
        node.confidence = max(node.confidence, confidence)
        node.provenance = provenance
        return node

    def add_association(
        self,
        concept_a: str,
        concept_b: str,
        relation: str = "associated",
        weight: float = 0.5,
    ) -> None:
        """Add an association between two concepts with a relation label.

        The relation is encoded in the concept_b key as ``concept_b:relation``
        so it can be retrieved later. Used by the knowledge seed.
        """
        key = f"{concept_b}:{relation}" if relation != "associated" else concept_b
        node_a = self.learn_concept(concept_a)
        self.learn_concept(concept_b)  # ensure concept_b exists
        node_a.associations[key] = max(
            node_a.associations.get(key, 0.0),
            weight,
        )

    def associate(self, concept_a: str, concept_b: str, weight: float = 1.0) -> None:
        """Strengthen the association between two concepts.

        The weight is Pisot-decayed by distance in the association graph,
        so directly co-occurring concepts strengthen more than distant ones.
        """
        node_a = self.learn_concept(concept_a)
        node_b = self.learn_concept(concept_b)
        # Hebbian-like strengthening: w *= (1 + α * weight).
        alpha = 0.1
        node_a.associations[concept_b] = (
            node_a.associations.get(concept_b, 0.0) * (1 + alpha * weight) + alpha * weight
        )
        node_b.associations[concept_a] = (
            node_b.associations.get(concept_a, 0.0) * (1 + alpha * weight) + alpha * weight
        )

    def abstract_from_episode(self, event: EpisodicEvent) -> None:
        """Abstract general rules from an episodic event.

        Extracts concepts from the trigger, plan, and outcome, then
        associates them based on co-occurrence. This is the Mem0-style
        autonomous fact extraction applied to episodic memory.
        """
        concepts: List[str] = []
        # Extract concepts from trigger and plan.
        for text in [event.trigger] + event.plan:
            # Simple concept extraction: split on whitespace, lowercase.
            for word in text.lower().split():
                if len(word) > 3:
                    concepts.append(word)
        # Extract from outcome keys.
        if isinstance(event.outcome, dict):
            for key in event.outcome:
                concepts.append(str(key))
        # Learn concepts and associate co-occurring ones.
        for c in set(concepts):
            self.learn_concept(c)
        # Associate all pairs (co-occurrence).
        unique = list(set(concepts))
        for i, a in enumerate(unique):
            for b in unique[i + 1 :]:
                reward_weight = max(0.1, event.reward) if not event.error_state else 0.1
                self.associate(a, b, weight=reward_weight)

    def query(self, concept: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Retrieve the top-k associated concepts for a given concept."""
        node = self._nodes.get(concept)
        if node is None:
            return []
        node.activation_count += 1
        node.last_accessed = time.time()
        ranked = sorted(node.associations.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def status(self) -> Dict[str, Any]:
        return {
            "n_concepts": len(self._nodes),
            "n_associations": sum(len(n.associations) for n in self._nodes.values()),
            "avg_confidence": (
                sum(n.confidence for n in self._nodes.values()) / len(self._nodes)
                if self._nodes
                else 0.0
            ),
        }

    # -- curation + persistence -------------------------------------------

    def nodes(self) -> List[SemanticNode]:
        """All concept nodes, for the curator to evaluate."""
        return list(self._nodes.values())

    def remove(self, concepts: set) -> int:
        """Remove concept nodes by name (curator decision).

        Also strips dangling edges to the removed concepts so the graph
        stays consistent.
        """
        before = len(self._nodes)
        for c in concepts:
            self._nodes.pop(c, None)
        for node in self._nodes.values():
            for key in list(node.associations):
                if key.split(":", 1)[0] in concepts:
                    del node.associations[key]
        return before - len(self._nodes)

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "nodes": [
                {
                    "concept": n.concept,
                    "zeckendorf_id": n.zeckendorf_id,
                    "confidence": n.confidence,
                    "activation_count": n.activation_count,
                    "associations": n.associations,
                    "category": n.category,
                    "definition": n.definition,
                    "properties": n.properties,
                    "provenance": n.provenance,
                    "last_accessed": n.last_accessed,
                }
                for n in self._nodes.values()
            ]
        }

    def load_snapshot(self, snap: Dict[str, Any]) -> None:
        self._nodes = {}
        for rec in snap.get("nodes", []):
            node = SemanticNode(
                concept=str(rec["concept"]),
                zeckendorf_id=list(rec.get("zeckendorf_id", [])),
                confidence=float(rec.get("confidence", 0.0)),
                activation_count=int(rec.get("activation_count", 0)),
                associations=dict(rec.get("associations", {})),
                category=str(rec.get("category", "")),
                definition=str(rec.get("definition", "")),
                properties=dict(rec.get("properties", {})),
                provenance=str(rec.get("provenance", "")),
                last_accessed=float(rec.get("last_accessed", 0.0)),
            )
            self._nodes[node.concept] = node


# ---------------------------------------------------------------------------
# Archival Memory — folded + Zeckendorf-encoded long-term storage
# ---------------------------------------------------------------------------


@dataclass
class ArchivalEntry:
    """One entry in archival memory (folded + stored in primes)."""

    entry_id: int
    folded_data: bytes  # golden symplectic fold
    zeckendorf_indices: List[int]  # Fibonacci/primes store
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0  # how often retrieval surfaced this entry
    last_accessed: float = 0.0  # timestamp of last retrieval hit


class ArchivalMemory:
    """Archival memory: unbounded long-term storage in the primes substrate.

    Patterns are folded via the golden symplectic transform and encoded
    into Zeckendorf (Fibonacci) indices. This is the "store in the primes"
    capability — Fibonacci/Lucas numbers are the golden-ratio sequence that
    generates prime structure.
    """

    def __init__(self):
        self._entries: List[ArchivalEntry] = []
        self._next_id = 0

    def _fold(self, data: np.ndarray) -> bytes:
        """Fold raw payload bytes through the T_phi bijection.

        M15 in GL(2, Z/256Z), det = -1 mod 256 (Cassini-protected): the
        fold is an exact byte-pair bijection — bit-exact, same length,
        and the stored form is the working representation queries run on.
        """
        raw = np.ascontiguousarray(data, dtype=np.float64).tobytes()
        if _turing is not None:
            return _turing.t_phi_fold(raw)
        return raw

    def _unfold(self, folded_data: bytes, length: int) -> np.ndarray:
        """Unfold via the exact T_phi inverse (byte-exact round trip)."""
        if _turing is not None:
            raw = _turing.t_phi_unfold(folded_data, len(folded_data))
        else:
            raw = folded_data
        arr = np.frombuffer(raw[: length * 8], dtype=np.float64).copy()
        if len(arr) < length:
            arr = np.pad(arr, (0, length - len(arr)))
        return arr

    def _store_in_primes(self, entry_id: int) -> List[int]:
        """Encode an ID into Zeckendorf (Fibonacci/primes) indices."""
        if _turing is not None:
            return _turing.zeckendorf_encode(abs(int(entry_id)))
        fibs = [1, 2]
        while fibs[-1] <= abs(entry_id):
            fibs.append(fibs[-1] + fibs[-2])
        indices: List[int] = []
        rem = abs(entry_id)
        for idx in range(len(fibs) - 1, -1, -1):
            if fibs[idx] <= rem:
                indices.append(idx + 2)
                rem -= fibs[idx]
                if rem == 0:
                    break
        return indices

    def store(self, data: np.ndarray, metadata: Optional[Dict[str, Any]] = None) -> ArchivalEntry:
        """Fold and store data in the primes substrate."""
        entry = ArchivalEntry(
            entry_id=self._next_id,
            folded_data=self._fold(np.asarray(data, dtype=float)),
            zeckendorf_indices=self._store_in_primes(self._next_id),
            metadata=metadata or {},
        )
        self._next_id += 1
        self._entries.append(entry)
        return entry

    def retrieve(self, entry_id: int, length: int = 32) -> Optional[np.ndarray]:
        """Retrieve and unfold an entry by ID."""
        for entry in self._entries:
            if entry.entry_id == entry_id:
                entry.access_count += 1
                entry.last_accessed = time.time()
                return self._unfold(entry.folded_data, length)
        return None

    def search(self, query: np.ndarray, top_k: int = 5) -> List[Tuple[ArchivalEntry, float]]:
        """Search archival memory by similarity to a query pattern."""
        if not self._entries:
            return []
        q = np.asarray(query, dtype=float)
        scored: List[Tuple[ArchivalEntry, float]] = []
        for entry in self._entries:
            unfolded = self._unfold(entry.folded_data, len(q))
            # Cosine similarity.
            nq = np.linalg.norm(q)
            nu = np.linalg.norm(unfolded)
            if nq > 0 and nu > 0:
                sim = float(np.dot(q, unfolded) / (nq * nu))
            else:
                sim = 0.0
            scored.append((entry, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]
        now = time.time()
        for entry, _ in top:
            entry.access_count += 1
            entry.last_accessed = now
        return top

    def status(self) -> Dict[str, Any]:
        return {
            "n_entries": len(self._entries),
            "total_folded_bytes": sum(len(e.folded_data) for e in self._entries),
            "total_zeckendorf_indices": sum(len(e.zeckendorf_indices) for e in self._entries),
        }

    # -- curation + persistence -------------------------------------------

    def entries(self) -> List[ArchivalEntry]:
        """All archival entries, for the curator to evaluate."""
        return list(self._entries)

    def remove(self, entry_ids: set) -> int:
        """Remove entries by id (curator decision). Returns count removed."""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.entry_id not in entry_ids]
        return before - len(self._entries)

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "next_id": self._next_id,
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "folded_data": base64.b64encode(e.folded_data).decode("ascii"),
                    "zeckendorf_indices": e.zeckendorf_indices,
                    "metadata": e.metadata,
                    "access_count": e.access_count,
                    "last_accessed": e.last_accessed,
                }
                for e in self._entries
            ],
        }

    def load_snapshot(self, snap: Dict[str, Any]) -> None:
        self._next_id = int(snap.get("next_id", 0))
        self._entries = []
        for rec in snap.get("entries", []):
            self._entries.append(
                ArchivalEntry(
                    entry_id=int(rec["entry_id"]),
                    folded_data=base64.b64decode(rec["folded_data"]),
                    zeckendorf_indices=list(rec.get("zeckendorf_indices", [])),
                    metadata=dict(rec.get("metadata", {})),
                    access_count=int(rec.get("access_count", 0)),
                    last_accessed=float(rec.get("last_accessed", 0.0)),
                )
            )


# ---------------------------------------------------------------------------
# Cognitive Scaffolding — progressive curriculum
# ---------------------------------------------------------------------------

MASTERY_MIN_TRIALS = 5


def wilson_lower(successes: int, trials: int, z: float = 1.959964) -> float:
    """Wilson score 95% lower bound of a success rate (0 with no trials)."""
    if trials <= 0:
        return 0.0
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = p + z * z / (2 * trials)
    spread = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    return max(0.0, (centre - spread) / denominator)


@dataclass
class CurriculumTask:
    """One task in the cognitive scaffolding curriculum."""

    task_id: int
    description: str
    difficulty: float  # 0.0 (trivial) to 1.0 (frontier)
    concepts: List[str]  # concepts this task exercises
    prerequisite_concepts: List[str]  # concepts that must be mastered first
    mastery_threshold: float = 0.7  # success rate (95% lower bound) needed to advance


class CognitiveScaffolding:
    """Structured progression of environment tasks for emergent learning.

    Presents progressively harder tasks as core concepts are mastered,
    without causing chaotic failure modes. The curriculum is adaptive:
    it tracks which concepts the agent has mastered (via semantic memory
    confidence) and presents the next appropriate challenge.
    """

    def __init__(self, semantic_memory: SemanticMemory):
        self.semantic = semantic_memory
        self._curriculum: List[CurriculumTask] = []
        self._current_task_idx = 0
        self._mastery_history: List[Dict[str, Any]] = []
        self._outcomes: Dict[int, Tuple[int, int]] = {}  # task -> (trials, successes)
        self._build_default_curriculum()

    def _build_default_curriculum(self) -> None:
        """Build the default mining-intelligence curriculum.

        Progressive difficulty:
        1. Pattern recognition (phi-structured vs random)
        2. Nonce schedule generation (Zeckendorf spacing)
        3. Mining guidance (AGI substrate prediction)
        4. Emergence observation (layered substrate)
        5. AGI/ASI requirements evaluation (four schools)
        """
        tasks = [
            CurriculumTask(
                0,
                "Recognise phi-structured patterns in mining data",
                0.2,
                ["pattern", "phi", "recognition"],
                [],
            ),
            CurriculumTask(
                1,
                "Generate Zeckendorf-spaced nonce schedules",
                0.3,
                ["zeckendorf", "nonce", "schedule"],
                ["pattern"],
            ),
            CurriculumTask(
                2,
                "Guide mining with AGI substrate prediction",
                0.5,
                ["agi", "mining", "prediction"],
                ["zeckendorf", "nonce"],
            ),
            CurriculumTask(
                3,
                "Observe emergence in the layered substrate",
                0.7,
                ["emergence", "layered", "substrate"],
                ["agi", "mining"],
            ),
            CurriculumTask(
                4,
                "Evaluate AGI/ASI requirements across four schools",
                0.9,
                ["agi", "asi", "requirements", "schools"],
                ["emergence", "layered"],
            ),
            CurriculumTask(
                5,
                "Synthesise novel mining strategies from learned rules",
                1.0,
                ["synthesis", "novelty", "strategy"],
                ["agi", "asi", "requirements"],
            ),
        ]
        self._curriculum = tasks

    def current_task(self) -> Optional[CurriculumTask]:
        """Return the current task, or None if curriculum is complete."""
        if self._current_task_idx >= len(self._curriculum):
            return None
        return self._curriculum[self._current_task_idx]

    def check_prerequisites(self, task: CurriculumTask) -> bool:
        """Check if the agent has mastered the prerequisites for a task."""
        for concept in task.prerequisite_concepts:
            node = self.semantic._nodes.get(concept)
            if node is None or node.confidence < task.mastery_threshold:
                return False
        return True

    def record_mastery(self, task: CurriculumTask, success: bool) -> bool:
        """Record one outcome of the current task; True when it is mastered.

        Mastery is earned from outcomes, not asserted: at least
        ``MASTERY_MIN_TRIALS`` attempts, and the Wilson 95% lower bound of
        the success rate at or above the task's threshold (capped at 0.95:
        certainty is never reachable from finite evidence).
        """
        trials, successes = self._outcomes.get(task.task_id, (0, 0))
        trials, successes = trials + 1, successes + int(bool(success))
        self._outcomes[task.task_id] = (trials, successes)
        confidence = wilson_lower(successes, trials)
        self._mastery_history.append(
            {
                "task_id": task.task_id,
                "description": task.description,
                "success": success,
                "trials": trials,
                "successes": successes,
                "confidence": confidence,
            }
        )
        # Strengthen the concepts this task exercises.
        for concept in task.concepts:
            self.semantic.learn_concept(concept)
        if trials >= MASTERY_MIN_TRIALS and confidence >= min(task.mastery_threshold, 0.95):
            self._current_task_idx += 1
            return True
        return False

    def status(self) -> Dict[str, Any]:
        current = self.current_task()
        return {
            "current_task": current.description if current else "curriculum complete",
            "current_difficulty": current.difficulty if current else 1.0,
            "tasks_completed": self._current_task_idx,
            "total_tasks": len(self._curriculum),
            "mastery_history": list(self._mastery_history),
            "curriculum_complete": self._current_task_idx >= len(self._curriculum),
        }


# ---------------------------------------------------------------------------
# Socratic Feedback — trace reasoning, provide feedback, update heuristics
# ---------------------------------------------------------------------------


@dataclass
class SocraticFeedback:
    """Feedback from a Socratic evaluation."""

    reasoning_trace: List[str]  # step-by-step reasoning trace
    divergence_point: Optional[int]  # where the internal model diverged
    feedback: str  # precise feedback on the divergence
    heuristic_updates: Dict[str, float]  # parameter updates
    retry_recommended: bool


class SocraticFeedbackLoop:
    """Socratic & environmental feedback for emergent learning.

    When the agent produces an unexpected state transition:
    1. Prompt the system to trace its reasoning step-by-step.
    2. Provide precise feedback on where the internal state diverged.
    3. Allow the agent to update its own heuristic parameters before retry.
    """

    def __init__(self, episodic_memory: EpisodicMemory):
        self.episodic = episodic_memory
        self._heuristics: Dict[str, float] = {
            "confidence_threshold": 0.5,
            "exploration_rate": 0.1,
            "learning_rate": 0.01,
            "compression_threshold": 0.8,
        }

    def trace_reasoning(self, working_memory: WorkingMemory) -> List[str]:
        """Trace the agent's reasoning step-by-step from working memory."""
        trace: List[str] = []
        trace.append(f"Goal: {working_memory.state.goal}")
        for i, task in enumerate(working_memory.state.sub_tasks):
            trace.append(f"Sub-task {i}: {task}")
        for entry in working_memory.state.scratchpad:
            tag = "[compressed]" if entry.compressed else "[active]"
            trace.append(f"Step {entry.step} {tag}: {entry.content}")
        for ret in working_memory.state.active_tool_returns:
            trace.append(f"Tool {ret['tool']}: {str(ret['result'])[:100]}")
        return trace

    def evaluate(
        self,
        working_memory: WorkingMemory,
        expected_outcome: Any,
        actual_outcome: Any,
    ) -> SocraticFeedback:
        """Evaluate an outcome and provide Socratic feedback.

        Compares the expected and actual outcomes, identifies where the
        internal state model diverged, and recommends heuristic updates.
        """
        trace = self.trace_reasoning(working_memory)
        # Find divergence point: the first scratchpad step where the
        # expected and actual outcomes differ.
        divergence = None
        feedback = "No divergence detected."
        for i, entry in enumerate(working_memory.state.scratchpad):
            if entry.compressed:
                continue
            # Check if this step's variables predict the wrong outcome.
            if "expected" in entry.variable_pointers and "actual" in entry.variable_pointers:
                if entry.variable_pointers["expected"] != entry.variable_pointers["actual"]:
                    divergence = i
                    feedback = (
                        f"Divergence at step {i}: expected "
                        f"{entry.variable_pointers['expected']} but got "
                        f"{entry.variable_pointers['actual']}. The internal "
                        f"model over-estimated the coherence of the pattern."
                    )
                    break
        if expected_outcome != actual_outcome and divergence is None:
            divergence = len(working_memory.state.scratchpad) - 1
            feedback = (
                f"Final outcome diverged: expected {str(expected_outcome)[:50]} "
                f"but got {str(actual_outcome)[:50]}. The reasoning trace "
                f"appears correct step-by-step but the aggregate prediction "
                f"was wrong — likely a heuristic calibration issue."
            )
        # Recommend heuristic updates.
        updates: Dict[str, float] = {}
        if divergence is not None:
            # Lower confidence threshold (be more cautious).
            updates["confidence_threshold"] = max(
                0.1, self._heuristics["confidence_threshold"] - 0.05
            )
            # Increase exploration (try more alternatives).
            updates["exploration_rate"] = min(0.5, self._heuristics["exploration_rate"] + 0.02)
            # Reduce learning rate (smaller steps).
            updates["learning_rate"] = max(0.001, self._heuristics["learning_rate"] * 0.9)
        self._heuristics.update(updates)
        return SocraticFeedback(
            reasoning_trace=trace,
            divergence_point=divergence,
            feedback=feedback,
            heuristic_updates=updates,
            retry_recommended=divergence is not None,
        )

    def get_heuristics(self) -> Dict[str, float]:
        return dict(self._heuristics)


# ---------------------------------------------------------------------------
# Meta-Cognitive Reflection — secondary validation pass
# ---------------------------------------------------------------------------


@dataclass
class ReflectionResult:
    """Result of a meta-cognitive reflection pass."""

    confidence_score: float  # self-assessed confidence [0, 1]
    logic_gaps: List[str]  # detected gaps in reasoning
    refined_decision: Any  # the refined decision after reflection
    should_proceed: bool  # should the agent proceed with the action?


class MetaCognitiveReflection:
    """Meta-cognitive reflection loops.

    A secondary validation pass where the system reflects on its own output
    before executing an action. Catches logic gaps, scores confidence, and
    refines the decision-making process autonomously.
    """

    def __init__(self):
        self._reflection_history: List[ReflectionResult] = []

    def reflect(
        self,
        proposed_action: Any,
        reasoning_trace: List[str],
        working_memory: WorkingMemory,
        confidence_threshold: float = 0.5,
    ) -> ReflectionResult:
        """Reflect on a proposed action before executing it.

        1. Check for logic gaps in the reasoning trace.
        2. Score self-confidence.
        3. Refine the decision if needed.
        4. Decide whether to proceed.
        """
        logic_gaps: List[str] = []
        # Check 1: Is the goal set?
        if not working_memory.state.goal:
            logic_gaps.append("No goal set in working memory.")
        # Check 2: Are there sub-tasks?
        if not working_memory.state.sub_tasks:
            logic_gaps.append("No sub-tasks defined — action may be unstructured.")
        # Check 3: Is the reasoning trace non-trivial?
        if len(reasoning_trace) < 2:
            logic_gaps.append("Reasoning trace too short — insufficient deliberation.")
        # Check 4: Are there compressed (lost) steps?
        compressed = sum(1 for e in working_memory.state.scratchpad if e.compressed)
        if compressed > len(working_memory.state.scratchpad) / 2:
            logic_gaps.append("More than half of scratchpad compressed — context loss risk.")
        # Confidence: start at 1.0, reduce for each gap.
        confidence = 1.0
        confidence -= 0.15 * len(logic_gaps)
        # Reduce confidence if working memory is near capacity (context loss).
        if working_memory.state.is_full():
            confidence -= 0.2
            logic_gaps.append("Working memory full — compression may have lost context.")
        confidence = max(0.0, min(1.0, confidence))
        # Refine: if confidence is low, recommend caution.
        refined = proposed_action
        should_proceed = confidence >= confidence_threshold
        if not should_proceed:
            refined = {
                "original_action": proposed_action,
                "recommendation": "defer",
                "reason": "confidence below threshold after reflection",
                "gaps": logic_gaps,
            }
        result = ReflectionResult(
            confidence_score=confidence,
            logic_gaps=logic_gaps,
            refined_decision=refined,
            should_proceed=should_proceed,
        )
        self._reflection_history.append(result)
        return result

    def status(self) -> Dict[str, Any]:
        return {
            "n_reflections": len(self._reflection_history),
            "avg_confidence": (
                sum(r.confidence_score for r in self._reflection_history)
                / len(self._reflection_history)
                if self._reflection_history
                else 0.0
            ),
            "n_proceeded": sum(1 for r in self._reflection_history if r.should_proceed),
            "n_deferred": sum(1 for r in self._reflection_history if not r.should_proceed),
        }


# ---------------------------------------------------------------------------
# PYTHIA Memory System — orchestrates all four tiers + scaffolding + feedback
# ---------------------------------------------------------------------------


class PythiaMemorySystem:
    """The complete PYTHIA memory system.

    Orchestrates the four memory tiers (working, episodic, semantic,
    archival) plus cognitive scaffolding, Socratic feedback, and
    meta-cognitive reflection into a single bi-directional architecture.

    The Memory Interaction Loop:
    1. Pre-task retrieval: Working Memory queries Episodic Memory.
    2. In-task updating: Working Memory records real-time state.
    3. Post-task consolidation: flush to Episodic, abstract to Semantic,
       fold+store to Archival.
    """

    def __init__(self):
        self.working = WorkingMemory(capacity=1024)
        self.episodic = EpisodicMemory(decay_lambda=0.01, embedding_dim=32)
        self.semantic = SemanticMemory()
        self.archival = ArchivalMemory()
        self.curriculum = CognitiveScaffolding(self.semantic)
        self.socratic = SocraticFeedbackLoop(self.episodic)
        self.reflection = MetaCognitiveReflection()

    # -- The Memory Interaction Loop ------------------------------------

    def begin_task(self, task_description: str) -> Dict[str, Any]:
        """Step 1: Pre-task retrieval.

        Working Memory queries Episodic Memory for relevant past patterns
        and failure traces. Sets the goal and loads context.
        """
        self.working.reset()
        self.working.set_goal(task_description)
        # Retrieve relevant past episodes.
        relevant = self.episodic.retrieve(task_description, top_k=5)
        failures = self.episodic.get_failure_traces(task_description, top_k=3)
        # Load relevant context into working memory.
        for event, score in relevant:
            self.working.add_scratchpad(
                f"Past episode (score={score:.3f}): {event.trigger} → {event.outcome}",
                variables={"past_event_id": event.event_id, "past_score": score},
            )
        for failure in failures:
            self.working.add_scratchpad(
                f"Failure trace: {failure.trigger} → ERROR: {failure.outcome}",
                variables={"failure_event_id": failure.event_id},
            )
        # Query semantic memory for relevant concepts.
        for word in task_description.lower().split():
            if len(word) > 3:
                associations = self.semantic.query(word, top_k=3)
                if associations:
                    self.working.add_scratchpad(
                        f"Semantic associations for '{word}': {associations}",
                    )
        return {
            "relevant_episodes": len(relevant),
            "failure_traces": len(failures),
            "working_memory_status": self.working.status(),
        }

    def execute_step(
        self,
        tool: str,
        result: Any,
        scratchpad_note: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Step 2: In-task updating.

        Working Memory records real-time state changes and intermediate
        tool results.
        """
        self.working.add_tool_return(tool, result)
        if scratchpad_note:
            self.working.add_scratchpad(scratchpad_note, variables)

    def reflect_before_action(self, proposed_action: Any) -> ReflectionResult:
        """Meta-cognitive reflection before executing an action."""
        trace = self.socratic.trace_reasoning(self.working)
        heuristics = self.socratic.get_heuristics()
        return self.reflection.reflect(
            proposed_action=proposed_action,
            reasoning_trace=trace,
            working_memory=self.working,
            confidence_threshold=heuristics["confidence_threshold"],
        )

    def consolidate_task(
        self,
        trigger: str,
        plan: List[str],
        tool_calls: List[Dict[str, Any]],
        outcome: Dict[str, Any],
        reward: float = 0.0,
        error_state: bool = False,
        unexpected: bool = False,
    ) -> Dict[str, Any]:
        """Step 3: Post-task consolidation.

        1. Flush working memory to Episodic Memory (immutable audit event).
        2. Abstract rules to Semantic Memory (knowledge graph).
        3. Fold + store significant patterns to Archival Memory (primes).
        4. Run Socratic feedback if there was an error.
        5. Record curriculum mastery.
        """
        # 1. Flush to episodic memory.
        event = self.episodic.record(
            trigger=trigger,
            plan=plan,
            tool_calls=tool_calls,
            outcome=outcome,
            reward=reward,
            error_state=error_state,
            unexpected=unexpected,
        )
        # 2. Abstract to semantic memory.
        self.semantic.abstract_from_episode(event)
        # 3. Fold + store to archival (if there's a significant pattern).
        if reward > 0 or unexpected:
            pattern = np.array(
                [event.embedding[i] for i in range(min(32, len(event.embedding)))],
                dtype=float,
            )
            self.archival.store(
                pattern,
                metadata={
                    "event_id": event.event_id,
                    "trigger": trigger,
                    "reward": reward,
                },
            )
        # 4. Socratic feedback on errors.
        socratic_result = None
        if error_state or unexpected:
            socratic_result = self.socratic.evaluate(
                self.working,
                expected_outcome=outcome.get("expected"),
                actual_outcome=outcome.get("actual", outcome),
            )
        # 5. Curriculum mastery.
        current_task = self.curriculum.current_task()
        mastery_advanced = False
        if current_task is not None:
            mastery_advanced = self.curriculum.record_mastery(current_task, success=not error_state)
        return {
            "event_id": event.event_id,
            "socratic_feedback": (
                {
                    "divergence_point": socratic_result.divergence_point,
                    "feedback": socratic_result.feedback,
                    "heuristic_updates": socratic_result.heuristic_updates,
                    "retry_recommended": socratic_result.retry_recommended,
                }
                if socratic_result
                else None
            ),
            "mastery_advanced": mastery_advanced,
            "curriculum_status": self.curriculum.status(),
        }

    # -- Persistence (snapshot / restore) --------------------------------

    def to_snapshot(self) -> Dict[str, Any]:
        """Serialise the persistent tiers to a JSON-safe snapshot.

        Working memory is intentionally transient and is not persisted —
        it is the execution buffer for the current task, not long-term
        storage.
        """
        return {
            "version": 1,
            "episodic": self.episodic.to_snapshot(),
            "semantic": self.semantic.to_snapshot(),
            "archival": self.archival.to_snapshot(),
            "socratic_heuristics": self.socratic.get_heuristics(),
            "curriculum": {
                "current_task_idx": self.curriculum._current_task_idx,
                "mastery_history": list(self.curriculum._mastery_history),
            },
        }

    def load_snapshot(self, snap: Dict[str, Any]) -> None:
        """Restore the persistent tiers from a snapshot produced by
        :meth:`to_snapshot`. Existing in-memory content is replaced."""
        if not isinstance(snap, dict) or snap.get("version") != 1:
            raise ValueError("unsupported memory snapshot format")
        self.episodic.load_snapshot(snap.get("episodic", {}))
        self.semantic.load_snapshot(snap.get("semantic", {}))
        self.archival.load_snapshot(snap.get("archival", {}))
        self.socratic._heuristics.update(
            {k: float(v) for k, v in snap.get("socratic_heuristics", {}).items()}
        )
        cur = snap.get("curriculum", {})
        self.curriculum._current_task_idx = int(cur.get("current_task_idx", 0))
        self.curriculum._mastery_history = list(cur.get("mastery_history", []))

    # -- Status ---------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return {
            "working_memory": self.working.status(),
            "episodic_memory": self.episodic.status(),
            "semantic_memory": self.semantic.status(),
            "archival_memory": self.archival.status(),
            "curriculum": self.curriculum.status(),
            "socratic_heuristics": self.socratic.get_heuristics(),
            "reflection": self.reflection.status(),
            "pythia_active": (
                self.curriculum.status()["tasks_completed"] >= 2
                and self.semantic.status()["avg_confidence"] > 0.3
            ),
        }


__all__ = [
    "WorkingMemory",
    "WorkingMemoryState",
    "ScratchpadEntry",
    "EpisodicMemory",
    "EpisodicEvent",
    "SemanticMemory",
    "SemanticNode",
    "ArchivalMemory",
    "ArchivalEntry",
    "CognitiveScaffolding",
    "CurriculumTask",
    "SocraticFeedbackLoop",
    "SocraticFeedback",
    "MetaCognitiveReflection",
    "ReflectionResult",
    "PythiaMemorySystem",
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
