import unittest
import numpy as np
from chronos import OneIGPU
from chronos.golden_quantum import MathematicalQuantumState,NonceLease
from chronos.igpu.structured_solver import StructuredHamiltonian
from chronos.igpu import Workload,VirtualRuntime
class StructuredTests(unittest.TestCase):
 def state(self,n,case):
  rng=np.random.default_rng(100+n+case)
  if case==0:a=np.ones(n)
  elif case==1:a=rng.normal(size=n)+1j*rng.normal(size=n)
  else:
   with OneIGPU()as g:a=g.golden.transform.forward(np.ones(n))
  return MathematicalQuantumState(a).amplitudes
 def test_matrix_free_matches_dense_real_and_complex(self):
  for n in(1,2,7,32,64,128):
   for k in range(3):
    a=self.state(n,k);o=StructuredHamiltonian(a,1.618033988749895);v=self.state(n,1)
    np.testing.assert_allclose(o.matvec(v),o.dense()@v,atol=5e-15,rtol=5e-15);self.assertEqual(o.storage_bytes,n*24)
 def test_native_ground_against_dense(self):
  for n in(1,2,7,32,64,128):
   for k in range(3):
    o=StructuredHamiltonian(self.state(n,k),1.618033988749895);r=o.ground('native');d=o.ground('dense');self.assertFalse(r.evidence['matrix_materialized']);self.assertLess(r.evidence['residual'],1e-10);self.assertAlmostEqual(r.evidence['eigenvalue'],d.evidence['eigenvalue'],places=10);self.assertGreater(abs(np.vdot(r.vector,d.vector)),1-1e-10)
 def test_python_native_equivalence(self):
  for n in(1,7,32):
   o=StructuredHamiltonian(self.state(n,1),1.618);a=o.ground('python');b=o.ground('native');np.testing.assert_allclose(a.vector,b.vector,atol=1e-10,rtol=1e-10)
 def test_large_linear_storage(self):
  o=StructuredHamiltonian(self.state(1024,1),1.618);r=o.ground('native');self.assertLess(r.evidence['working_bytes'],1024*64);self.assertLess(r.evidence['residual'],1e-10)
  with self.assertRaises(ValueError):o.dense()
 def test_original_engine_unchanged_order(self):
  with OneIGPU()as g:
   for n in(32,64,128):
    lease=NonceLease(0,n,'same',1);g.configure_solver('dense',False);a=g.golden.plan(lease);g.configure_solver('structured',False);b=g.golden.plan(lease);self.assertEqual(a['order'],b['order']);self.assertIsNone(b['reason'])
 def test_auto_native_path_really_executed(self):
  with OneIGPU()as g:
   g.golden.plan(NonceLease(0,64));self.assertEqual(g.golden.events[-1]['details']['solver']['backend'],'native_structured_cpu')
 def test_mutation_rejected(self):
  o=StructuredHamiltonian(self.state(7,0),1.618)
  with self.assertRaises(ValueError):o.real[0]=1
 def test_zero_invalid_quota(self):
  for a in([0],[float('nan')],np.ones(8193)):
   with self.assertRaises(ValueError):StructuredHamiltonian(a,1.618)
 def test_raw_native_rejects_bad_values(self):
  from chronos.igpu import _structured_native as n
  for a,b,p in((b'',b'',1.618),(b'123',b'123',1.618),(np.array([np.nan]).tobytes(),np.zeros(1).tobytes(),1.618),(np.ones(1).tobytes(),np.zeros(1).tobytes(),0)):
   with self.assertRaises(ValueError):n.ground(a,b,p)
 def test_unknown_mode(self):
  with OneIGPU()as g:
   with self.assertRaises(ValueError):g.configure_solver('madeup')
 def test_numerical_ambiguity_dense_fallback(self):
  with OneIGPU()as g:
   # Dimension 128 often contains positional near-ties; whichever path is used,
   # the exact caller permutation and dense reference remain identical.
   g.configure_solver('structured',False);a=g.golden.plan(NonceLease(0,128));e=g.golden.events[-1]['details']['solver'];g.configure_solver('dense',False);b=g.golden.plan(NonceLease(0,128));self.assertEqual(a['order'],b['order']);self.assertIn('dense_fallback_reason',e)
 def test_service_abi_structured(self):
  with OneIGPU()as g:
   w=Workload('structured','local','structured_ground',{'real':[.5]*4},quota=4);r=g.execute_workload(w);self.assertTrue(VirtualRuntime.verify_receipt(r,w));self.assertFalse(r['output']['evidence']['matrix_materialized'])

class ScaledWiringTests(unittest.TestCase):
 def test_rung31_metadata_and_actual_budget(self):
  with OneIGPU()as g:
   g.configure_asic_like(require_native=True);r=g.scaled_mine(bytes(76),0,1,31,max_evaluations=71);self.assertEqual(r['result']['sha256d_evaluations'],71);self.assertGreater(r['plan']['effective_items'],71);self.assertEqual(g.golden.events[-1]['lucas_rung'],31);self.assertEqual(g.golden.events[-2]['lucas_rung'],31)
 def test_undeclared_rung_rejected(self):
  with OneIGPU()as g:
   with self.assertRaises(ValueError):g.mine(bytes(76),0,NonceLease(0,1),scale_index=99)

class StructuredOverlayTests(unittest.TestCase):
 def test_cpu_matvec_owner(self):
  with OneIGPU()as g:
   result=g.structured_matvec([.5]*4,[1,2,3,4]);reference=StructuredHamiltonian([.5]*4,g.golden.constants.phi).matvec([1,2,3,4]);np.testing.assert_array_equal(result,reference)
 def test_absent_gpu_fail_closed(self):
  from chronos.adapters.base import BackendAbsent
  with OneIGPU()as g:
   with self.assertRaises(BackendAbsent):g.structured_matvec([.5]*4,[1,2,3,4],backend='host_gpu')
 def test_packaged_kernel_contract(self):
  from importlib.resources import files
  text=files('chronos').joinpath('igpu/kernels/structured_matvec.cl').read_text();self.assertIn('chronos_rank2_partials',text);self.assertIn('chronos_structured_apply',text)
