import tempfile,unittest
from dataclasses import dataclass
from al_haras.promotion_gates import PromotionState
from al_haras.promotion_pipeline import *
from al_haras.release_engineering import *
from hyba_services import *
class Tests(unittest.TestCase):
 def test_sod_rejects_author_and_accepts_distinct_roles(self):
  base=dict(subsystem='guardian',from_state=PromotionState.CONTRACTED,to_state=PromotionState.VERIFIED,approved_at=1,evidence_commit='sha',reason='ok',source_url='u')
  approvals=(Approval(approver_role='ARCH_OWNER',approver_identity='arch',**base),Approval(approver_role='EVIDENCE_OWNER',approver_identity='evidence',**base));members={'ARCH_OWNER':{'arch'},'EVIDENCE_OWNER':{'evidence'}}
  self.assertEqual(len(enforce_sod('guardian',PromotionState.CONTRACTED,PromotionState.VERIFIED,'sha',{'author'},approvals,members)),2)
  with self.assertRaises(PromotionRejected):enforce_sod('guardian',PromotionState.CONTRACTED,PromotionState.VERIFIED,'sha',{'arch'},approvals,members)
 def test_receipt_requires_all_pass(self):
  a=Approval('guardian',PromotionState.CONTRACTED,PromotionState.VERIFIED,'ARCH_OWNER','arch',1,'sha','ok','u');r=build_receipt('guardian',PromotionState.CONTRACTED,PromotionState.VERIFIED,'sha',({'status':'PASS','gate':'g'},),(a,),b'k'*32);self.assertTrue(r.signature)
  with self.assertRaises(PromotionRejected):build_receipt('guardian',PromotionState.CONTRACTED,PromotionState.VERIFIED,'sha',({'status':'SKIP'},),(a,),b'k'*32)
 def test_release_tags_pins_and_major_approval(self):
  self.assertTrue(is_release_tag('v1.2.3'));self.assertTrue(is_prerelease('v1.2.3-rc1'));self.assertEqual(pin('PYTHIA','1.2.3'),'mla1517-core==1.2.3')
  with self.assertRaises(PromotionRejected):authorize_upgrade('ENTERPRISE','1.2.3','2.0.0')
  self.assertEqual(authorize_upgrade('ENTERPRISE','1.2.3','2.0.0',True),'mla1517-core==2.0.0')
 def test_flow_ontology_and_agent_metrics(self):
  transport=InMemoryTransport();obs=Observability(transport)
  class Objects:
   def create(self,event,family,scale,tenant,instance):return type('O',(),{'payload_type':family})()
  class Sink:
   def put(self,obj):pass
  ctx=ServiceContext('t','i','enterprise');self.assertEqual(FlowService(Objects(),Sink(),obs).start([1,2],ctx,lambda e:'f',lambda e:1),2)
  with tempfile.NamedTemporaryFile() as f:
   onto=OntologyService(f.name,{'read'},{'READ'},{'Case'},obs);onto.publish('t','i','enterprise',{'name':'case','obj_class':'Case','verbs':['read'],'permissions':['READ']});self.assertEqual(onto.resolve('t','case')['obj_class'],'Case');onto.close()
  self.assertEqual(agent_tick('act','r',ctx,obs,lambda a,r:True,lambda a:False),'act')
 def test_research_gates_and_acknowledgement(self):
  with self.assertRaises(FeatureDisabled):quantum_submit({},lambda x:x,lambda x:True)
  with self.assertRaises(ServicePolicyError):privacy_run({'kind':'MPC'},1,2,{})
  with self.assertRaises(AckRequired):autonomous_apply({'acknowledged':False},lambda p:True)
  self.assertEqual(energy_report('t',(1,2),lambda *_:10,lambda *_:3)['claim'],'measured_only')
 def test_function_registry_requires_external_sandbox(self):
  reg=FunctionRegistry();reg.register({'id':'f','language':'WASM','determinism':'exact','resource_budget':{},'network_policy':'deny'})
  self.assertEqual(reg.invoke('f',[1],{},lambda *x:True,lambda fn,args:args[0]+1),2)
if __name__=='__main__':unittest.main()
