import copy, hashlib, json, threading, time
import numpy as np
import pytest
from chronos import OneIGPU,ResidentConfig,ResidentRuntime
from chronos.igpu.intrinsics import execute_intrinsic,verify_intrinsic
from chronos.projection_analysis import projection_contract,preimage_at,preimage_ordinal,project_digest,exhaustive_projection
from chronos.pythi_native import matrix_fold,compute_receipt,verify_receipt
from chronos.lucas_engine import lucas,zeckendorf_encode,fibonacci_pair
from chronos.igpu.virtual_abi import Workload,VirtualRuntime
from chronos.adapters.base import BackendAbsent

def flatten(r):return [x for tile in r['completed_tiles']for x in tile['output']]
def seal(r):
 r.pop('receipt_digest',None);r['receipt_digest']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest();return r

def test_full_exact_fiber_contract():
 c=projection_contract();assert c['preimages_per_rung']==2**248;assert c['domain_size']==c['rung_count']*c['preimages_per_rung'];assert c['header_preimage_bound']is None
@pytest.mark.parametrize('bits',[1,2,3,4,5,6,7,8])
def test_full_constructive_fibers(bits):
 k=2**(256-bits)
 for rung in (1,1<<bits):
  for ordinal in(0,1,2**128,k-1):
   d=preimage_at(rung,ordinal,bits);assert project_digest(d,bits)==rung;assert preimage_ordinal(d,bits)==ordinal
@pytest.mark.parametrize('index',[1,2,31,256])
def test_exhaustive_balanced_reduced_domain(index):
 r=exhaustive_projection(4,3,index);assert r['digests_checked']==256;assert set(r['per_rung_counts'].values())=={32}
def test_projection_not_11d_or_header_bijection():
 with pytest.raises(ValueError):project_digest([0.]*11)
 assert projection_contract()['uniform_headers_proven']is False
 assert projection_contract()['cryptographic_collision_resistance_claimed']is False
def test_collision_does_not_authorize_other_header():
 seen={};pair=None
 for i in range(4096):
  h=f'collision-fixture-{i}'.encode();r=compute_receipt(h)
  if r['rung']in seen:pair=(seen[r['rung']],h,r);break
  seen[r['rung']]=(h,r)
 assert pair is not None
 (old,oldr),new,newr=pair
 assert oldr['rung']==newr['rung'];assert oldr['certificate_id']!=newr['certificate_id']
 with pytest.raises(ValueError):verify_receipt(oldr,new)
@pytest.mark.parametrize('op',['fibonacci','lucas','binet_exact','zeckendorf_encode','pisot_schedule','phi_weight'])
def test_typed_intrinsics(op):
 n={'op':op,'n':31}
 if op=='pisot_schedule':n.update(modulus=257,count=20)
 if op=='phi_weight':n.update(numerator=-3,denominator=7)
 r=execute_intrinsic(n);assert verify_intrinsic(r);assert r['execution_backend']=='cpu_exact'
@pytest.mark.parametrize('value',[0,1,2,2**32,2**64-1])
def test_u64_zeckendorf_roundtrip(value):
 a=execute_intrinsic({'op':'zeckendorf_encode','n':value});b=execute_intrinsic({'op':'zeckendorf_decode','n':a['value']});assert b['value']==value
def test_cassini_supplied_witness_rejection():
 n=31;node={'op':'cassini','n':n,'previous':lucas(n-1),'current':lucas(n),'next':lucas(n+1)}
 assert execute_intrinsic(node)['value']['verified_supplied_witnesses'];node['current']+=1
 with pytest.raises(ValueError):execute_intrinsic(node)
def test_intrinsic_mutation_does_not_mutate_input_receipt():
 n={'op':'lucas','n':31};r=execute_intrinsic(n);n['n']=32;assert r['node']['n']==31;assert verify_intrinsic(r)
def test_intrinsic_unknown_fields_and_bool():
 for n in({'op':'lucas','n':True},{'op':'lucas','n':31,'research':False},{'op':'zeckendorf_decode','n':3}):
  with pytest.raises(ValueError):execute_intrinsic(n)
