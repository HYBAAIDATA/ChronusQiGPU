"""Instance-local capability contracts and guarded governed invocation."""
import json
from . import server as base
from .capability_contracts import ContractError, decompose_goal, validate_plan
from .production_contracts import ContractViolation, bounded_json, capability_definition, failure, validate_value
from .skills import discover_skills

def tool(description, properties, required):
    return {"description": description, "inputSchema": {"type": "object", "properties": properties,
        "required": required, "additionalProperties": False}}

CAPABILITY_TOOLS = {
    "goal_decompose": tool("Normalize explicit registered subgoals; no semantic inference.", {"goal_contract": {"type": "object"}}, ["goal_contract"]),
    "plan_validate": tool("Validate structure and skill inputs without granting authority.", {"plan": {"type": "object"}}, ["plan"]),
    "capability_contract": tool("Return a versioned skill definition, digest and authority limits.", {"skill_id": {"type": "string", "minLength": 1, "maxLength": 256}}, ["skill_id"]),
    "capability_invoke": tool("Invoke through existing authorization, audit and sandbox gates with strict input/output guards.",
        {"skill_id": {"type": "string", "minLength": 1, "maxLength": 256}, "arguments": {"type": "object"},
         "options": {"type": "object", "properties": {
             "constraints": {"type": "object", "properties": {
                 "max_cost": {"type": "number", "minimum": 0}, "max_risk": {"type": "number", "minimum": 0, "maximum": 1},
                 "max_seconds": {"type": "number", "minimum": 0}}, "additionalProperties": False},
             "sandbox": {"type": "object", "properties": {
                 "timeout_seconds": {"type": "number", "minimum": 0.001, "maximum": 30},
                 "cpu_seconds": {"type": "integer", "minimum": 1, "maximum": 15},
                 "memory_bytes": {"type": "integer", "minimum": 1, "maximum": 2147483648},
                 "max_input_bytes": {"type": "integer", "minimum": 1, "maximum": 1048576},
                 "max_output_bytes": {"type": "integer", "minimum": 1, "maximum": 1048576}}, "additionalProperties": False}},
             "additionalProperties": False}}, ["skill_id", "arguments"]),
}

class CapabilityMCPServer:
    """Compose the existing server without changing its global registry.

    Trusted host constructor arguments are forwarded to HybaMCPServer.
    The existing CLI and deployment credentials are not changed.
    """
    def __init__(self, *args, **kwargs):
        self.base = base.HybaMCPServer(*args, **kwargs)

    def execute_tool(self, name, arguments):
        if name not in CAPABILITY_TOOLS:
            return self.base.execute_tool(name, arguments)
        try:
            validate_value(arguments, CAPABILITY_TOOLS[name]["inputSchema"])
        except ContractViolation:
            return failure("invalid_contract")
        try:
            catalog = {entry["skill_id"]: entry for entry in discover_skills()}
            if name in {"capability_contract", "capability_invoke"}:
                entry = catalog.get(arguments["skill_id"])
                if entry is None: return failure("unknown_capability")
                try: definition = capability_definition(entry)
                except ContractViolation: return failure("unsupported_contract")
                if name == "capability_contract": return {"ok": True, "capability": definition}
                try: validate_value(arguments["arguments"], definition["input_schema"])
                except ContractViolation: return failure("invalid_contract")
                result = self.base.execute_tool("invoke_skill", arguments)
                if result.get("ok") is not True:
                    code = result.get("error", {}).get("code")
                    return failure(code if code in {"permission_denied", "timeout"} else "execution_failed")
                try:
                    validate_value(result.get("result"), definition["output_schema"])
                    bounded_json(result)
                except ContractViolation: return failure("invalid_output")
                return {"ok": True, "contract_digest": definition["contract_digest"], "invocation": result}
            if name == "goal_decompose":
                result = decompose_goal(arguments["goal_contract"], catalog)
                plan = result.get("plan")
            else:
                plan = arguments["plan"]
                result = validate_plan(plan, catalog)
            if plan is not None:
                for node in plan["nodes"]:
                    validate_value(node["arguments"], capability_definition(catalog[node["skill_id"]])["input_schema"])
            bounded_json(result)
            return result
        except (ContractError, ContractViolation):
            return failure("invalid_contract")
        except Exception:
            return failure("internal_error")

    def handle_request(self, request):
        if not isinstance(request, dict): return self.base.handle_request(request)
        method, params = request.get("method"), request.get("params", {})
        if method == "tools/call" and isinstance(params, dict) and isinstance(params.get("name"), str) and params["name"] in CAPABILITY_TOOLS:
            if "id" not in request: return None
            rid = request["id"]
            if request.get("jsonrpc") != "2.0" or type(rid) not in (str, int, type(None)):
                return self.base._error(None, -32600, "Invalid Request")
            if not self.base._initialized or not self.base._ready:
                return self.base._error(rid, -32000, "Initialization required")
            if set(params) - {"name", "arguments"}: return self.base._error(rid, -32602, "Invalid arguments")
            result = self.execute_tool(params["name"], params.get("arguments", {}))
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(result, allow_nan=False)}],
                "structuredContent": result, "isError": result.get("ok") is False}}
        response = self.base.handle_request(request)
        if method == "tools/list" and isinstance(response, dict) and "result" in response:
            response["result"]["tools"].extend({"name": name, **definition} for name, definition in CAPABILITY_TOOLS.items())
        return response
