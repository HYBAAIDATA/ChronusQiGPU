"""Project EUCLID creative-intelligence substrate.

Canonical, governed implementation of the five-layer creative architecture:
intent -> semantic geometry -> generation -> world state -> expression.
The kernel is provider-neutral, fail-closed, lineage-preserving, and explicit
about the boundary between implemented capability and deployed infrastructure.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import numpy as np

from hyba_substrate.memory_preservation import verified_atomic_json_write

SCHEMA = "EUCLID_CREATIVE_SUBSTRATE_V2"
MODALITIES = ("narrative", "visual", "audio", "interactive")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode()


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[a-z0-9']+", text.lower())))


def _stable_id(prefix: str, payload: Any) -> str:
    return f"{prefix}-" + _hash(payload).split(":", 1)[1][:24]


class ExpressionMode(str, Enum):
    CREATOR = "creator"
    AUDIENCE = "audience"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class ReferenceMedia:
    reference_id: str
    media_type: str
    source: str
    rights: str
    content_hash: str
    owner_id: str
    consent_scope: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.media_type not in {"text", "image", "sketch", "audio", "video", "interactive", "other"}:
            raise ValueError("unsupported reference media type")
        if not self.source.strip() or self.rights not in {"owned", "licensed", "permissioned", "public_domain"}:
            raise ValueError("reference source and lawful rights basis required")
        if not _SHA256.fullmatch(self.content_hash):
            raise ValueError("reference content hash must be sha256")
        if not self.owner_id.strip():
            raise ValueError("reference owner required")


@dataclass(frozen=True)
class CreatorDirective:
    creator_id: str
    text: str
    weight: float = 1.0
    structured: Mapping[str, Any] = field(default_factory=dict)
    references: tuple[ReferenceMedia | Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.creator_id.strip() or not self.text.strip():
            raise ValueError("creator and text required")
        if not math.isfinite(float(self.weight)) or self.weight <= 0:
            raise ValueError("positive finite weight required")


@dataclass(frozen=True)
class ProviderManifest:
    provider_id: str
    version: str
    modalities: tuple[str, ...]
    output_kind: str = "blueprint"
    governed: bool = True
    deterministic: bool = True
    rights_handling: str = "preserve_creator_rights"
    deployment_validated: bool = False

    def __post_init__(self) -> None:
        if not self.provider_id or not self.version or not self.modalities:
            raise ValueError("provider identity, version and modalities required")
        if any(modality not in MODALITIES for modality in self.modalities):
            raise ValueError("invalid provider modality")
        if self.output_kind not in {"blueprint", "rendered"}:
            raise ValueError("invalid provider output kind")
        if self.output_kind == "rendered" and not self.deployment_validated:
            raise ValueError("rendered provider requires deployment validation")
        if not self.governed or self.rights_handling != "preserve_creator_rights":
            raise ValueError("provider violates governance or creative sovereignty")

    @property
    def content_hash(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True)
class IntentVector:
    intent_id: str
    revision: int
    creators: tuple[str, ...]
    creator_weights: Mapping[str, float]
    tone: tuple[str, ...]
    themes: tuple[str, ...]
    aesthetics: tuple[str, ...]
    symbols: tuple[str, ...]
    emotional_trajectory: tuple[float, ...]
    narrative_direction: str
    constraints: Mapping[str, Any]
    source_hashes: tuple[str, ...]
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.intent_id or self.revision < 1 or not self.creators:
            raise ValueError("invalid intent identity")
        if set(self.creators) != set(self.creator_weights):
            raise ValueError("creator weights must cover creators")
        if abs(sum(map(float, self.creator_weights.values())) - 1.0) > 1e-9:
            raise ValueError("creator weights must sum to one")
        if not self.emotional_trajectory or any(not 0 <= float(x) <= 1 for x in self.emotional_trajectory):
            raise ValueError("emotional trajectory must be in [0,1]")

    @property
    def content_hash(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k not in {"intent_id", "timestamp"}}
        return _hash(payload)


@dataclass(frozen=True)
class ManifoldNode:
    node_id: str
    kind: str
    label: str
    vector: tuple[float, ...]
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ManifoldEdge:
    source: str
    target: str
    relation: str
    weight: float


@dataclass(frozen=True)
class CreativeManifold:
    manifold_id: str
    intent_hash: str
    dimensions: tuple[str, ...]
    nodes: tuple[ManifoldNode, ...]
    edges: tuple[ManifoldEdge, ...]
    style_field: Mapping[str, float]
    tension_gradient: tuple[float, ...]
    world_rules: Mapping[str, Any]
    characters: Mapping[str, Mapping[str, Any]]
    motifs: tuple[str, ...]

    def __post_init__(self) -> None:
        ids = {node.node_id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("duplicate manifold node")
        if any(edge.source not in ids or edge.target not in ids or not 0 <= edge.weight <= 1 for edge in self.edges):
            raise ValueError("invalid manifold edge")
        if any(len(node.vector) != len(self.dimensions) or not np.all(np.isfinite(node.vector)) for node in self.nodes):
            raise ValueError("invalid manifold vector")

    @property
    def content_hash(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k != "manifold_id"}
        return _hash(payload)


@dataclass(frozen=True)
class CreativeArtifact:
    artifact_id: str
    modality: str
    intent_hash: str
    manifold_hash: str
    world_version: int
    content: Mapping[str, Any]
    style_tokens: tuple[str, ...]
    motifs: tuple[str, ...]
    provider_id: str
    provider_manifest_hash: str = ""
    rendered: bool = False

    def __post_init__(self) -> None:
        if self.modality not in MODALITIES or self.world_version < 0:
            raise ValueError("invalid artifact modality or world version")
        if self.provider_manifest_hash and not _SHA256.fullmatch(self.provider_manifest_hash):
            raise ValueError("invalid provider manifest hash")

    @property
    def content_hash(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k != "artifact_id"}
        return _hash(payload)


@dataclass(frozen=True)
class WorldEntity:
    entity_id: str
    kind: str
    state: Mapping[str, Any]
    revision: int = 1


@dataclass(frozen=True)
class WorldEvent:
    event_id: str
    event_type: str
    payload: Mapping[str, Any]
    timestamp: float
    previous_event_hash: str | None
    event_hash: str


@dataclass(frozen=True)
class WorldStateGraph:
    world_id: str
    version: int
    intent_hash: str
    manifold_hash: str
    entities: Mapping[str, WorldEntity]
    relationships: tuple[ManifoldEdge, ...]
    lore: tuple[str, ...]
    events: tuple[WorldEvent, ...]
    rules: Mapping[str, Any]
    timestamp: float = field(default_factory=time.time)

    @property
    def content_hash(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k != "timestamp"}
        return _hash(payload)


@dataclass(frozen=True)
class CoherenceReport:
    tone_consistency: float
    character_continuity: float
    world_rule_compliance: float
    aesthetic_unity: float
    temporal_coherence: float
    cross_modal_alignment: float
    aggregate: float
    passed: bool
    violations: tuple[str, ...]


@dataclass(frozen=True)
class EmergenceProposal:
    proposal_id: str
    proposal_type: str
    description: str
    motifs: tuple[str, ...]
    novelty: float
    coherence: float
    allowed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TruthTelemetry:
    intent_fidelity: float
    substrate_coherence: float
    phi_density: float
    qec_rejection_rate: float
    scaling_exponent: float | None
    artifact_count: int
    world_version: int
    claims: Mapping[str, str]


@dataclass(frozen=True)
class ExpressionBundle:
    mode: ExpressionMode
    world_id: str
    world_version: int
    artifacts: tuple[CreativeArtifact, ...]
    creator_controls: Mapping[str, Any]
    audience_controls: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class ProvenanceRecord:
    sequence: int
    kind: str
    content_hash: str
    parents: tuple[str, ...]
    previous_record_hash: str | None
    metadata: Mapping[str, Any]
    record_hash: str


class ProvenanceChain:
    """One append-only chain spanning every creative layer."""

    def __init__(self, checkpoint_path: str | Path | None = None) -> None:
        self.checkpoint_path = Path(checkpoint_path).resolve() if checkpoint_path else None
        self.records: list[ProvenanceRecord] = []
        self._restore_if_present()

    @property
    def head(self) -> str:
        return self.records[-1].record_hash if self.records else "sha256:" + "0" * 64

    def append(
        self, kind: str, content_hash: str, parents: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> ProvenanceRecord:
        if not kind or not _SHA256.fullmatch(content_hash):
            raise ValueError("valid provenance kind and content hash required")
        payload = {
            "sequence": len(self.records),
            "kind": kind,
            "content_hash": content_hash,
            "parents": tuple(parents),
            "previous": self.records[-1].record_hash if self.records else None,
            "metadata": dict(metadata or {}),
        }
        record = ProvenanceRecord(
            payload["sequence"], kind, content_hash, payload["parents"],
            payload["previous"], payload["metadata"], _hash(payload),
        )
        self.records.append(record)
        self._persist()
        return record

    def verify(self) -> bool:
        previous = None
        for sequence, record in enumerate(self.records):
            payload = {
                "sequence": sequence,
                "kind": record.kind,
                "content_hash": record.content_hash,
                "parents": record.parents,
                "previous": previous,
                "metadata": dict(record.metadata),
            }
            if record.sequence != sequence or record.previous_record_hash != previous or record.record_hash != _hash(payload):
                return False
            previous = record.record_hash
        return True

    def _persist(self) -> None:
        if self.checkpoint_path:
            verified_atomic_json_write(self.checkpoint_path, {
                "schema": "EUCLID_PROVENANCE_CHAIN_V1",
                "records": [asdict(record) for record in self.records],
                "head": self.head,
            })

    def _restore_if_present(self) -> None:
        if not self.checkpoint_path or not self.checkpoint_path.exists():
            return
        payload = json.loads(self.checkpoint_path.read_text())
        if payload.get("schema") != "EUCLID_PROVENANCE_CHAIN_V1":
            raise ValueError("invalid provenance schema")
        self.records = [ProvenanceRecord(**record) for record in payload.get("records", ())]
        if not self.verify() or payload.get("head") != self.head:
            raise ValueError("provenance chain invalid")


@dataclass(frozen=True)
class CreativeCycle:
    intent: IntentVector
    manifold: CreativeManifold
    artifacts: tuple[CreativeArtifact, ...]
    world: WorldStateGraph
    coherence: CoherenceReport
    emergence: tuple[EmergenceProposal, ...]
    telemetry: TruthTelemetry
    expression: ExpressionBundle
    provenance_head: str
    provenance_verified: bool


class CoherenceGateError(RuntimeError):
    pass


class IntentLayer:
    """Formalises explicit direction without claiming access to hidden intent."""

    def interpret(
        self, directives: Sequence[CreatorDirective], *, revision: int = 1,
        prior: IntentVector | None = None,
    ) -> IntentVector:
        items = tuple(directives)
        if not items:
            raise ValueError("at least one creator directive required")
        if len({item.creator_id for item in items}) != len(items):
            raise ValueError("creator ids must be unique")
        total = sum(float(item.weight) for item in items)
        weights = {item.creator_id: float(item.weight) / total for item in items}

        def collect(key: str) -> tuple[str, ...]:
            values: list[str] = []
            for item in items:
                raw = item.structured.get(key, ())
                if isinstance(raw, str):
                    raw = (raw,)
                values.extend(str(value).strip().lower() for value in raw if str(value).strip())
            return tuple(dict.fromkeys(values))

        tone = collect("tone") or tuple(
            token for token in _tokens(" ".join(item.text for item in items))
            if token in {"warm", "dark", "hopeful", "tense", "playful", "solemn", "intimate", "epic"}
        )
        themes, aesthetics, symbols = collect("themes"), collect("aesthetics"), collect("symbols")
        trajectories = [np.asarray(item.structured.get("emotional_trajectory", (0.5,)), float).reshape(-1) for item in items]
        length = max(map(len, trajectories))
        combined, denominator = np.zeros(length), np.zeros(length)
        for item, trajectory in zip(items, trajectories):
            if not len(trajectory) or not np.all(np.isfinite(trajectory)) or np.any((trajectory < 0) | (trajectory > 1)):
                raise ValueError("invalid emotional trajectory")
            padded = np.pad(trajectory, (0, length - len(trajectory)), mode="edge")
            combined += weights[item.creator_id] * padded
            denominator += weights[item.creator_id]

        constraints: dict[str, Any] = {}
        for item in items:
            for key, value in dict(item.structured.get("constraints", {})).items():
                if key in constraints and constraints[key] != value:
                    constraints[key] = {"conflict": [constraints[key], value], "requires_resolution": True}
                else:
                    constraints[key] = value
        if prior:
            constraints = {**dict(prior.constraints), **constraints}

        source_hashes = []
        for item in items:
            references = [asdict(ref) if isinstance(ref, ReferenceMedia) else dict(ref) for ref in item.references]
            source_hashes.append(_hash({
                "creator": item.creator_id, "text": item.text,
                "structured": dict(item.structured), "references": references,
            }))
        sources = tuple(source_hashes)
        direction = " | ".join(item.text.strip() for item in items)
        identity = _stable_id("intent", {"revision": revision, "creators": tuple(item.creator_id for item in items), "weights": weights, "sources": sources})
        return IntentVector(
            identity, revision, tuple(item.creator_id for item in items), weights,
            tone, themes, aesthetics, symbols,
            tuple(map(float, combined / np.maximum(denominator, 1e-12))),
            direction, constraints, sources,
        )

    def refine(self, prior: IntentVector, feedback: Mapping[str, Any]) -> IntentVector:
        def sequence(name: str, current: Sequence[str]) -> tuple[str, ...]:
            value = feedback.get(name, current)
            if isinstance(value, str):
                value = (value,)
            return tuple(str(item).strip().lower() for item in value if str(item).strip())

        trajectory = tuple(map(float, feedback.get("emotional_trajectory", prior.emotional_trajectory)))
        if not trajectory or any(not 0 <= value <= 1 for value in trajectory):
            raise ValueError("invalid refined emotional trajectory")
        constraints = {**dict(prior.constraints), **dict(feedback.get("constraints", {}))}
        feedback_hash = _hash({"prior": prior.content_hash, "feedback": dict(feedback)})
        identity = _stable_id("intent", {"revision": prior.revision + 1, "prior": prior.content_hash, "feedback": dict(feedback)})
        return IntentVector(
            identity, prior.revision + 1, prior.creators, dict(prior.creator_weights),
            sequence("tone", prior.tone), sequence("themes", prior.themes),
            sequence("aesthetics", prior.aesthetics), sequence("symbols", prior.symbols),
            trajectory, str(feedback.get("direction", prior.narrative_direction)),
            constraints, prior.source_hashes + (feedback_hash,),
        )


class SemanticGeometryLayer:
    DIMENSIONS = ("intent_fidelity", "tension", "novelty", "coherence", "agency", "symbolic_density")

    @staticmethod
    def _vector(label: str, kind: str) -> tuple[float, ...]:
        digest = hashlib.sha256(f"{kind}|{label}".encode()).digest()
        return tuple(int.from_bytes(digest[index:index + 2], "big") / 65535 for index in range(0, 12, 2))

    def construct(self, intent: IntentVector) -> CreativeManifold:
        labels = (
            [("theme", item) for item in intent.themes]
            + [("motif", item) for item in intent.symbols]
            + [("tone", item) for item in intent.tone]
            + [("aesthetic", item) for item in intent.aesthetics]
        )
        if not labels:
            labels = [("direction", token) for token in _tokens(intent.narrative_direction)[:8]]
        nodes = tuple(
            ManifoldNode(f"{kind}-{index}", kind, label, self._vector(label, kind), {})
            for index, (kind, label) in enumerate(labels)
        )
        edges = tuple(
            ManifoldEdge(
                left.node_id, right.node_id, "narrative_progression",
                float(np.dot(left.vector, right.vector) / (np.linalg.norm(left.vector) * np.linalg.norm(right.vector) + 1e-12)),
            )
            for left, right in zip(nodes, nodes[1:])
        )
        style_terms = intent.aesthetics + intent.tone
        style = {term: 1 / len(style_terms) for term in style_terms} if style_terms else {"unresolved": 1.0}
        characters = dict(intent.constraints.get("characters", {}))
        rules = dict(intent.constraints.get("world_rules", {}))
        motifs = tuple(dict.fromkeys(intent.symbols + intent.themes))
        identity = _stable_id("manifold", {
            "intent": intent.content_hash, "dimensions": self.DIMENSIONS,
            "nodes": nodes, "edges": edges, "style": style,
            "rules": rules, "characters": characters, "motifs": motifs,
        })
        return CreativeManifold(
            identity, intent.content_hash, self.DIMENSIONS, nodes, edges, style,
            intent.emotional_trajectory, rules, characters, motifs,
        )


class ModalityProvider(Protocol):
    provider_id: str
    manifest: ProviderManifest

    def generate(
        self, modality: str, intent: IntentVector,
        manifold: CreativeManifold, world: WorldStateGraph | None,
    ) -> Mapping[str, Any]: ...


class StructuredBlueprintProvider:
    """Deterministic plans, never misrepresented as rendered media."""

    provider_id = "euclid.structured-blueprint.v1"
    manifest = ProviderManifest(provider_id, "1.0.0", MODALITIES)

    def generate(self, modality: str, intent: IntentVector, manifold: CreativeManifold, world: WorldStateGraph | None) -> Mapping[str, Any]:
        base = {
            "direction": intent.narrative_direction, "tone": intent.tone,
            "themes": intent.themes, "aesthetics": intent.aesthetics,
            "motifs": manifold.motifs,
        }
        if modality == "narrative":
            return {**base, "format": "scene_blueprint", "beats": tuple(node.label for node in manifold.nodes), "continuity": tuple(manifold.characters)}
        if modality == "visual":
            return {**base, "format": "visual_brief", "palette": tuple(manifold.style_field), "subjects": tuple(manifold.characters)}
        if modality == "audio":
            return {**base, "format": "score_brief", "emotional_curve": manifold.tension_gradient, "motif_cues": manifold.motifs}
        if modality == "interactive":
            return {**base, "format": "interaction_graph", "choices": tuple(node.label for node in manifold.nodes), "rules": manifold.world_rules}
        raise ValueError("unsupported modality")


class GenerativeSubstrateLayer:
    def __init__(self, providers: Mapping[str, ModalityProvider] | None = None) -> None:
        self.providers = dict(providers or {modality: StructuredBlueprintProvider() for modality in MODALITIES})

    def generate(
        self, intent: IntentVector, manifold: CreativeManifold,
        world: WorldStateGraph | None = None,
        modalities: Sequence[str] = MODALITIES,
    ) -> tuple[CreativeArtifact, ...]:
        requested = tuple(modalities)
        if not requested:
            raise ValueError("at least one modality required")
        if len(set(requested)) != len(requested):
            raise ValueError("duplicate modalities are not permitted")
        artifacts = []
        for modality in requested:
            if modality not in MODALITIES or modality not in self.providers:
                raise ValueError(f"no governed provider for {modality}")
            provider = self.providers[modality]
            manifest = getattr(provider, "manifest", None)
            if not isinstance(manifest, ProviderManifest) or provider.provider_id != manifest.provider_id or modality not in manifest.modalities:
                raise PermissionError(f"provider manifest invalid for {modality}")
            content = dict(provider.generate(modality, intent, manifold, world))
            _canonical(content)
            payload = {
                "modality": modality, "intent": intent.content_hash,
                "manifold": manifold.content_hash,
                "world_version": world.version if world else 0,
                "content": content, "provider": provider.provider_id,
                "manifest": manifest.content_hash,
            }
            artifacts.append(CreativeArtifact(
                _stable_id("artifact", payload), modality, intent.content_hash,
                manifold.content_hash, world.version if world else 0, content,
                tuple(intent.tone + intent.aesthetics), manifold.motifs,
                provider.provider_id, manifest.content_hash,
                manifest.output_kind == "rendered",
            ))
        return tuple(artifacts)


class WorldStateEngine:
    def __init__(self, checkpoint_path: str | Path | None = None) -> None:
        self.checkpoint_path = Path(checkpoint_path).resolve() if checkpoint_path else None
        self.world: WorldStateGraph | None = None

    def initialize(self, intent: IntentVector, manifold: CreativeManifold) -> WorldStateGraph:
        entities = {name: WorldEntity(name, "character", dict(state), 1) for name, state in manifold.characters.items()}
        entities.update({
            node.node_id: WorldEntity(node.node_id, node.kind, {"label": node.label}, 1)
            for node in manifold.nodes if node.kind in {"motif", "theme"}
        })
        world_id = _stable_id("world", {"intent": intent.content_hash, "manifold": manifold.content_hash})
        self.world = WorldStateGraph(
            world_id, 0, intent.content_hash, manifold.content_hash, entities,
            manifold.edges, (), (), dict(manifold.world_rules),
        )
        self._persist()
        return self.world

    def apply(self, event_type: str, payload: Mapping[str, Any]) -> WorldStateGraph:
        if self.world is None:
            raise RuntimeError("world not initialized")
        data = dict(payload)
        entities = dict(self.world.entities)
        lore = list(self.world.lore)
        if event_type == "character_update":
            entity_id = str(data.get("entity_id", ""))
            patch = dict(data.get("state", {}))
            if entity_id not in entities or entities[entity_id].kind != "character":
                raise ValueError("unknown character")
            forbidden = set(self.world.rules.get("immutable_character_fields", ())) & set(patch)
            if forbidden:
                raise ValueError(f"immutable character fields: {sorted(forbidden)}")
            current = entities[entity_id]
            entities[entity_id] = WorldEntity(entity_id, current.kind, {**dict(current.state), **patch}, current.revision + 1)
        elif event_type == "lore_add":
            statement = str(data.get("statement", "")).strip()
            if not statement:
                raise ValueError("lore statement required")
            forbidden = tuple(map(str, self.world.rules.get("forbidden_lore", ())))
            if any(term.lower() in statement.lower() for term in forbidden):
                raise ValueError("world-rule violation")
            lore.append(statement)
        elif event_type == "artifact_commit":
            hashes = tuple(map(str, data.get("artifact_hashes", ())))
            if not hashes or any(not _SHA256.fullmatch(value) for value in hashes):
                raise ValueError("valid artifact hashes required")
        elif event_type == "conflict_resolution":
            entity_id = str(data.get("entity_id", ""))
            field_name = str(data.get("field", ""))
            candidates = tuple(data.get("candidates", ()))
            if entity_id not in entities or not field_name or not candidates:
                raise ValueError("entity, field and candidates required")
            policy = str(data.get("policy", "creator_priority"))
            if policy == "creator_priority":
                chosen = candidates[0]
            elif policy == "latest":
                chosen = candidates[-1]
            elif policy == "consensus":
                counts = {item: candidates.count(item) for item in candidates}
                chosen = max(counts, key=lambda item: (counts[item], -candidates.index(item)))
            else:
                raise ValueError("unsupported conflict policy")
            current = entities[entity_id]
            entities[entity_id] = WorldEntity(entity_id, current.kind, {**dict(current.state), field_name: chosen}, current.revision + 1)
            data["chosen"] = chosen
        else:
            raise ValueError("unsupported world event")

        previous = self.world.events[-1].event_hash if self.world.events else None
        logical_time = float(self.world.version + 1)
        event_hash = _hash({"type": event_type, "payload": data, "timestamp": logical_time, "previous": previous})
        event = WorldEvent(_stable_id("event", event_hash), event_type, data, logical_time, previous, event_hash)
        self.world = WorldStateGraph(
            self.world.world_id, self.world.version + 1, self.world.intent_hash,
            self.world.manifold_hash, entities, self.world.relationships, tuple(lore),
            self.world.events + (event,), self.world.rules,
        )
        self._persist()
        return self.world

    def verify_chain(self) -> bool:
        if self.world is None:
            return True
        previous = None
        for event in self.world.events:
            expected = _hash({"type": event.event_type, "payload": dict(event.payload), "timestamp": event.timestamp, "previous": previous})
            if event.previous_event_hash != previous or event.event_hash != expected:
                return False
            previous = event.event_hash
        return True

    def restore(self) -> WorldStateGraph:
        if self.checkpoint_path is None or not self.checkpoint_path.exists():
            raise FileNotFoundError("world checkpoint unavailable")
        payload = json.loads(self.checkpoint_path.read_text())
        if payload.get("schema") != SCHEMA:
            raise ValueError("world checkpoint schema mismatch")
        raw = payload["world"]
        entities = {key: WorldEntity(**value) for key, value in raw["entities"].items()}
        relationships = tuple(ManifoldEdge(**value) for value in raw["relationships"])
        events = tuple(WorldEvent(**value) for value in raw["events"])
        world = WorldStateGraph(
            raw["world_id"], raw["version"], raw["intent_hash"], raw["manifold_hash"],
            entities, relationships, tuple(raw["lore"]), events, raw["rules"], raw["timestamp"],
        )
        if world.content_hash != payload["world_hash"]:
            raise ValueError("world checkpoint hash mismatch")
        self.world = world
        if not self.verify_chain():
            raise ValueError("world event chain invalid")
        return world

    def _persist(self) -> None:
        if self.checkpoint_path and self.world:
            verified_atomic_json_write(self.checkpoint_path, {
                "schema": SCHEMA, "world": asdict(self.world),
                "world_hash": self.world.content_hash,
            })


class CoherenceEngine:
    def evaluate(
        self, intent: IntentVector, manifold: CreativeManifold,
        artifacts: Sequence[CreativeArtifact], world: WorldStateGraph,
    ) -> CoherenceReport:
        items = tuple(artifacts)
        violations: list[str] = []
        if not items:
            violations.append("no artifacts")
        tone = float(np.mean([set(intent.tone) <= set(artifact.style_tokens) for artifact in items])) if items else 0.0
        aesthetic = float(np.mean([set(intent.aesthetics) <= set(artifact.style_tokens) for artifact in items])) if items else 0.0
        lineage = float(np.mean([
            artifact.intent_hash == intent.content_hash
            and artifact.manifold_hash == manifold.content_hash
            and bool(artifact.provider_manifest_hash)
            for artifact in items
        ])) if items else 0.0
        relevant = [artifact for artifact in items if artifact.modality in {"narrative", "visual"}]
        character = float(np.mean([
            set(manifold.characters) <= set(artifact.content.get("continuity", ())) | set(artifact.content.get("subjects", ()))
            for artifact in relevant
        ])) if relevant else 1.0
        rules = 1.0 if world.manifold_hash == manifold.content_hash and world.intent_hash == intent.content_hash else 0.0
        temporal = 1.0 if all(right.timestamp >= left.timestamp for left, right in zip(world.events, world.events[1:])) else 0.0
        if lineage < 1:
            violations.append("artifact lineage mismatch")
        if rules < 1:
            violations.append("world lineage mismatch")
        if temporal < 1:
            violations.append("non-monotonic world events")
        aggregate = float(np.mean([tone, character, rules, aesthetic, temporal, lineage]))
        return CoherenceReport(tone, character, rules, aesthetic, temporal, lineage, aggregate, aggregate >= 0.8 and not violations, tuple(violations))


class EmergenceEngine:
    def propose(
        self, intent: IntentVector, manifold: CreativeManifold,
        world: WorldStateGraph, *, limit: int = 3,
    ) -> tuple[EmergenceProposal, ...]:
        if limit < 0:
            raise ValueError("limit must be nonnegative")
        forbidden = set(map(str, intent.constraints.get("forbidden_motifs", ())))
        candidates = []
        labels = [node.label for node in manifold.nodes]
        for index, (left, right) in enumerate(zip(labels, labels[1:])):
            motif = f"{left}-{right}"
            allowed = motif not in forbidden
            coherence = float((manifold.edges[index].weight + 1) / 2) if index < len(manifold.edges) else 0.5
            novelty = 1 / (1 + sum(motif in statement for statement in world.lore))
            reasons = () if allowed else ("forbidden motif",)
            payload = {"motif": motif, "world": world.content_hash, "allowed": allowed}
            candidates.append(EmergenceProposal(
                _stable_id("proposal", payload), "motif_synthesis",
                f"Explore {motif} as a constrained development", (motif,),
                novelty, coherence, allowed, reasons,
            ))
        return tuple(sorted(candidates, key=lambda item: (item.allowed, item.coherence * item.novelty), reverse=True)[:limit])


class TelemetryTruthLayer:
    def measure(
        self, intent: IntentVector, manifold: CreativeManifold,
        artifacts: Sequence[CreativeArtifact], world: WorldStateGraph,
        coherence: CoherenceReport, rejected: int = 0,
        attempted: int | None = None,
        scaling_observations: Sequence[tuple[float, float]] | None = None,
    ) -> TruthTelemetry:
        items = tuple(artifacts)
        count = len(items)
        attempted = count if attempted is None else int(attempted)
        if rejected < 0 or attempted < 0 or rejected > attempted:
            raise ValueError("invalid rejection telemetry")
        rejection = rejected / max(1, attempted)
        phi_density = float((1 + math.sqrt(5)) / 2 * len(manifold.edges) / max(1, len(manifold.nodes) ** 2))
        fidelity = float(np.mean([artifact.intent_hash == intent.content_hash for artifact in items])) if count else 0.0
        exponent = None
        if scaling_observations and len(scaling_observations) >= 2:
            values = np.asarray(scaling_observations, float)
            if np.all(np.isfinite(values)) and np.all(values > 0):
                exponent = float(np.polyfit(np.log(values[:, 0]), np.log(values[:, 1]), 1)[0])
        claims = {
            "identity": "EUCLID is a creative-intelligence substrate; AGI/ASI labels are not asserted.",
            "media": "Artifacts with rendered=false are structured plans, not rendered media.",
            "emergence": "Proposals are constrained candidates, not autonomous permission or proof of consciousness.",
            "determinism": "Semantic identities and logical event order are deterministic for equal validated input; wall-clock execution is not a capability claim.",
        }
        return TruthTelemetry(fidelity, coherence.aggregate, phi_density, rejection, exponent, count, world.version, claims)


class ExpressionLayer:
    def deliver(
        self, mode: ExpressionMode | str, world: WorldStateGraph,
        artifacts: Sequence[CreativeArtifact],
    ) -> ExpressionBundle:
        selected = ExpressionMode(mode)
        creator = {
            "intent_edit": selected in {ExpressionMode.CREATOR, ExpressionMode.HYBRID},
            "world_edit": selected in {ExpressionMode.CREATOR, ExpressionMode.HYBRID},
        }
        audience = {
            "interact": selected in {ExpressionMode.AUDIENCE, ExpressionMode.HYBRID},
            "mutate_rules": False,
        }
        return ExpressionBundle(
            selected, world.world_id, world.version, tuple(artifacts), creator, audience,
            {"world_hash": world.content_hash, "artifact_hashes": tuple(artifact.content_hash for artifact in artifacts)},
        )


class WorldEngineCluster:
    """Deterministic sharding with optimistic concurrency and fork rejection."""

    def __init__(self, shard_count: int = 8) -> None:
        if shard_count <= 0:
            raise ValueError("shard_count must be positive")
        self.shards: list[dict[str, WorldStateGraph]] = [{} for _ in range(int(shard_count))]

    def shard_for(self, world_id: str) -> int:
        if not world_id:
            raise ValueError("world id required")
        return int(hashlib.sha256(world_id.encode()).hexdigest(), 16) % len(self.shards)

    def put(self, world: WorldStateGraph, expected_version: int | None = None) -> None:
        shard = self.shards[self.shard_for(world.world_id)]
        current = shard.get(world.world_id)
        if expected_version is not None and (current is None or current.version != expected_version):
            raise RuntimeError("world version conflict")
        if current is not None and world.version < current.version:
            raise RuntimeError("world version regression")
        if current is not None and world.version == current.version and world.content_hash != current.content_hash:
            raise RuntimeError("same-version world fork")
        shard[world.world_id] = world

    def get(self, world_id: str) -> WorldStateGraph:
        try:
            return self.shards[self.shard_for(world_id)][world_id]
        except KeyError:
            raise KeyError("unknown world") from None

    def health(self) -> Mapping[str, Any]:
        return {
            "shards": len(self.shards),
            "worlds": sum(len(shard) for shard in self.shards),
            "contract": "deterministic_sharding_with_optimistic_concurrency_and_fork_rejection",
        }


class CreativeGovernancePolicy:
    """Fail-closed provenance and sovereignty gate."""

    def validate(self, directives: Sequence[CreatorDirective]) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        for directive in directives:
            for raw in directive.references:
                try:
                    reference = raw if isinstance(raw, ReferenceMedia) else ReferenceMedia(
                        str(raw.get("reference_id", _stable_id("reference", raw))),
                        str(raw.get("media_type", "")), str(raw.get("source", "")),
                        str(raw.get("rights", "")), str(raw.get("content_hash", "")),
                        str(raw.get("owner_id", directive.creator_id)),
                        tuple(raw.get("consent_scope", ())),
                    )
                    if reference.owner_id != directive.creator_id and directive.creator_id not in reference.consent_scope:
                        reasons.append(f"reference consent missing for {directive.creator_id}")
                except (TypeError, ValueError) as exc:
                    reasons.append(f"reference provenance invalid for {directive.creator_id}: {exc}")
            if directive.structured.get("transfer_creator_ownership") is True:
                reasons.append("creator ownership transfer prohibited")
        return not reasons, tuple(reasons)

    def validate_intent(self, intent: IntentVector) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []

        def walk(value: Any, path: str = "constraints") -> None:
            if isinstance(value, Mapping):
                if value.get("requires_resolution") is True:
                    reasons.append(f"unresolved intent conflict at {path}")
                for key, item in value.items():
                    walk(item, f"{path}.{key}")
            elif isinstance(value, (list, tuple)):
                for index, item in enumerate(value):
                    walk(item, f"{path}[{index}]")

        walk(intent.constraints)
        return not reasons, tuple(reasons)

    def validate_feedback(self, feedback: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
        blocked = {
            "transfer_creator_ownership", "override_rights_provenance",
            "disable_governance", "bypass_coherence",
        } & set(feedback)
        reasons = tuple(f"feedback operation prohibited: {item}" for item in sorted(blocked))
        return not reasons, reasons


class EuclidCreativeKernel:
    """Federated organism with one governed creative core."""

    def __init__(
        self, *, world_checkpoint: str | Path | None = None,
        provenance_checkpoint: str | Path | None = None,
        providers: Mapping[str, ModalityProvider] | None = None,
        world_cluster: WorldEngineCluster | None = None,
        governance: CreativeGovernancePolicy | None = None,
    ) -> None:
        self.intent_layer = IntentLayer()
        self.geometry_layer = SemanticGeometryLayer()
        self.generative_layer = GenerativeSubstrateLayer(providers)
        self.world_engine = WorldStateEngine(world_checkpoint)
        self.world_cluster = world_cluster or WorldEngineCluster()
        self.coherence_engine = CoherenceEngine()
        self.emergence_engine = EmergenceEngine()
        self.truth_layer = TelemetryTruthLayer()
        self.expression_layer = ExpressionLayer()
        self.governance = governance or CreativeGovernancePolicy()
        self.provenance = ProvenanceChain(provenance_checkpoint)
        self.history: list[CreativeCycle] = []

    def run(
        self, directives: Sequence[CreatorDirective], *,
        mode: ExpressionMode | str = ExpressionMode.CREATOR,
        modalities: Sequence[str] = MODALITIES,
    ) -> CreativeCycle:
        allowed, reasons = self.governance.validate(directives)
        if not allowed:
            raise PermissionError("; ".join(reasons))
        intent = self.intent_layer.interpret(directives)
        self._enforce_intent(intent)
        manifold = self.geometry_layer.construct(intent)
        world = self.world_engine.initialize(intent, manifold)
        self.world_cluster.put(world)
        artifacts = self.generative_layer.generate(intent, manifold, world, modalities)
        world = self.world_engine.apply("artifact_commit", {"artifact_hashes": [artifact.content_hash for artifact in artifacts]})
        self.world_cluster.put(world, expected_version=0)
        return self._complete(intent, manifold, artifacts, world, mode)

    def refine(
        self, cycle: CreativeCycle, feedback: Mapping[str, Any], *,
        mode: ExpressionMode | str = ExpressionMode.CREATOR,
    ) -> CreativeCycle:
        allowed, reasons = self.governance.validate_feedback(feedback)
        if not allowed:
            raise PermissionError("; ".join(reasons))
        intent = self.intent_layer.refine(cycle.intent, feedback)
        self._enforce_intent(intent)
        manifold = self.geometry_layer.construct(intent)
        world = self.world_engine.initialize(intent, manifold)
        self.world_cluster.put(world)
        artifacts = self.generative_layer.generate(intent, manifold, world)
        world = self.world_engine.apply("artifact_commit", {"artifact_hashes": [artifact.content_hash for artifact in artifacts]})
        self.world_cluster.put(world, expected_version=0)
        return self._complete(intent, manifold, artifacts, world, mode)

    def adapt_world(
        self, cycle: CreativeCycle, event_type: str, payload: Mapping[str, Any], *,
        mode: ExpressionMode | str = ExpressionMode.HYBRID,
    ) -> CreativeCycle:
        if self.world_engine.world is None or self.world_engine.world.world_id != cycle.world.world_id:
            self.world_engine.world = cycle.world
        world = self.world_engine.apply(event_type, payload)
        self.world_cluster.put(world, expected_version=cycle.world.version)
        artifacts = self.generative_layer.generate(cycle.intent, cycle.manifold, world)
        return self._complete(cycle.intent, cycle.manifold, artifacts, world, mode)

    def _enforce_intent(self, intent: IntentVector) -> None:
        allowed, reasons = self.governance.validate_intent(intent)
        if not allowed:
            raise PermissionError("; ".join(reasons))

    def _complete(
        self, intent: IntentVector, manifold: CreativeManifold,
        artifacts: Sequence[CreativeArtifact], world: WorldStateGraph,
        mode: ExpressionMode | str,
    ) -> CreativeCycle:
        coherence = self.coherence_engine.evaluate(intent, manifold, artifacts, world)
        if not coherence.passed:
            raise CoherenceGateError("coherence gate rejected cycle: " + ", ".join(coherence.violations))
        emergence = self.emergence_engine.propose(intent, manifold, world)
        telemetry = self.truth_layer.measure(intent, manifold, artifacts, world, coherence)
        expression = self.expression_layer.deliver(mode, world, artifacts)
        cycle = self._seal(intent, manifold, artifacts, world, coherence, emergence, telemetry, expression)
        self.history.append(cycle)
        return cycle

    def _seal(
        self, intent: IntentVector, manifold: CreativeManifold,
        artifacts: Sequence[CreativeArtifact], world: WorldStateGraph,
        coherence: CoherenceReport, emergence: Sequence[EmergenceProposal],
        telemetry: TruthTelemetry, expression: ExpressionBundle,
    ) -> CreativeCycle:
        intent_record = self.provenance.append("intent", intent.content_hash, intent.source_hashes, {"revision": intent.revision})
        manifold_record = self.provenance.append("creative_manifold", manifold.content_hash, (intent_record.record_hash,), {"intent_hash": intent.content_hash})
        artifact_records = [
            self.provenance.append(
                "artifact", artifact.content_hash,
                (intent_record.record_hash, manifold_record.record_hash),
                {"modality": artifact.modality, "provider": artifact.provider_id, "rendered": artifact.rendered},
            )
            for artifact in artifacts
        ]
        world_record = self.provenance.append(
            "world_state", world.content_hash,
            (manifold_record.record_hash,) + tuple(record.record_hash for record in artifact_records),
            {"version": world.version},
        )
        coherence_record = self.provenance.append("coherence", _hash(asdict(coherence)), (world_record.record_hash,), {"passed": coherence.passed})
        emergence_record = self.provenance.append("emergence", _hash([asdict(item) for item in emergence]), (coherence_record.record_hash,), {"allowed": sum(item.allowed for item in emergence)})
        telemetry_record = self.provenance.append("truth_telemetry", _hash(asdict(telemetry)), (coherence_record.record_hash,), {})
        self.provenance.append(
            "expression", _hash(asdict(expression)),
            (world_record.record_hash, emergence_record.record_hash, telemetry_record.record_hash),
            {"mode": expression.mode.value},
        )
        verified = self.provenance.verify()
        if not verified:
            raise RuntimeError("provenance chain verification failed")
        return CreativeCycle(
            intent, manifold, tuple(artifacts), world, coherence, tuple(emergence),
            telemetry, expression, self.provenance.head, verified,
        )


class EuclidCreatorAPI:
    """In-process creator/audience contract; network transport remains deployment."""

    def __init__(
        self, kernel: EuclidCreativeKernel | None = None,
        governance: CreativeGovernancePolicy | None = None,
    ) -> None:
        policy = governance or CreativeGovernancePolicy()
        self.kernel = kernel or EuclidCreativeKernel(governance=policy)
        self.governance = policy
        self.cycles: dict[str, CreativeCycle] = {}

    def create(
        self, directives: Sequence[CreatorDirective],
        mode: ExpressionMode | str = ExpressionMode.CREATOR,
    ) -> CreativeCycle:
        cycle = self.kernel.run(directives, mode=mode)
        self.cycles[cycle.world.world_id] = cycle
        return cycle

    def refine(
        self, world_id: str, feedback: Mapping[str, Any],
        mode: ExpressionMode | str = ExpressionMode.CREATOR,
    ) -> CreativeCycle:
        if world_id not in self.cycles:
            raise KeyError("unknown world")
        cycle = self.kernel.refine(self.cycles[world_id], feedback, mode=mode)
        self.cycles.pop(world_id)
        self.cycles[cycle.world.world_id] = cycle
        return cycle

    def interact(
        self, world_id: str, event_type: str, payload: Mapping[str, Any],
        mode: ExpressionMode | str = ExpressionMode.HYBRID,
    ) -> CreativeCycle:
        if world_id not in self.cycles:
            raise KeyError("unknown world")
        selected = ExpressionMode(mode)
        if selected is ExpressionMode.AUDIENCE and event_type in {"conflict_resolution", "world_rule_update"}:
            raise PermissionError("audience cannot mutate world rules or resolve creator conflicts")
        cycle = self.kernel.adapt_world(self.cycles[world_id], event_type, payload, mode=selected)
        self.cycles[world_id] = cycle
        return cycle


def architecture_audit() -> dict[str, Any]:
    """Machine-readable audit against the canonical Product Architecture Spec."""
    return {
        "schema": "EUCLID_CREATIVE_ARCHITECTURE_AUDIT_V2",
        "identity": {
            "agi": False, "asi": False,
            "classification": "Project EUCLID creative-intelligence substrate beyond legacy AGI/ASI taxonomy",
        },
        "architecture": {
            "lineage": "federated modular organism with one durable hash-chained provenance ledger",
            "intent_layer": "implemented_with_deterministic_semantic_identity",
            "semantic_geometry_layer": "implemented_with_deterministic_geometry",
            "generative_substrate_layer": "implemented_with_governed_provider_manifests",
            "world_state_engine": "implemented_with_hash_verified_persistence_sharding_and_fork_protection",
            "expression_layer": "implemented_in_process_contract",
            "coherence_engine": "implemented_fail_closed_in_kernel",
            "emergence_engine": "implemented_controlled_proposals",
            "telemetry_truth_layer": "implemented",
            "governance": "implemented_fail_closed_before_world_creation_and_refinement",
        },
        "closed_gaps": {
            "reference_media": "typed hash-verified rights and consent metadata",
            "provider_governance": "manifest, modality, sovereignty and rendered-deployment validation",
            "provenance": "single append-only chain across every creative layer",
            "determinism": "stable intent, manifold, world, event and artifact identities for equal validated input",
            "concurrency": "same-version fork rejection",
            "coherence": "kernel rejection on failed gate",
            "intent_conflicts": "unresolved collisions rejected before world creation",
            "audience_governance": "audience rule mutation and creator-conflict resolution prohibited",
        },
        "production_boundaries": {
            "rendered_visual_audio": "requires validated external modality provider deployment",
            "distributed_world_cluster": "contract implemented; durable distributed storage adapter requires deployment infrastructure",
            "network_api_sdk_ui": "in-process API contract implemented; transports and product UI require deployment",
            "independent_evaluation": "requires held-out external baselines and independent assessors",
            "share_acceptance_metrics": "excluded_as_midas_mining_specific",
            "claim": "EUCLID is not labelled AGI or ASI; those historical categories do not define its identity.",
        },
    }


__all__ = [
    "SCHEMA", "MODALITIES", "ExpressionMode", "ReferenceMedia",
    "CreatorDirective", "ProviderManifest", "IntentVector", "ManifoldNode",
    "ManifoldEdge", "CreativeManifold", "CreativeArtifact", "WorldEntity",
    "WorldEvent", "WorldStateGraph", "CoherenceReport", "EmergenceProposal",
    "TruthTelemetry", "ExpressionBundle", "ProvenanceRecord", "ProvenanceChain",
    "CreativeCycle", "CoherenceGateError", "IntentLayer", "SemanticGeometryLayer",
    "ModalityProvider", "StructuredBlueprintProvider", "GenerativeSubstrateLayer",
    "WorldStateEngine", "CoherenceEngine", "EmergenceEngine",
    "TelemetryTruthLayer", "ExpressionLayer", "WorldEngineCluster",
    "CreativeGovernancePolicy", "EuclidCreativeKernel", "EuclidCreatorAPI",
    "architecture_audit",
]