@pytest.mark.parametrize('units',[80,800,8000])
def test_resident_independence_and_virtual_scale(units):
 with OneIGPU()as g:
  rt=g.resident(ResidentConfig(virtual_units=units));p={'rungs':[10,12,15,18,20,31]*4};r=rt.execute('lucas',p)
  assert flatten(r)==[lucas(n)for n in p['rungs']];assert rt.verify(r,p)
  assert r['manifest']['mode']=='independent';assert r['manifest']['scaling']['virtual_units']==units
  assert r['actual_worker_limit']==2;assert r['peak_inflight']<=4;assert r['manifest']['physical_compute_units']is None
  assert r['hardware_throughput_multiplier']is None
@pytest.mark.parametrize('op',['matmul','add','hadamard','scale'])
def test_resident_tensor_row_execution(op):
 a=np.arange(48,dtype=float).reshape(12,4);b=np.ones((4,5))if op=='matmul'else np.ones_like(a)if op!='scale'else np.asarray(3.)
 p={'operator':op,'left':a.tolist(),'right':b.tolist()}
 with OneIGPU()as g:
  r=g.resident(ResidentConfig(virtual_units=8000)).execute('tensor',p)
  expected=a@b if op=='matmul'else a+b if op=='add'else a*b
  assert np.allclose(flatten(r),expected);assert ResidentRuntime.verify(r,p)
def test_resident_intrinsics_exact_and_verified():
 p={'nodes':[{'op':'lucas','n':i}for i in range(64)]}
 with OneIGPU()as g:r=g.resident(ResidentConfig(virtual_units=8000)).execute('intrinsics',p)
 assert ResidentRuntime.verify(r,p);assert all(verify_intrinsic(n)for n in flatten(r))
def test_resident_cancellation_before_dispatch():
 event=threading.Event();event.set()
 with OneIGPU()as g:r=g.resident().execute('lucas',{'rungs':[10]*100},cancel=event)
 assert r['status']=='cancelled';assert r['completed_items']==0;assert r['peak_inflight']==0
def test_resident_empty_is_complete():
 with OneIGPU()as g:r=g.resident().execute('lucas',{'rungs':[]})
 assert r['status']=='complete';assert r['completed_items']==0
def test_resident_expired_deadline_refused():
 with OneIGPU()as g:
  with pytest.raises(ValueError):g.resident().execute('lucas',{'rungs':[10]},deadline=time.perf_counter()-1)
def test_resident_required_gpu_cannot_use_cpu():
 with OneIGPU()as g:
  with pytest.raises(BackendAbsent):g.resident().execute('lucas',{'rungs':[10]},require_host_gpu=True)
def test_resident_mutated_output_resealed_rejected():
 with OneIGPU()as g:r=g.resident().execute('lucas',{'rungs':[10]})
 r['completed_tiles'][0]['output'][0]+=1;seal(r)
 with pytest.raises(ValueError):ResidentRuntime.verify(r,{'rungs':[10]})
def test_resident_output_quota_and_recovery():
 with OneIGPU()as g:
  rt=g.resident(ResidentConfig(max_bytes=1024))
  with pytest.raises(MemoryError):rt.execute('intrinsics',{'nodes':[{'op':'binet_exact','n':1000}]})
  assert rt.execute('lucas',{'rungs':[10]})['status']=='complete'
def test_resident_lucas_ladder_bound():
 with OneIGPU()as g:
  m=g.resident(ResidentConfig(base_units=80,scale_index=10)).manifest();assert m['scaling']['virtual_units']==80*lucas(10)
  with pytest.raises(ValueError):g.resident(ResidentConfig(scale_index=11))
def test_resident_abi_idempotency_and_quota():
 with OneIGPU()as g:
  p={'kind':'intrinsics','data':{'nodes':[{'op':'lucas','n':31}]},'config':{'virtual_units':8000,'max_items':64}}
  w=Workload('resident','tenant','resident',p,quota=64);r=g.execute_workload(w);assert r==g.execute_workload(w);assert VirtualRuntime.verify_receipt(r,w)
  assert r['output']['completed_items']==1
  with pytest.raises(ValueError):g.execute_workload(Workload('too-small','tenant','resident',p,quota=1))
