"""QC-corrected, instance-local MCP capability composition."""
import hashlib
import json
import time
import uuid
from . import server as base
from .capability_contracts import ContractError, decompose_goal, validate_plan
from .production_contracts import ContractViolation, bounded_json, capability_definition, failure, public_output, validate_value
from .skills import discover_skills

def tool(description, props, required):
    return {"description":description,"inputSchema":{"type":"object","properties":props,"required":required,"additionalProperties":False}}

OPTIONS = {"type":"object","properties":{
    "constraints":{"type":"object","properties":{k:{"type":"number","minimum":0} for k in ("max_cost","max_risk","max_seconds")},"additionalProperties":False},
    "sandbox":{"type":"object","properties":{k:{"type":t,"minimum":lo,"maximum":hi} for k,t,lo,hi in (
        ("timeout_seconds","number",.001,30),("cpu_seconds","integer",1,15),
        ("memory_bytes","integer",1,2147483648),("max_input_bytes","integer",1,1048576),
        ("max_output_bytes","integer",1,1048576))},"additionalProperties":False}},"additionalProperties":False}
OPTIONS["properties"]["constraints"]["properties"]["max_risk"]["maximum"]=1
CAPABILITY_TOOLS = {
    "goal_decompose":tool("Normalize explicit subgoals; no semantic planning.",{"goal_contract":{"type":"object"}},["goal_contract"]),
    "plan_validate":tool("Validate plan structure and skill inputs.",{"plan":{"type":"object"}},["plan"]),
    "capability_contract":tool("Return a validated versioned contract.",{"skill_id":{"type":"string","minLength":1,"maxLength":256}},["skill_id"]),
    "capability_invoke":tool("Governed execution with durable evidence and projected output.",{
        "skill_id":{"type":"string","minLength":1,"maxLength":256},"arguments":{"type":"object"},"options":OPTIONS},["skill_id","arguments"])}

def reference(record):
    if not isinstance(record,dict): return None
    h, n = record.get("record_hash"), record.get("sequence")
    if type(h) is str and len(h)==64 and all(c in "0123456789abcdef" for c in h) and type(n) is int and n>0:
        return {"record_hash":h,"sequence":n}
    return None

