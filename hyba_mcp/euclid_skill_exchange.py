"""Read-only MCP sharing of EUCLID-owned, custody-verified intelligence.

This is an adapter, not another learner, source of knowledge, or MCP server.
Skills are acquired by EUCLID's existing SkillLibrary during episodes and
persisted via EuclidRuntime's canonical adaptive-knowledge SystemDataPort.
Only already-promoted and durably verified skills may be exported or rendered.
External agents re-use the representation without repeating training.
Authentication/tenant/mission authorization is mandatory at EVERY call.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

_SKILL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_FEATURE = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_ROLE = re.compile(r"r[0-9]{1,2}\Z")
_MAX_OUTPUT_BYTES = 65536

def _tool(description: str, fields: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "description": description,
        "inputSchema": {"type": "object", "properties": fields,
                        "required": required, "additionalProperties": False},
    }

_MISSION = {"type": "string", "minLength": 1, "maxLength": 128}
_SKILL_ID = {"type": "string", "minLength": 1, "maxLength": 128}
_LIMIT = {"type": "integer", "minimum": 1, "maximum": 16}

EUCLID_SKILL_TOOLS = {
    "euclid_skills_list": _tool(
        "List promoted, custody-verified skills owned by the live EUCLID intelligence.",
        {"mission_id": _MISSION, "limit": _LIMIT}, ["mission_id"]),
    "euclid_skill_get": _tool(
        "Get a promoted EUCLID skill's sealed representation, provenance and bounds.",
        {"mission_id": _MISSION, "skill_id": _SKILL_ID},
        ["mission_id", "skill_id"]),
    "euclid_skill_render": _tool(
        "Instantiate a qualified EUCLID mathematical skill as portable operator "
        "specification. Never executes actions, runs training, or grants authority.",
        {"mission_id": _MISSION, "skill_id": _SKILL_ID,
         "roles": {"type": "object"}, "fill": {"type": "integer", "minimum": -32, "maximum": 32}},
        ["mission_id", "skill_id", "roles"]),
    "euclid_memory_recall": _tool(
        "Recall structurally relevant, OVID-custodied EUCLID team memory, with provenance.",
        {"mission_id": _MISSION,
         "features": {"type": "array", "minItems": 1, "maxItems": 32},
         "kinds": {"type": "array", "maxItems": 7}, "limit": _LIMIT},
        ["mission_id", "features"]),
}


class EuclidSkillExchange:
    """A scoped consumer of the EXISTING EUCLID runtime and persistent port.

    authorization: trusted AL HARAS or tenant-authority callback
    (actor_id, tenant_id, mission_id, tool_name) -> bool. Failure denies.
    The actor_id must be provided by the trusted MCP host, not tool arguments.
    """

    def __init__(
        self, runtime: Any,
        *,
        authorize: Callable[[str, str, str, str], bool],
    ) -> None:
        if not callable(authorize):
            raise TypeError("a trusted tenant- and mission-scoped authorizer is mandatory")
        self.runtime = runtime
        self.authorize = authorize

    @staticmethod
    def _identifier(value: Any, label: str) -> str:
        if type(value) is not str or not _SKILL.fullmatch(value):
            raise ValueError(f"{label} must be a bounded identifier")
        return value

    def _verified_knowledge(self) -> tuple[Any, str, str]:
        """Read back actual durable EUCLID knowledge, never an uncommitted copy."""
        from euclid.cognition.integrated.memory import AgentKnowledge

        runtime = self.runtime
        # This is the canonical runtime synchronization lock: a learning
        # episode cannot publish a half-written skill or checkpoint.
        lock = getattr(runtime, "_adaptive_lock", None)
        if lock is None:
            raise RuntimeError("EUCLID runtime is not composed")
        with lock:
            if getattr(runtime, "_closed", True) or getattr(runtime, "adaptive", None) is None:
                raise RuntimeError("EUCLID adaptive cognition unavailable")
            port = getattr(runtime, "_adaptive_data_port", None)
            if port is None:
                raise RuntimeError("EUCLID persistent knowledge custody is not bound")
            kind = runtime.ADAPTIVE_KNOWLEDGE_KIND
            binding = port.latest(kind)
            if binding is None:
                raise RuntimeError("EUCLID has no committed knowledge checkpoint")
            # Canonical runtime verifies fabric index, content hash, schema,
            # creator/tenant identity, seal and physical persistence.
            payload = runtime._read_adaptive_binding(binding)
            knowledge = AgentKnowledge.from_payload(payload["knowledge"])
            live_seal = runtime.adaptive.knowledge.to_payload()["seal"]
            durable_seal = payload["knowledge"]["seal"]
            if live_seal != durable_seal:
                raise RuntimeError("latest EUCLID learning has not been durably committed")
            return knowledge, str(payload["tenant_id"]), binding.binding_id

    def _authorize(self, actor_id: Any, tenant_id: str, mission_id: Any, tool: str) -> str:
        if type(actor_id) is not str or not actor_id.strip():
            raise PermissionError("authenticated MCP identity required")
        mission = self._identifier(mission_id, "mission_id")
        try:
            allowed = self.authorize(actor_id, tenant_id, mission, tool)
        except Exception as exc:
            raise PermissionError("EUCLID access authorizer unavailable") from exc
        if allowed is not True:
            raise PermissionError("EUCLID mission access denied")
        return mission

    @staticmethod
    def _promoted(library: Any, skill_id: str) -> Any:
        record = library.records.get(skill_id)
        if record is None or record.status != "promoted":
            raise ValueError("EUCLID skill is not qualified or is no longer available")
        if not record.semantic or record.adversarial_failures != 0 \
                or record.held_out_utility is None or record.held_out_utility <= 0:
            raise ValueError("EUCLID skill evidence requirements are not met")
        return record

    @staticmethod
    def _mechanism(value: Any) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": value.kind, "params": list(value.params)}
        if value.inner is not None:
            result["inner"] = EuclidSkillExchange._mechanism(value.inner)
        if value.second is not None:
            result["second"] = EuclidSkillExchange._mechanism(value.second)
        return result

    @staticmethod
    def _validate_arguments(tool: str, arguments: Any) -> dict[str, Any]:
        if tool not in EUCLID_SKILL_TOOLS or not isinstance(arguments, dict):
            raise ValueError("unknown EUCLID tool or invalid arguments")
        schema = EUCLID_SKILL_TOOLS[tool]["inputSchema"]
        if arguments.keys() - schema["properties"].keys() \
                or set(schema["required"]) - arguments.keys():
            raise ValueError("unknown or missing EUCLID tool arguments")
        EuclidSkillExchange._identifier(arguments["mission_id"], "mission_id")
        if "skill_id" in arguments:
            EuclidSkillExchange._identifier(arguments["skill_id"], "skill_id")
        limit = arguments.get("limit", 16)
        if type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("limit must be an integer in [1,16]")
        if tool == "euclid_skill_render":
            roles = arguments["roles"]
            if type(roles) is not dict or len(roles) > 16 \
                    or any(type(k) is not str or not _ROLE.fullmatch(k) or
                           type(v) is not int or not 0 <= v <= 63
                           for k,v in roles.items()) \
                    or len(set(roles.values())) != len(roles):
                raise ValueError("role indices must be unique, bounded integers")
            fill = arguments.get("fill", 1)
            if type(fill) is not int or not -32 <= fill <= 32:
                raise ValueError("fill must be a bounded integer")
        if tool == "euclid_memory_recall":
            features = arguments["features"]
            if not isinstance(features, list) or not 1 <= len(features) <= 32 \
                    or any(type(x) is not str or not _FEATURE.fullmatch(x) for x in features):
                raise ValueError("1 to 32 structural feature identifiers required")
            kinds = arguments.get("kinds", [])
            if not isinstance(kinds, list) or len(kinds) > 7 \
                    or any(type(x) is not str for x in kinds):
                raise ValueError("invalid memory kind selector")
        return arguments

    def execute_tool(
        self, name: str, arguments: dict[str, Any], *, actor_id: str,
    ) -> dict[str, Any]:
        """Read one committed EUCLID generation and return scoped results."""
        from euclid.cognition.integrated.skills import _roles_of, instantiate
        from euclid.cognition.state import MemoryKind

        args = self._validate_arguments(name, arguments)
        # Authorize BEFORE inspecting custody or revealing whether it exists.
        tenant = getattr(self.runtime, "_adaptive_tenant_id", "")
        self._authorize(actor_id, tenant, args["mission_id"], name)
        knowledge, persisted_tenant, binding_id = self._verified_knowledge()
        if tenant != persisted_tenant:
            raise PermissionError("EUCLID custody tenant mismatch")
        library = knowledge.skills

        if name == "euclid_skills_list":
            records = [
                record for record in sorted(library.records.values(), key=lambda item: item.skill_id)
                if record.status == "promoted" and record.semantic
                and record.adversarial_failures == 0 and record.held_out_utility is not None
                and record.held_out_utility > 0
            ][:args.get("limit", 16)]
            return {"owner": "EUCLID", "custody_binding": binding_id,
                    "skills": [
                        {"skill_id": record.skill_id, "level": record.level,
                         "semantic": record.semantic, "seal": library.seal(record),
                         "surfaces": sorted(record.surfaces)}
                        for record in records
                    ], "training_required_for_consumer": False}
        if name in {"euclid_skill_get", "euclid_skill_render"}:
            record = self._promoted(library, args["skill_id"])
            body = library.to_payload()
            sealed_row = next(row for row in body["skills"] if row["skill_id"] == record.skill_id)
            if name == "euclid_skill_get":
                return {"owner": "EUCLID", "custody_binding": binding_id,
                        "skill": {
                            "skill_id": record.skill_id, "status": record.status,
                            "level": record.level, "pattern": sealed_row["pattern_json"],
                            "semantic_digest": record.semantic, "seal": sealed_row["seal"],
                            "support_count": len(record.support),
                            "surfaces": sorted(record.surfaces),
                            "held_out_utility": record.held_out_utility,
                            "provenance": record.provenance,
                            "adversarial_failures": record.adversarial_failures,
                        }, "training_required_for_consumer": False}
            roles = args["roles"]
            if set(roles) != set(_roles_of(record.pattern, [])):
                raise ValueError("skill role binding must match the qualified pattern")
            instructions = instantiate(record.pattern, roles, fill=args.get("fill", 1))
            return {"owner": "EUCLID", "custody_binding": binding_id,
                    "skill_id": record.skill_id, "semantic_digest": record.semantic,
                    "operators": [self._mechanism(m) for m in instructions],
                    "execution_performed": False, "authority_granted": False}

        # StructuralMemory items carry no mission binding, so retrieval cannot
        # be confined to the authorized mission. Fail closed rather than expose
        # another mission's episodes; re-enable once items are mission-scoped.
        raise PermissionError("EUCLID memory recall is not mission-scoped and is denied")
        kinds = args.get("kinds", [])
        types = [MemoryKind(x) for x in kinds] if kinds else None
        records = knowledge.memory.retrieve(frozenset(args["features"]), kinds=types)
        results = []
        for item in records[:args.get("limit", 16)]:
            body = {"memory_id": item.memory_id, "kind": item.kind.value,
                    "payload": dict(item.payload), "provenance": item.provenance,
                    "structural_features": sorted(item.structural_features),
                    "transfer_value": item.transfer_value}
            encoded = __import__("json").dumps(body, allow_nan=False, sort_keys=True).encode()
            if len(encoded) > 8192:
                raise RuntimeError("memory item exceeds bounded MCP context window")
            results.append(body)
        return {"owner": "EUCLID", "custody_binding": binding_id,
                "memory": results, "recall_method": "EUCLID_STRUCTURAL_MEMORY",
                "theoretical_context_window_increase": False,
                "retraining_required_for_consumer": False}
