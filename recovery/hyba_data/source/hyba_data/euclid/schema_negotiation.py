"""Self-Directed Schema Negotiation Engine. 19 July 2026."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from euclid.foundation_types import IOPEnvelope, IOPMessageType


class TransformType(Enum):
    RENAME = "rename"; SCALE = "scale"; INJECT_DEFAULT = "default"

@dataclass
class TranslationRule:
    source_key: str; target_key: str; transform_type: TransformType
    parameter: Optional[Any] = None

@dataclass
class SchemaMapping:
    source_schema_id: str; target_schema_id: str
    rules: List[TranslationRule] = field(default_factory=list)


class SchemaNegotiator:
    def __init__(self):
        self.active_mappings: Dict[Tuple[str, str], SchemaMapping] = {}

    def propose_translation_rules(self, peer_id: str, mapping: SchemaMapping) -> Tuple[bool, str]:
        for rule in mapping.rules:
            if rule.transform_type == TransformType.SCALE:
                if not isinstance(rule.parameter, (int, float)):
                    return (False, f"Invalid scale parameter for: {rule.source_key}")
            if rule.transform_type == TransformType.INJECT_DEFAULT and rule.parameter is None:
                return (False, f"Missing default for: {rule.source_key}")
        self.active_mappings[(mapping.source_schema_id, mapping.target_schema_id)] = mapping
        return (True, "Schema mapping registered.")

    def apply_translation(self, src: str, tgt: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        m = self.active_mappings.get((src, tgt))
        if not m: return (False, {}, "No registered mapping.")
        translated: Dict[str, Any] = {}
        try:
            for rule in m.rules:
                if rule.transform_type == TransformType.RENAME:
                    if rule.source_key in payload: translated[rule.target_key] = payload[rule.source_key]
                elif rule.transform_type == TransformType.SCALE:
                    if rule.source_key in payload:
                        v = payload[rule.source_key]
                        if isinstance(v, (int, float)) and isinstance(rule.parameter, (int, float)):
                            translated[rule.target_key] = v * rule.parameter
                        else:
                            return (False, {}, f"Non-numeric for scaling: {rule.source_key}")
                elif rule.transform_type == TransformType.INJECT_DEFAULT:
                    translated[rule.target_key] = payload.get(rule.source_key, rule.parameter)
            mapped_srcs = {r.source_key for r in m.rules}
            mapped_tgts = {r.target_key for r in m.rules}
            for k, v in payload.items():
                if k not in mapped_srcs and k not in mapped_tgts: translated[k] = v
            return (True, translated, "Translated.")
        except Exception as e:
            return (False, {}, f"Mapping failure: {e}")


class EnhancedIOPRouter:
    def __init__(self, organism_id: str, negotiator: SchemaNegotiator, secret: str = "test"):
        self.oid = organism_id; self.negotiator = negotiator; self.secret = secret
        self.peer_secrets: Dict[str, str] = {}

    def register_peer(self, pid: str, sec: str): self.peer_secrets[pid] = sec

    def handle_inbound_envelope(self, env: IOPEnvelope) -> Optional[IOPEnvelope]:
        if env.message_type.value == "negotiate" and "schema_proposal" in env.payload:
            md = env.payload["schema_proposal"]
            rules = [TranslationRule(
                r["source_key"], r["target_key"],
                TransformType(r["transform_type"]), r.get("parameter")
            ) for r in md.get("rules", [])]
            mapping = SchemaMapping(md["source_schema_id"], md["target_schema_id"], rules)
            ok, msg = self.negotiator.propose_translation_rules(env.sender_id, mapping)
            if not ok:
                return self._veto(env, f"Schema negotiation failed: {msg}")
            return IOPEnvelope(message_id=f"ack_{env.message_id}", sender_id=self.oid,
                receiver_id=env.sender_id, message_type=IOPMessageType.NEGOTIATE,
                payload={"status": "SCHEMA_MAPPING_ACCEPTED"})

        if env.message_type.value == "dispatch":
            src = env.payload.get("source_schema_id", "")
            tgt = env.payload.get("target_schema_id", "")
            if src and tgt and src != tgt:
                tp = env.payload.get("task_payload", {})
                ok, translated, reason = self.negotiator.apply_translation(src, tgt, tp)
                if not ok:
                    return self._veto(env, f"Schema mismatch: {reason}")
                env.payload["task_payload"] = translated
            return IOPEnvelope(message_id=f"res_{env.message_id}", sender_id=self.oid,
                receiver_id=env.sender_id, message_type=IOPMessageType.RESOLVE,
                payload={"task_id": env.payload.get("task_id", "?"), "status": "accepted"})
        return None

    def _veto(self, env, reason):
        return IOPEnvelope(message_id=f"veto_{env.message_id}", sender_id=self.oid,
            receiver_id=env.sender_id, message_type=IOPMessageType.VETO,
            payload={"reason": reason})
