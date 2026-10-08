import unittest,threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from chronos import OneIGPU
from chronos.igpu.solver_cache import DeterministicSolverCache
from chronos.golden_quantum import MathematicalQuantumState,GoldenConstants,NonceLease
class SolverCacheTests(unittest.TestCase):
 def test_exact_dense_reuse(self):
  from chronos.engine import ChronosEngine
  c=DeterministicSolverCache();phi=GoldenConstants().phi
  for n in (1,2,7,32,64,128):
   a=MathematicalQuantumState(np.arange(1,n+1)+1j*np.arange(n)).amplitudes
   order,e=c.rank(a,phi);h=np.diag(np.linspace(0,1,n))-np.real(np.outer(a,a.conj()))
   if n>1:h+=np.diag(np.full(n-1,-1/phi),1)+np.diag(np.full(n-1,-1/phi),-1)
   v=ChronosEngine().evolve(h);self.assertEqual(order,tuple(int(i)for i in np.argsort(-np.abs(v)**2,kind='stable')));self.assertLess(e['residual'],1e-10)
   repeat,receipt=c.rank(a,phi);self.assertEqual(order,repeat);self.assertTrue(receipt['cache_hit'])
 def test_input_changes_invalidate(self):
  c=DeterministicSolverCache();a=MathematicalQuantumState(np.ones(4)).amplitudes
  c.rank(a,1.618);c.rank(a*1j,1.618);c.rank(a,1.619);self.assertEqual(c.stats()['solves'],3)
 def test_eviction(self):
  c=DeterministicSolverCache(entries=2)
  for n in (2,3,4):c.rank(MathematicalQuantumState(np.ones(n)).amplitudes,1.618)
  self.assertEqual(c.stats()['entries'],2);c.rank(MathematicalQuantumState(np.ones(2)).amplitudes,1.618);self.assertEqual(c.stats()['solves'],4)
 def test_no_cache_control(self):
  c=DeterministicSolverCache(enabled=False);a=MathematicalQuantumState(np.ones(4)).amplitudes
  c.rank(a,1.618);c.rank(a,1.618);self.assertEqual(c.stats()['solves'],2);self.assertEqual(c.stats()['entries'],0)
 def test_concurrent_single_solve(self):
  c=DeterministicSolverCache();a=MathematicalQuantumState(np.ones(64)).amplitudes
  with ThreadPoolExecutor(max_workers=8)as pool:r=list(pool.map(lambda _:c.rank(a,1.618),range(16)))
  self.assertEqual(c.stats()['solves'],1);self.assertEqual(c.stats()['hits'],15);self.assertTrue(all(x[0]==r[0][0]for x in r))
 def test_job_nonce_identity_not_cached(self):
  with OneIGPU()as g:
   a=g.golden.plan(NonceLease(0,64,'a',1));b=g.golden.plan(NonceLease(1000,1064,'b',2))
   self.assertEqual(tuple(n+1000 for n in a['order']),b['order']);self.assertEqual(g.golden.solver_cache.stats()['hits'],1);self.assertEqual(g.golden.solver_cache.stats()['cached_nonce_count'],0)
 def test_cache_and_reference_full_pipeline_identical(self):
  with OneIGPU()as g:
   g.configure_asic_like(require_native=True)
   for start in (0,123,2**32-128):
    lease=NonceLease(start,start+128,'equal',1);g.golden.solver_cache.enabled=False;a=g.golden.plan(lease);g.golden.solver_cache.enabled=True;b=g.golden.plan(lease);d=g.golden.plan(lease);self.assertEqual(a['order'],b['order']);self.assertEqual(b['order'],d['order'])
    r=g.mine(bytes(76),0,lease,max_evaluations=128);self.assertEqual(r.sha256d_evaluations,128);self.assertFalse(r.verified);self.assertIn('S6_chronos_solver',r.path)
 def test_invalid_inputs(self):
  c=DeterministicSolverCache()
  for a,p in (([],1.6),([float('nan')],1.6),([1],0),(np.ones(129),1.6)):
   with self.assertRaises(ValueError):c.rank(a,p)
 def test_returned_evidence_cannot_mutate_cache(self):
  c=DeterministicSolverCache();a=MathematicalQuantumState(np.ones(4)).amplitudes;_,e=c.rank(a,1.6);e['input_digest']='bad';_,again=c.rank(a,1.6);self.assertNotEqual(again['input_digest'],'bad')
