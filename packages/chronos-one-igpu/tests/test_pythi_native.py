import unittest,copy,hashlib
from chronos import OneIGPU
from chronos.pythi_native import NativePolicy,matrix_fold,matrix_unfold,compute_receipt,verify_receipt,bounded_pisot_adjustment,security_gate
from chronos.lucas_engine import lucas,fibonacci_pair,nth_prime
from chronos.igpu import Workload,VirtualRuntime
class NativeTests(unittest.TestCase):
 def test_toy_fold_bijection_exhaustive(self):
  for index in (1,2,3,31):
   seen=set()
   for x in range(256):
    p=matrix_fold(x,index,4);self.assertEqual(matrix_unfold(p,index,4),x);seen.add(p)
   self.assertEqual(len(seen),256)
 def test_full_digest_boundary_roundtrip(self):
  for i in(1,2,31,128,256):
   for x in(0,1,2**128-1,2**128,2**256-1,int.from_bytes(hashlib.sha256(b'genesis').digest(),'big')):self.assertEqual(matrix_unfold(matrix_fold(x,i),i),x)
 def test_rung_projection_not_bijective(self):
  # Same low-bit rung, different full folded coordinates; inverse needs both.
  self.assertEqual(0&255,256&255);self.assertNotEqual(matrix_unfold((0,0)),matrix_unfold((256,0)))
 def test_exact_cassini_sign(self):
  for n in range(1,513):self.assertEqual(lucas(n-1)*lucas(n+1)-lucas(n)**2,5*(-1)**(n+1))
 def test_reference_compute_verify(self):
  r=compute_receipt(b'header');self.assertTrue(verify_receipt(r,b'header'));self.assertEqual(r['nonce_enumeration_evaluations'],0);self.assertFalse(r['bitcoin_compatible']);self.assertFalse(r['consensus_security_proven']);self.assertEqual(r,compute_receipt(b'header'))
 def test_domain_separation(self):
  a=compute_receipt(b'header');b=compute_receipt(b'header',NativePolicy(chain_id='other'));self.assertNotEqual(a['header_digest'],b['header_digest'])
 def test_epoch_bound(self):
  r=compute_receipt(b'header',NativePolicy(epoch=2))
  with self.assertRaises(ValueError):verify_receipt(r,b'header',NativePolicy(epoch=1))
 def test_header_bound(self):
  r=compute_receipt(b'header')
  with self.assertRaises(ValueError):verify_receipt(r,b'other')
 def test_threshold_refusal(self):
  p=NativePolicy(maximum_lucas=0);r=compute_receipt(b'header',p);self.assertFalse(r['admissible']);self.assertTrue(verify_receipt(r,b'header',p))
 def test_tamper_all_certificate_fields(self):
  r=compute_receipt(b'header')
  for k,v in r.items():
   s=copy.deepcopy(r);s[k]=None if v is not None else'bad'
   with self.assertRaises(ValueError):verify_receipt(s,b'header')
 def test_forged_seal_does_not_replace_authority(self):
  import json
  r=compute_receipt(b'header');r['lucas_value']+=1;r.pop('certificate_id');r['certificate_id']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  with self.assertRaises(ValueError):verify_receipt(r,b'header')
 def test_prime_and_family_authority(self):
  r=compute_receipt(b'header');self.assertEqual(r['prime_address'],nth_prime(r['rung']+1));self.assertEqual(tuple(r['fibonacci_pair']),fibonacci_pair(r['rung']))
 def test_bounded_adjustment_extremes(self):
  for current in(1,4,8):
   for a,b in((1e-300,1e300),(1e300,1e-300),(1,1)):
    r=bounded_pisot_adjustment(current,a,b,1);self.assertLessEqual(abs(r['delta']),1);self.assertTrue(1<=r['updated']<=8)
 def test_invalid_policy(self):
  for p in(NativePolicy(rung_bits=9),NativePolicy(epoch=-1),NativePolicy(fold_index=0),NativePolicy(maximum_lucas=-1),NativePolicy(chain_id='bad path')):
   with self.assertRaises(ValueError):compute_receipt(b'header',p)
 def test_header_quota(self):
  for h in(b'',b'a'*65537,'notbytes'):
   with self.assertRaises(ValueError):compute_receipt(h)
 def test_native_through_owner(self):
  with OneIGPU()as g:r=g.compute_pythi(b'header');self.assertTrue(verify_receipt(r,b'header'));self.assertEqual(g.golden.events[-1]['operation'],'pythi_native_compute')
 def test_abi_idempotent(self):
  with OneIGPU()as g:
   w=Workload('native','local','pythi_native',{'header_hex':b'header'.hex()},quota=1);r=g.execute_workload(w);self.assertEqual(r,g.execute_workload(w));self.assertTrue(VirtualRuntime.verify_receipt(r,w));self.assertFalse(r['output']['bitcoin_compatible'])
 def test_security_gate_blocked(self):self.assertFalse(security_gate()['deployable']);self.assertFalse(security_gate()['mainnet_deployed'])
 def test_bounded_native_fold_inputs(self):
  for x in(-1,2**256,True):
   with self.assertRaises(ValueError):matrix_fold(x)
 def test_unknown_policy_fields(self):
  with self.assertRaises(ValueError):NativePolicy.from_dict({'pretend_secure':True})

class ModelsTests(unittest.TestCase):
 def test_pipeline_depth_not_initiation_interval(self):
  from chronos.pythi_native import capacity_model
  a=capacity_model(24,1e9,6);b=capacity_model(24,1e9,1);self.assertEqual(a['modeled_receipts_per_second'],4e9);self.assertEqual(b['modeled_receipts_per_second'],24e9);self.assertFalse(a['hardware_measured'])
 def test_energy_assumptions_explicit(self):
  from chronos.pythi_native import landauer_model
  r=landauer_model(300,256);self.assertFalse(r['erasure_count_derived_from_algorithm']);self.assertGreater(r['joules_lower_bound'],0)

class CanonicalTypeTests(unittest.TestCase):
 def test_numeric_type_substitution_rejected(self):
  import json
  r=compute_receipt(b'header');r['rung']=float(r['rung']);r.pop('certificate_id');r['certificate_id']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  with self.assertRaises(ValueError):verify_receipt(r,b'header')