def test_intrinsic_abi():
 with OneIGPU()as g:r=g.execute_workload(Workload('intrinsic','tenant','intrinsic',{'node':{'op':'binet_exact','n':31}},quota=1))
 assert verify_intrinsic(r['output'])
def test_host_binding_unknown_backend_rejected():
 with OneIGPU()as g:
  with pytest.raises(ValueError):g.bind_host_gpu('fabricated_gpu')
  assert g.compose()['contract_device']['independent_of_physical_gpu']
def test_bind_metal_unavailable_on_linux():
 import platform
 if platform.system()!='Darwin':
  with OneIGPU()as g:
   with pytest.raises(BackendAbsent):g.bind_host_gpu('metal')

def test_host_composed_contract_not_silicon_multiplier():
 class ContractOnlyOverlay:
  last_receipt=None
  def capability(self):return {'backend':'contract_only_test_adapter','device_id':'controlled-fixture','physical':True,'physical_compute_units':80,'operations':['lucas_mod256']}
  def execute_lucas(self,rungs,width):
   self.last_receipt={'test_fixture':True,'physical':False};return tuple(lucas(n)%(1<<width)for n in rungs)
 with OneIGPU(host_adapter=ContractOnlyOverlay())as g:
  r=g.resident(ResidentConfig(virtual_units=8000)).execute('lucas',{'rungs':[10,15]},require_host_gpu=True)
  assert r['manifest']['mode']=='host_gpu_composed';assert r['manifest']['physical_compute_units']==80
  assert r['manifest']['scaling']['virtual_units']==8000;assert r['actual_worker_limit']==1
  assert r['completed_tiles'][0]['backend']=='contract_only_test_adapter'
  with pytest.raises(BackendAbsent):g.resident().execute('intrinsics',{'nodes':[{'op':'lucas','n':10}]},require_host_gpu=True)

def test_failed_executor_releases_resident_admission():
 with OneIGPU()as g:
  rt=g.resident()
  with pytest.raises(ValueError):rt.execute('intrinsics',{'nodes':[{'op':'missing','n':31}]})
  assert rt.execute('lucas',{'rungs':[10]})['status']=='complete'

def test_feedback_audit_retains_all_prior_components():
 from pathlib import Path
 root=Path(__file__).parents[1];audit=json.loads((root/'docs/FEEDBACK_AUDIT-v3.10.json').read_text());contract=json.loads((root/'docs/COMPLETION_CONTRACT.json').read_text())
 assert {r['component']for r in contract['components']}=={r['component']for r in audit['carried_components']}
 assert len(audit['requirements'])==18;assert not audit['fully_production_qualified'];assert not audit['all_feedback_implemented'];assert len(audit['reviewed_sources'])==10

def test_new_source_capture_digests_and_review_complete():
 from pathlib import Path
 root=Path(__file__).parents[1];sources=json.loads((root/'docs/REVIEWED_NOTION-v3.10.json').read_text())
 for source in sources:assert hashlib.sha256((root/source['captured_file']).read_bytes()).hexdigest()==source['sha256']
 text=(root/'docs/source_notes/resident-projection-user-review.txt').read_text();assert 'Priority 5' in text;assert 'Apple M5' in text

def test_resident_native_policy_no_host_probe():
 with OneIGPU()as g:
  g.bind_host_gpu=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('probe forbidden'))
  r=g.resident(ResidentConfig(host_binding='native')).manifest();assert r['mode']=='independent'

def test_resident_explicit_binding_fails_not_fallback():
 with OneIGPU()as g:
  g.bind_host_gpu=lambda *args,**kwargs:(_ for _ in ()).throw(BackendAbsent('controlled missing device'))
  with pytest.raises(BackendAbsent):g.resident(ResidentConfig(host_binding='opencl'))
  assert g.fabric.overlay is None

def test_resident_auto_missing_device_reason():
 with OneIGPU()as g:
  g.bind_host_gpu=lambda *args,**kwargs:(_ for _ in ()).throw(BackendAbsent('controlled missing device'))
  rt=g.resident();assert rt.manifest()['overlay_unavailable_reason']=='controlled missing device'
  assert rt.execute('lucas',{'rungs':[10]})['status']=='complete'
