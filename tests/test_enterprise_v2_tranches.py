import tempfile,unittest
from pathlib import Path
from hyba_contracts import *
from hyba_services.core import *
from hyba_services.platform import *
from al_haras.extraction import route_path,STAGES
from al_haras.environment_boundary import *
from al_haras.core_api import import_audit,PrivateImport
from al_haras.delivery_plan import SPRINTS,RELEASE_TRAINS,run_sprint,SprintGateFailed
from al_haras.gate_runner import run_gates
class Math:
 def fib_pair(self,n):
  a,b=0,1
  for _ in range(n):a,b=b,a+b
  return a,b
 def lucas(self,n):return 2*self.fib_pair(n)[1]-self.fib_pair(n)[0]
 def zeckendorf(self,n):return n
 def nth_prime(self,n):return n+1
 def route(self,n):return n%32
 def binet(self,n):return (n,"exact")
 def transform(self,n):return (1,n)
 def cassini(self,n):return -1 if n%2 else 1
def fold(x):return x,None
def unfold(x,r):return x
FOLD=FoldContract("fibonacci","pair","lossless",fold,unfold,("add",),("cassini",),"zero","sha256-json",("exact",),1)
BACKEND=BackendCertificate("python",BackendClass.CLASSICAL_EXACT,"cpu",("exact",),"fail_closed",("add",),"attested","hash")
class Tests(unittest.TestCase):
 def test_prime_object_policy_and_lineage(self):
  with tempfile.NamedTemporaryFile() as f:
   lineage=LineageStore(f.name,b"l"*32);service=ObjectService(Math(),{"fibonacci":FOLD},lineage.head);obj=service.create({"x":1},"fibonacci",8,"t","i");obj.validate();self.assertTrue(obj.object_id)
   ctx=EnterprisePolicyContext("actor","t","i","train","local","7y",True,True,True,True,False,False,"uk","restricted")
   self.assertTrue(PolicyService().evaluate("read",ctx,obj).allowed);first=lineage.append("t","i",{"object":obj.object_id});self.assertEqual(first["prev_hash"],"GENESIS");lineage.close()
 def test_proof_and_backend_contract(self):
  obj=ObjectService(Math(),{"fibonacci":FOLD},lambda *_:"GENESIS").create(1,"fibonacci",5,"t","i")
  proof=ProofService(b"p"*32).certify("add",obj,obj,{"same":lambda a,b:a.object_id==b.object_id},BACKEND);self.assertTrue(proof.signature)
  with self.assertRaises(ValueError):BackendCertificate("x",BackendClass.CLASSICAL_APPROX,"d",(),"wrap",(),"a","h").validate()
 def test_registry_approval_requires_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   reg=ModelRegistry(d);sha=reg.register(b"m",{}, {},"t")
   with self.assertRaises(PromotionBlocked):reg.promote("t",sha,"APPROVED",())
 def test_extraction_environment_and_api_audit(self):
  self.assertEqual(route_path("mla1517_platform_v3.4/python/mla1517/core.py"),"CORE");self.assertEqual(len(STAGES),4)
  self.assertEqual(classify_failure("x",ModuleNotFoundError("fastapi"),"linux"),FailureClass.ENV_MISSING_DECLARED_DEP)
  with tempfile.TemporaryDirectory() as d:
   good=Path(d)/"good.py";good.write_text("from mla1517_core.core import fib\n");import_audit([good])
   good.write_text("from mla1517_core.core import secret\n")
   with self.assertRaises(PrivateImport):import_audit([good])
 def test_sprints_and_signed_gate_report(self):
  self.assertEqual(len(SPRINTS),13);self.assertEqual(RELEASE_TRAINS["R4"],(11,12))
  s=SPRINTS[0];actions={s.deliverables[0]:lambda:"done",s.gates[0]:lambda:True};self.assertEqual(run_sprint(s,actions,lambda n,o:"sig")["sprint"],0)
  report=run_gates("repo","sha",{"ok":lambda:True,"skip":lambda:(_ for _ in ()).throw(NotImplementedError("hardware"))},b"g"*32);self.assertTrue(report.passed);self.assertTrue(report.signature)
if __name__=="__main__":unittest.main()
