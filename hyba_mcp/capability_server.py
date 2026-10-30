"""Opt-in MCP extension exposing read-only contract planning tools.

Embed CapabilityMCPServer instead of HybaMCPServer. Existing entrypoints and
transport behavior are not changed. All existing skill execution gates remain.
"""
from . import server as base
from .capability_contracts import ContractError, decompose_goal, fields, validate_plan
from .skills import discover_skills

CAPABILITY_TOOLS = {
    "goal_decompose": {
        "description": "Validate explicit structured subgoals; prose alone returns needs_clarification. No execution.",
        "inputSchema": {"type": "object", "properties": {"goal_contract": {"type": "object"}},
                        "required": ["goal_contract"], "additionalProperties": False},
        "outputSchema": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
    },
    "plan_validate": {
        "description": "Validate bounded DAG, registered skill inputs and declared criterion coverage. Never authorizes execution.",
        "inputSchema": {"type": "object", "properties": {"plan": {"type": "object"}},
                        "required": ["plan"], "additionalProperties": False},
        "outputSchema": {"type": "object", "properties": {"valid": {"type": "boolean"}}, "required": ["valid"]},
    },
}

class CapabilityMCPServer(base.HybaMCPServer):
    """Additive planning surface over the existing governed server.

    Existing protocol dispatcher uses a module-global tool registry, so opting
    in registers the planning tools for this process. Do not mix base and
    extension instances in one process: base instances cannot dispatch them.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, definition in CAPABILITY_TOOLS.items():
            if name in base.TOOLS and base.TOOLS[name] != definition:
                raise RuntimeError("capability tool registration conflict: " + name)
        base.TOOLS.update(CAPABILITY_TOOLS)

    def _validate_skill_inputs(self, plan):
        for node in plan["nodes"]:
            validation = self.control_plane.validate_inputs(node["skill_id"], node["arguments"])
            if not validation.get("valid"):
                raise ContractError("invalid skill arguments for node " + node["id"])

    def execute_tool(self, name, arguments):
        if name not in CAPABILITY_TOOLS:
            return super().execute_tool(name, arguments)
        try:
            catalog = {entry["skill_id"]: entry for entry in discover_skills()}
            if name == "goal_decompose":
                fields(arguments, ("goal_contract",))
                result = decompose_goal(arguments["goal_contract"], catalog)
                if result["status"] == "proposed":
                    self._validate_skill_inputs(result["plan"])
                return result
            fields(arguments, ("plan",))
            result = validate_plan(arguments["plan"], catalog)
            self._validate_skill_inputs(arguments["plan"])
            return result
        except ContractError as exc:
            if name == "plan_validate":
                return {"valid": False, "error": {"code": "invalid_contract", "message": str(exc)},
                        "execution_authorized": False, "theorem_proven": False}
            return {"status": "invalid", "error": {"code": "invalid_contract", "message": str(exc)},
                    "execution_authorized": False, "theorem_proven": False}
