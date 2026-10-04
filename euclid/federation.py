"""
EUCLID Federation Core — Canonical Implementation

Sovereign EUCLID nodes, governed coordination, shared creative manifold.

No cross-node autonomy. No peer authority. No distributed world mutation.
No multi-EUCLID self-permission. This is federation without autonomy.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .creative_substrate import (
    CoherenceEngine,
    CoherenceReport,
    CreativeArtifact,
    CreativeGovernancePolicy,
    CreativeManifold,
    CreatorDirective,
    EmergenceEngine,
    EmergenceProposal,
    EuclidCreativeKernel,
    ExpressionMode,
    IntentLayer,
    IntentVector,
    ManifoldEdge,
    ManifoldNode,
    SemanticGeometryLayer,
    WorldEntity,
    WorldEvent,
    WorldStateEngine,
    WorldStateGraph,
    _hash,
    _stable_id,
)


class RegistryError(Exception):
    pass


class NodeHealth:
    """Tri-state health for a federation node."""

    def __init__(self, healthy: bool, details: Mapping[str, Any] | None = None):
        self.healthy = bool(healthy)
        self.details = dict(details or {})

    def is_red(self) -> bool:
        return not self.healthy

    def is_yellow(self) -> bool:
        return bool(self.details.get("warning"))


class FederationNode:
    """One sovereign EUCLID instance participating in the federation."""

    def __init__(self, node_id: str, euclid_instance: Any):
        self.id = node_id
        self.euclid = euclid_instance
        self.status: NodeHealth | None = None
        self.intent_vector: IntentVector | None = None
        self.manifold: CreativeManifold | None = None
        self.artifacts: list[CreativeArtifact] = []
        self.health: NodeHealth | None = None


class FederationState:
    def __init__(self):
        self.node_states: dict[str, NodeHealth] = {}
        self.verdict: str | None = None

    def record(self, node_id: str, status: NodeHealth) -> None:
        self.node_states[node_id] = status

    def any_red(self) -> bool:
        return any(s.is_red() for s in self.node_states.values())

    def any_yellow(self) -> bool:
        return any(s.is_yellow() for s in self.node_states.values())


class FederationRegistry:
    _nodes: dict[str, FederationNode] = {}

    @classmethod
    def register(cls, node: FederationNode) -> None:
        if node.id in cls._nodes:
            raise RegistryError("duplicate_federation_node")
        cls._nodes[node.id] = node

    @classmethod
    def all_nodes(cls) -> list[FederationNode]:
        return list(cls._nodes.values())

    @classmethod
    def get(cls, node_id: str) -> FederationNode | None:
        return cls._nodes.get(node_id)

    @classmethod
    def clear(cls) -> None:
        cls._nodes = {}


# =========================================================
# Node Facade (exposes the interface the orchestrator expects)
# =========================================================

class _StartupOrchestrator:
    def __init__(self, kernel: EuclidCreativeKernel):
        self.kernel = kernel

    def boot(self) -> NodeHealth:
        try:
            self.kernel.run(
                [CreatorDirective("boot", "federation boot check", 1.0, {"themes": ("federation",)})],
                modalities=("narrative",),
            )
            return NodeHealth(True, {"smoke_test": "passed"})
        except Exception as exc:
            return NodeHealth(False, {"error": str(exc)})


class _NodeIntentLayer:
    def __init__(self, kernel: EuclidCreativeKernel, node: FederationNode):
        self.kernel = kernel
        self.node = node

    def current_intent(self) -> IntentVector:
        if self.node.intent_vector is not None:
            return self.node.intent_vector
        if self.kernel.history:
            return self.kernel.history[-1].intent
        return self.kernel.intent_layer.interpret([
            CreatorDirective(self.node.id, "federation default intent", 1.0, {"themes": ("coordination",)})
        ])

    def update(self, intent: IntentVector) -> None:
        self.node.intent_vector = intent


class _NodeSemanticGeometry:
    def __init__(self, kernel: EuclidCreativeKernel, node: FederationNode):
        self.kernel = kernel
        self.node = node

    def build_manifold(self) -> CreativeManifold:
        intent = self.node.intent_vector or self.kernel.intent_layer.interpret([
            CreatorDirective(self.node.id, "federation default intent", 1.0, {"themes": ("coordination",)})
        ])
        self.node.manifold = self.kernel.geometry_layer.construct(intent)
        return self.node.manifold


class _NodeGenerativeSubstrate:
    def __init__(self, kernel: EuclidCreativeKernel, node: FederationNode):
        self.kernel = kernel
        self.node = node

    def generate(self, federation_manifold: CreativeManifold) -> CreativeArtifact:
        intent = self.node.intent_vector
        if intent is None:
            intent = self.kernel.intent_layer.interpret([
                CreatorDirective(self.node.id, "federation derived intent", 1.0, {"themes": ("coordination",)})
            ])
        world = self.kernel.world_engine.world
        if world is None or world.manifold_hash != federation_manifold.content_hash:
            world = self.kernel.world_engine.initialize(intent, federation_manifold)
            self.kernel.world_cluster.put(world)
        artifacts = self.kernel.generative_layer.generate(intent, federation_manifold, world, modalities=("narrative",))
        return artifacts[0]


class _NodeFeedbackCore:
    def __init__(self, kernel: EuclidCreativeKernel):
        self.kernel = kernel

    def process(self, artifacts: Sequence[CreativeArtifact]) -> None:
        if self.kernel.world_engine.world is None:
            return
        self.kernel.world_engine.apply(
            "artifact_commit",
            {"artifact_hashes": [a.content_hash for a in artifacts], "source": "federation_feedback"},
        )


class FederatedEuclid:
    """Wrap a real EuclidCreativeKernel with the federation interface."""

    def __init__(self, node_id: str, kernel: EuclidCreativeKernel):
        self.kernel = kernel
        self._node = FederationNode(node_id, self)
        self.startup_orchestrator = _StartupOrchestrator(kernel)
        self.intent_layer = _NodeIntentLayer(kernel, self._node)
        self.semantic_geometry = _NodeSemanticGeometry(kernel, self._node)
        self.generative_substrate = _NodeGenerativeSubstrate(kernel, self._node)
        self.feedback_core = _NodeFeedbackCore(kernel)

    @property
    def node(self) -> FederationNode:
        return self._node


# =========================================================
# Governance
# =========================================================

class Audit:
    records: list[dict[str, Any]] = []

    @classmethod
    def record(cls, data: Mapping[str, Any]) -> None:
        cls.records.append(dict(data))

    @classmethod
    def clear(cls) -> None:
        cls.records = []


class ForbiddenMotifs:
    @staticmethod
    def list() -> tuple[str, ...]:
        return ("autonomy", "self_permission", "peer_authority", "world_override")


class OperatorConsole:
    @staticmethod
    def request_approval(emergence: Sequence["FederationEmergenceProposal"]) -> bool:
        # Fail-closed: explicit operator approval required in production.
        return False


class Governance:
    """Fail-closed federation governance hooks."""

    vetos: list[dict[str, Any]] = []

    def __init__(self):
        self.vetos = []

    @staticmethod
    def validate_intent(intent: IntentVector) -> bool:
        policy = CreativeGovernancePolicy()
        allowed, _ = policy.validate_intent(intent)
        return allowed

    @staticmethod
    def validate_manifold(manifold: CreativeManifold) -> bool:
        try:
            return bool(manifold.content_hash)
        except Exception:
            return False

    @staticmethod
    def veto(reason: str) -> None:
        entry = {"veto": reason}
        Governance.vetos.append(entry)
        Audit.record(entry)

    def approve(self, emergence: Sequence["FederationEmergenceProposal"]) -> bool:
        if not emergence:
            return False
        for proposal in emergence:
            if Governance.forbids_motif(proposal.candidate):
                return False
        return OperatorConsole.request_approval(emergence)

    @staticmethod
    def forbids_motif(motif: str) -> bool:
        forbidden = ForbiddenMotifs.list()
        return any(term in str(motif).lower() for term in forbidden)


# =========================================================
# Intent Harmoniser
# =========================================================

class IntentHarmoniser:
    @staticmethod
    def combine(intent_vectors: Sequence[IntentVector]) -> IntentVector | None:
        vectors = tuple(intent_vectors)
        if not vectors:
            return None
        if len(vectors) == 1:
            return vectors[0]

        normalised = [IntentHarmoniser._normalise(v) for v in vectors]
        weights = IntentHarmoniser._compute_weights(vectors)
        total = sum(weights)
        if total <= 0:
            return None
        weights = [w / total for w in weights]

        merged = _merge_intents(normalised, weights)
        if not Governance.validate_intent(merged):
            Governance.veto("intent_harmonisation_failure")
            return None
        return merged

    @staticmethod
    def _normalise(intent: IntentVector) -> IntentVector:
        return intent

    @staticmethod
    def _compute_weights(intent_vectors: Sequence[IntentVector]) -> list[float]:
        return [1.0 for _ in intent_vectors]


def _merge_intents(intents: Sequence[IntentVector], weights: Sequence[float]) -> IntentVector:
    if not intents:
        raise ValueError("no intents to merge")

    merged_creators = tuple(dict.fromkeys(c for v in intents for c in v.creators))
    merged_weights: dict[str, float] = {cid: 0.0 for cid in merged_creators}
    for v, w in zip(intents, weights):
        for cid, weight in v.creator_weights.items():
            merged_weights[cid] += w * weight
    wsum = sum(merged_weights.values())
    if wsum > 0:
        merged_weights = {k: v / wsum for k, v in merged_weights.items()}

    def merge_tuples(field: str) -> tuple[str, ...]:
        counts: dict[str, float] = {}
        for v, w in zip(intents, weights):
            for item in getattr(v, field):
                counts[item] = counts.get(item, 0.0) + w
        return tuple(item for item, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8])

    def merge_trajectory() -> tuple[float, ...]:
        seqs = [np.asarray(v.emotional_trajectory, float) for v in intents]
        length = max((len(s) for s in seqs), default=1)
        combined = np.zeros(length)
        for s, w in zip(seqs, weights):
            padded = np.pad(s, (0, length - len(s)), mode="edge") if len(s) < length else s[:length]
            combined += w * padded
        return tuple(float(x) for x in np.clip(combined, 0, 1))

    merged_constraints: dict[str, Any] = {}
    for v in intents:
        for key, value in v.constraints.items():
            if key in merged_constraints and merged_constraints[key] != value:
                merged_constraints[key] = {"conflict": [merged_constraints[key], value], "requires_resolution": True}
            else:
                merged_constraints[key] = value

    return IntentVector(
        intent_id=_stable_id("intent", {"harmonised": [v.intent_id for v in intents]}),
        revision=max(v.revision for v in intents) + 1,
        creators=merged_creators,
        creator_weights=merged_weights,
        tone=merge_tuples("tone"),
        themes=merge_tuples("themes"),
        aesthetics=merge_tuples("aesthetics"),
        symbols=merge_tuples("symbols"),
        emotional_trajectory=merge_trajectory(),
        narrative_direction=" | ".join(v.narrative_direction for v in intents),
        constraints=merged_constraints,
        source_hashes=tuple(v.content_hash for v in intents),
    )


# =========================================================
# Manifold Synthesiser
# =========================================================

class ManifoldSynthesiser:
    DIMENSIONS = SemanticGeometryLayer.DIMENSIONS

    @staticmethod
    def merge(manifolds: Sequence[CreativeManifold]) -> CreativeManifold | None:
        items = tuple(manifolds)
        if not items:
            return None
        if len(items) == 1:
            return items[0]

        nodes: list[ManifoldNode] = []
        edges: list[ManifoldEdge] = []
        for m in items:
            nodes.extend(m.nodes)
            edges.extend(m.edges)

        merged_nodes, id_map = ManifoldSynthesiser._dedupe_nodes(nodes)
        merged_edges = ManifoldSynthesiser._merge_edges(merged_nodes, edges, id_map)

        style: dict[str, float] = {}
        for m in items:
            for k, v in m.style_field.items():
                style[k] = style.get(k, 0.0) + float(v)
        if style:
            total = sum(style.values())
            style = {k: v / total for k, v in style.items()}
        else:
            style = {"unresolved": 1.0}

        tension = tuple(
            float(np.mean([m.tension_gradient[i] if i < len(m.tension_gradient) else 0.5 for m in items]))
            for i in range(6)
        )

        rules: dict[str, Any] = {}
        for m in items:
            for k, v in m.world_rules.items():
                if k in rules and rules[k] != v:
                    rules[k] = {"conflict": [rules[k], v], "requires_resolution": True}
                else:
                    rules[k] = v

        characters: dict[str, Mapping[str, Any]] = {}
        for m in items:
            for name, state in m.characters.items():
                if name in characters and characters[name] != state:
                    characters[name] = {**dict(characters[name]), "conflict": True}
                else:
                    characters[name] = state

        motifs = tuple(dict.fromkeys(m for mf in items for m in mf.motifs))
        intent_hash = items[0].intent_hash

        identity = _stable_id("manifold", {
            "intent": intent_hash,
            "nodes": merged_nodes,
            "edges": merged_edges,
            "style": style,
            "rules": rules,
            "characters": characters,
            "motifs": motifs,
        })
        return CreativeManifold(
            manifold_id=identity,
            intent_hash=intent_hash,
            dimensions=ManifoldSynthesiser.DIMENSIONS,
            nodes=tuple(merged_nodes),
            edges=tuple(merged_edges),
            style_field=style,
            tension_gradient=tension,
            world_rules=rules,
            characters=characters,
            motifs=motifs,
        )

    @staticmethod
    def _dedupe_nodes(nodes: Sequence[ManifoldNode]) -> tuple[list[ManifoldNode], dict[str, str]]:
        seen: dict[str, ManifoldNode] = {}
        for n in nodes:
            key = f"{n.kind}:{n.label}"
            if key not in seen:
                seen[key] = n
        # Reassign stable unique node IDs so merged manifolds never collide.
        remapped: list[ManifoldNode] = []
        id_map: dict[str, str] = {}
        for index, n in enumerate(seen.values()):
            new_id = f"{n.kind}-{index}"
            id_map[n.node_id] = new_id
            remapped.append(ManifoldNode(new_id, n.kind, n.label, n.vector, n.attributes))
        return remapped, id_map

    @staticmethod
    def _merge_edges(nodes: Sequence[ManifoldNode], edges: Sequence[ManifoldEdge], id_map: dict[str, str]) -> list[ManifoldEdge]:
        valid_ids = {n.node_id for n in nodes}
        merged: list[ManifoldEdge] = []
        for e in edges:
            src = id_map.get(e.source, e.source)
            tgt = id_map.get(e.target, e.target)
            if src not in valid_ids or tgt not in valid_ids:
                continue
            if not any(src == x.source and tgt == x.target for x in merged):
                merged.append(ManifoldEdge(src, tgt, e.relation, e.weight))
        return merged


# =========================================================
# Federation Coherence Engine
# =========================================================

class FederationCoherence:
    _engine = CoherenceEngine()

    @staticmethod
    def check(artifacts: Sequence[CreativeArtifact], manifold: CreativeManifold, intent: IntentVector | None = None) -> bool:
        if not artifacts:
            return False
        world = FederationCoherence._ensure_world(intent, manifold)
        if not FederationCoherence._engine.evaluate(intent or FederationCoherence._default_intent(), manifold, artifacts, world).passed:
            return False
        return True

    @staticmethod
    def _ensure_world(intent: IntentVector | None, manifold: CreativeManifold) -> WorldStateGraph:
        if FederationCoherence._engine_state is None:
            FederationCoherence._engine_state = WorldStateEngine()
        engine = FederationCoherence._engine_state
        if engine.world is None or engine.world.manifold_hash != manifold.content_hash:
            intent = intent or FederationCoherence._default_intent()
            engine.initialize(intent, manifold)
        return engine.world

    @staticmethod
    def _default_intent() -> IntentVector:
        return IntentLayer().interpret([
            CreatorDirective("federation", "default federation coherence intent", 1.0, {"themes": ("coordination",)})
        ])


FederationCoherence._engine_state = None


# =========================================================
# Federation Emergence Engine
# =========================================================

class FederationEmergenceProposal:
    def __init__(self, candidate: str, novelty_score: float, coherence_score: float):
        self.candidate = candidate
        self.novelty_score = novelty_score
        self.coherence_score = coherence_score


class FederationEmergence:
    _engine = EmergenceEngine()

    @staticmethod
    def propose(manifold: CreativeManifold, artifacts: Sequence[CreativeArtifact], intent: IntentVector | None = None) -> list[FederationEmergenceProposal]:
        motifs = FederationEmergence._extract_motifs(artifacts)
        tension = FederationEmergence._compute_tension(manifold)
        candidates = FederationEmergence._generate_candidates(motifs, tension)

        scored = [
            FederationEmergenceProposal(
                candidate=c,
                novelty_score=FederationEmergence._novelty_score(c, artifacts),
                coherence_score=FederationEmergence._coherence_score(c, manifold),
            )
            for c in candidates
        ]

        filtered = [s for s in scored if not Governance.forbids_motif(s.candidate)]
        ranked = sorted(filtered, key=lambda x: x.novelty_score * x.coherence_score, reverse=True)
        return ranked[:5]

    @staticmethod
    def _extract_motifs(artifacts: Sequence[CreativeArtifact]) -> list[str]:
        motifs: list[str] = []
        for a in artifacts:
            motifs.extend(a.motifs)
        return motifs

    @staticmethod
    def _compute_tension(manifold: CreativeManifold) -> float:
        if not manifold.tension_gradient:
            return 0.5
        return float(np.mean(manifold.tension_gradient))

    @staticmethod
    def _generate_candidates(motifs: Sequence[str], tension: float) -> list[str]:
        candidates: list[str] = []
        for i, left in enumerate(motifs):
            for right in motifs[i + 1:]:
                candidates.append(f"{left}-{right}")
        if not candidates:
            candidates = ["federation-emergence"]
        return candidates

    @staticmethod
    def _novelty_score(candidate: str, artifacts: Sequence[CreativeArtifact]) -> float:
        seen = sum(candidate in str(a.content) for a in artifacts)
        return 1.0 / (1.0 + seen)

    @staticmethod
    def _coherence_score(candidate: str, manifold: CreativeManifold) -> float:
        parts = candidate.split("-")
        matched = sum(1 for p in parts if any(p in m.label for m in manifold.nodes))
        return matched / max(len(parts), 1)


# =========================================================
# World Cluster
# =========================================================

class WorldCluster:
    _engine: WorldStateEngine | None = None

    @classmethod
    def update(cls, manifold: CreativeManifold, artifacts: Sequence[CreativeArtifact], intent: IntentVector | None = None) -> bool:
        if cls._engine is None:
            cls._engine = WorldStateEngine()
        intent = intent or cls._default_intent()
        world = cls._engine.initialize(intent, manifold)
        cls._engine.apply(
            "artifact_commit",
            {"artifact_hashes": [a.content_hash for a in artifacts], "source": "WorldCluster.update"},
        )
        if not cls._engine.verify_chain():
            Governance.veto("world_chain_integrity_failure")
            return False
        return True

    @classmethod
    def apply(cls, emergence_proposal: FederationEmergenceProposal, manifold: CreativeManifold, intent: IntentVector | None = None) -> bool:
        if cls._engine is None:
            cls._engine = WorldStateEngine()
        if cls._engine.world is None or cls._engine.world.manifold_hash != manifold.content_hash:
            intent = intent or cls._default_intent()
            cls._engine.initialize(intent, manifold)
        cls._engine.apply(
            "lore_add",
            {"statement": f"Emergence proposal: {emergence_proposal.candidate}"},
        )
        if not cls._engine.verify_chain():
            Governance.veto("emergence_chain_failure")
            return False
        return True

    @classmethod
    def _default_intent(cls) -> IntentVector:
        return IntentLayer().interpret([
            CreatorDirective("world_cluster", "world cluster default intent", 1.0, {"themes": ("coordination",)})
        ])

    @classmethod
    def reset(cls) -> None:
        cls._engine = None


# =========================================================
# Federation Orchestrator
# =========================================================

class EuclidFederationOrchestrator:
    def __init__(self, nodes: Sequence[FederationNode], governance: Governance):
        self.nodes = list(nodes)
        self.governance = governance
        self.state = FederationState()
        self.cycles_completed = 0

    def startup(self) -> FederationState:
        for node in self.nodes:
            status = node.euclid.startup_orchestrator.boot()
            node.health = status
            self.state.record(node.id, status)

        if self.state.any_red():
            return self.enter_emergency_mode()
        return self.enter_operational_mode()

    def enter_operational_mode(self) -> FederationState:
        for node in self.nodes:
            FederationRegistry.register(node)
        self.run_federated_cycle(max_cycles=1)
        return self.state

    def run_federated_cycle(self, max_cycles: int | None = None) -> None:
        while True:
            if max_cycles is not None and self.cycles_completed >= max_cycles:
                break

            intents = [n.euclid.intent_layer.current_intent() for n in self.nodes]
            federation_intent = IntentHarmoniser.combine(intents)
            if federation_intent is None:
                self.governance.veto("intent_harmonisation_failure")
                self.cycles_completed += 1
                continue

            for n in self.nodes:
                n.euclid.intent_layer.update(federation_intent)

            manifolds = [n.euclid.semantic_geometry.build_manifold() for n in self.nodes]
            federation_manifold = ManifoldSynthesiser.merge(manifolds)
            if federation_manifold is None:
                self.governance.veto("manifold_synthesis_failure")
                self.cycles_completed += 1
                continue

            artifacts = []
            for n in self.nodes:
                a = n.euclid.generative_substrate.generate(federation_manifold)
                artifacts.append(a)
                n.artifacts.append(a)

            if not FederationCoherence.check(artifacts, federation_manifold, federation_intent):
                self.governance.veto("federation_coherence_failure")
                self.cycles_completed += 1
                continue

            WorldCluster.update(federation_manifold, artifacts, federation_intent)

            for n in self.nodes:
                n.euclid.feedback_core.process(artifacts)

            emergence = FederationEmergence.propose(federation_manifold, artifacts, federation_intent)

            if self.governance.approve(emergence):
                for proposal in emergence:
                    WorldCluster.apply(proposal, federation_manifold, federation_intent)

            self.cycles_completed += 1
            continue

    def enter_emergency_mode(self) -> FederationState:
        self.state.verdict = "RED"
        return self.state

    def run_single_cycle(self) -> dict[str, Any]:
        """Run exactly one federation cycle and return the result."""
        self.run_federated_cycle(max_cycles=self.cycles_completed + 1)
        return {
            "cycles_completed": self.cycles_completed,
            "node_count": len(self.nodes),
            "vetos": list(self.governance.vetos),
            "registry": [n.id for n in FederationRegistry.all_nodes()],
        }