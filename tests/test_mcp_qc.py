"""QC regressions. Fixtures never authorize a production deployment."""
import io
import json
import pytest
from hyba_mcp import capability_server as m
from hyba_mcp.production_contracts import ContractViolation, bounded_json, public_output, schema_contract, validate_value
from hyba_mcp.governed_server import serve

@pytest.mark.parametrize("schema",[
    {"type":"integer","properties":{}}, {"type":"string","minimum":0},
    {"type":"array","minLength":1}, {"type":["number","number"]},
    {"type":["object","string"]}, {"type":"integer","minimum":2,"maximum":1},
    {"type":"integer","minimum":.1,"maximum":.9},
    {"type":"string","minLength":2,"maxLength":1},
    {"type":"object","required":["missing"]},
    {"type":"integer","enum":["bad"]}, {"type":"number","enum":[1,1.0]},
    {"type":"integer","default":True}, {"type":"object","properties":{"x":{"type":"integer","items":{}}}},
])
def test_malformed_schema(schema):
    with pytest.raises(ContractViolation): schema_contract(schema)

def test_nullable_and_projection():
    validate_value(None,{"type":["number","null"],"minimum":0})
    assert public_output({"x":1,"secret":"no"},{"type":"object","properties":{"x":{"type":"integer"}},"required":["x"]})=={"x":1}

class Audit:
    durable=True
    def __init__(self): self.events=[]
    def verify(self): return True
    def append(self,event):
        self.events.append(event)
        return {"record_hash":format(len(self.events),'064x'),"sequence":len(self.events)}

class Base:
    def __init__(self,**kwargs):
        self._initialized=self._ready=True
        self.control_plane=type('CP',(),{'audit':Audit()})()
        self.calls=0
        self.output={"ok":True,"result":{"value":1,"private":"secret"},"private":"secret"}
    def _trusted_identity(self): return 'host-only'
    def execute_tool(self,name,args): self.calls+=1; return self.output
    def handle_request(self,request): return {"jsonrpc":"2.0","id":request.get('id'),"result":{"tools":[]}}
    @staticmethod
    def _error(rid,code,message): return {"jsonrpc":"2.0","id":rid,"error":{"code":code,"message":message}}

@pytest.fixture
def server(monkeypatch):
    entry={"skill_id":"fixture","source":"fixture.run","input_schema":{"type":"object","additionalProperties":False},
        "output_schema":{"type":"object","properties":{"value":{"type":"integer"}},"required":["value"]}}
    monkeypatch.setattr(m.base,'HybaMCPServer',Base)
    monkeypatch.setattr(m,'discover_skills',lambda:[entry])
    return m.CapabilityMCPServer()

def invoke(server): return server.execute_tool('capability_invoke',{'skill_id':'fixture','arguments':{}})

def test_public_envelope_and_incident_link(server):
    result=invoke(server)
    assert result['result']=={'value':1} and 'invocation' not in result and 'private' not in result
    assert server.base.calls==1
    assert server.base.control_plane.audit.events[-1]['execution_id']==result['execution_id']

def test_output_rejection_is_post_execution(server):
    server.base.output={'ok':True,'result':{'value':'wrong'}}
    result=invoke(server)
    assert result['execution_status']=='completed' and result['output_status']=='rejected'
    assert result['error']['retryable'] is False and result['incident_persisted']
    assert server.base.calls==1

def test_denial_is_not_execution(server):
    server.base.output={'ok':False,'error':{'code':'permission_denied','message':'secret'}}
    result=invoke(server)
    assert result['execution_status']=='not_executed'
    assert 'secret' not in json.dumps(result)

def test_audit_failure_prevents_dispatch(server):
    server.base.control_plane.audit.durable=False
    result=invoke(server)
    assert server.base.calls==0 and result['incident_persisted'] is False

def test_protocol_exception_contained(server,monkeypatch):
    monkeypatch.setattr(server.base,'handle_request',lambda request: {'result':{'tools':object()}})
    response=server.handle_request({'jsonrpc':'2.0','id':1,'method':'tools/list'})
    assert response['error']['code']==-32603
    bounded_json(response)

def test_stdio_rejects_duplicate_keys(server):
    reader=io.BytesIO(b'{"jsonrpc":"2.0","id":1,"id":2}\n')
    writer=io.StringIO(); serve(server,reader,writer)
    assert json.loads(writer.getvalue())['error']['code']==-32700

def test_real_authorization_and_spawned_skill(tmp_path):
    from hyba_mcp.control_plane import ControlPlane
    from hyba_mcp.capability_server import CapabilityMCPServer
    cp=ControlPlane(authorizer=lambda subject,skill,args: subject=='test-owner',audit_path=tmp_path/'audit.jsonl')
    server=CapabilityMCPServer(control_plane=cp,identity_provider=lambda:'test-owner')
    request={'skill_id':'proof.emergence_verify','arguments':{'spectral_gap':.2,'betti_1':1,'phi_resonance':.7}}
    result=server.execute_tool('capability_invoke',request)
    assert result['ok'] is True, result
    assert result['execution_status']=='completed' and cp.audit.verify()
    denied=CapabilityMCPServer(control_plane=cp,identity_provider=lambda:'other')
    assert denied.execute_tool('capability_invoke',request)['execution_status']=='not_executed'

def test_post_execution_audit_failure_is_not_rollback(server,monkeypatch):
    audit=server.base.control_plane.audit
    original=audit.append
    def append(event):
        if audit.events: raise OSError('test disk failure')
        return original(event)
    monkeypatch.setattr(audit,'append',append)
    result=invoke(server)
    assert server.base.calls==1 and result['execution_status']=='completed'
    assert result['incident_persisted'] is False and result['rollback_performed'] is False

def test_serialization_failure_is_contained(server,monkeypatch):
    monkeypatch.setattr(server,'execute_tool',lambda *args: {'value':object()})
    response=server.handle_request({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'capability_contract','arguments':{'skill_id':'fixture'}}})
    assert response['error']['code']==-32603
    bounded_json(response)

def slow_worker(connection,skill_id,arguments,sandbox):
    import time
    time.sleep(2)

def test_real_sandbox_timeout(monkeypatch):
    from hyba_mcp import control_plane
    monkeypatch.setattr(control_plane,'_sandbox_worker',slow_worker)
    result=control_plane.ControlPlane().execute_skill('proof.emergence_verify',
        {'spectral_gap':.2,'betti_1':1,'phi_resonance':.7},{'timeout_seconds':.01})
    assert result['error']['code']=='timeout'