class CapabilityMCPServer:
    def __init__(self,*args,**kwargs):
        self.base = base.HybaMCPServer(*args,**kwargs)

    def _record(self, correlation, event, state, source=None):
        audit = self.base.control_plane.audit
        if not audit.durable or not audit.verify(): raise RuntimeError("durable audit unavailable")
        record = audit.append({"event":event,"correlation_id":correlation,"execution_id":correlation,
            "identity":self.base._trusted_identity(),"execution_status":state,"source_record":source,"timestamp":time.time()})
        ref = reference(record)
        if ref is None: raise RuntimeError("invalid audit reference")
        return ref

    def _fail(self,code,correlation,state="not_executed",output="not_available",source=None):
        result = failure(code,correlation)
        result.pop("execution_authorized",None)
        try:
            result["audit_record"] = self._record(correlation,"capability_incident",state,source)
            result["incident_persisted"] = True
        except Exception:
            result["audit_record"], result["incident_persisted"] = None, False
        result.update(execution_id=correlation,execution_status=state,output_status=output,
            source_record=source,rollback_performed=False)
        return result

    def execute_tool(self,name,arguments):
        if name not in CAPABILITY_TOOLS: return self.base.execute_tool(name,arguments)
        correlation, state, source = uuid.uuid4().hex,"not_executed",None
        try:
            validate_value(arguments,CAPABILITY_TOOLS[name]["inputSchema"])
            catalog = {s["skill_id"]:s for s in discover_skills()}
            if name in {"capability_contract","capability_invoke"}:
                entry = catalog.get(arguments["skill_id"])
                if entry is None: return self._fail("unknown_capability",correlation)
                try: definition=capability_definition(entry)
                except ContractViolation: return self._fail("unsupported_contract",correlation)
                if name=="capability_contract": return {"ok":True,"capability":definition}
                validate_value(arguments["arguments"],definition["input_schema"])
                try: dispatch=self._record(correlation,"capability_dispatch","not_executed")
                except Exception: return self._fail("audit_unavailable",correlation)
                state="unknown"
                invoked=self.base.execute_tool("invoke_skill",arguments)
                source=reference(invoked.get("audit_record")) or dispatch
                if invoked.get("ok") is not True:
                    code=invoked.get("error",{}).get("code")
                    if code in {"permission_denied","budget_exceeded","invalid_input","invalid_options","unknown_skill","invalid_sandbox_config"}: state="not_executed"
                    if code=="invalid_skill_output":
                        return self._fail("output_rejected",correlation,"completed","rejected",source)
                    return self._fail("permission_denied" if code=="permission_denied" else "execution_failed",correlation,state,source=source)
                state="completed"
                try: output=public_output(invoked.get("result"),definition["output_schema"])
                except ContractViolation: return self._fail("output_rejected",correlation,state,"rejected",source)
                try: evidence=self._record(correlation,"capability_output_accepted",state,source)
                except Exception: return self._fail("audit_unavailable",correlation,state,"accepted",source)
                result={"ok":True,"execution_id":correlation,"execution_status":state,"output_status":"accepted",
                    "contract_digest":definition["contract_digest"],"result":output,"audit_record":evidence,
                    "source_record":source,"theorem_proven":False}
                bounded_json(result)
                return result
            if name=="goal_decompose":
                result=decompose_goal(arguments["goal_contract"],catalog); plan=result.get("plan")
            else:
                plan=arguments["plan"]; result=validate_plan(plan,catalog)
            if plan is not None:
                for node in plan["nodes"]: validate_value(node["arguments"],capability_definition(catalog[node["skill_id"]])["input_schema"])
            bounded_json(result)
            return result
        except (ContractViolation,ContractError):
            return self._fail("output_rejected" if state=="completed" else "invalid_contract",correlation,state,
                "rejected" if state=="completed" else "not_available",source)
        except Exception:
            return self._fail("internal_error",correlation,state,source=source)

    def handle_request(self,request):
        rid=request.get("id") if isinstance(request,dict) else None
        if type(rid) not in (str,int,type(None)): rid=None
        response=None
        try:
            response=self._handle(request)
            if response is not None: bounded_json(response)
            return response
        except Exception:
            public=response.get("result",{}).get("structuredContent",{}) if isinstance(response,dict) else {}
            correlation=public.get("execution_id") if isinstance(public,dict) else None
            if type(correlation) is not str or len(correlation)!=32: correlation=uuid.uuid4().hex
            state=public.get("execution_status","unknown") if isinstance(public,dict) else "unknown"
            if state not in {"completed","not_executed","unknown"}: state="unknown"
            data=self._fail("internal_error",correlation,state)
            return {"jsonrpc":"2.0","id":rid,"error":{"code":-32603,"message":"Internal error","data":data}}

    def _handle(self,request):
        if not isinstance(request,dict): return self.base.handle_request(request)
        method,params=request.get("method"),request.get("params",{})
        if method=="tools/call" and isinstance(params,dict) and isinstance(params.get("name"),str) and params["name"] in CAPABILITY_TOOLS:
            if "id" not in request: return None
            rid=request["id"]
            if request.get("jsonrpc")!="2.0" or type(rid) not in (str,int,type(None)): return self.base._error(None,-32600,"Invalid Request")
            if not self.base._initialized or not self.base._ready: return self.base._error(rid,-32000,"Initialization required")
            if set(params)-{"name","arguments"}: return self.base._error(rid,-32602,"Invalid arguments")
            result=self.execute_tool(params["name"],params.get("arguments",{}))
            text=bounded_json(result)
            return {"jsonrpc":"2.0","id":rid,"result":{"content":[{"type":"text","text":text}],"structuredContent":result,"isError":result.get("ok") is False}}
        response=self.base.handle_request(request)
        if method=="tools/list" and isinstance(response,dict) and "result" in response:
            response=json.loads(bounded_json(response))
            tools=response["result"]["tools"]
            if {t["name"] for t in tools}&set(CAPABILITY_TOOLS): raise RuntimeError("tool collision")
            tools.extend({"name":n,**d} for n,d in CAPABILITY_TOOLS.items())
        return response
