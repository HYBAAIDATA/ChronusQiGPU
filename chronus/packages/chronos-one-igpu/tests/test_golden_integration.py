"""Reference vectors and adversarial tests for actual facade wiring."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'src'))
import hashlib
import math
import tempfile
import time
import unittest
from dataclasses import replace
import numpy as np
from chronos import OneIGPU
from chronos.golden_quantum import *
from chronos.igpu.golden_runtime import verify_evidence
from chronos.adapters.base import BackendAbsent

GENESIS_HEADER = bytes.fromhex(
    '01000000' + '00'*32 +
    '3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a' +
    '29ab5f49' + 'ffff001d' + '1dac2b7c')
GENESIS_HASH = '000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f'
GENESIS_NONCE = 2083236893
GENESIS_TARGET = 0xffff * 2**(8*(0x1d-3))

class ConstantsTests(unittest.TestCase):
    def test_phi_identity(self): self.assertAlmostEqual(GoldenConstants().phi**2, GoldenConstants().phi+1)
    def test_golden_angle(self): self.assertAlmostEqual(math.degrees(GoldenConstants().golden_angle),137.50776405003785)
    def test_lucas_15(self): self.assertEqual(GoldenConstants.lucas(15),1364)
    def test_fibonacci(self): self.assertEqual([GoldenConstants.fibonacci(i) for i in range(10)],[0,1,1,2,3,5,8,13,21,34])
    def test_primes(self): self.assertEqual([GoldenConstants.prime(i) for i in range(1,6)],[2,3,5,7,11])

class StateTests(unittest.TestCase):
    def test_normalization(self): self.assertAlmostEqual(MathematicalQuantumState([3,4]).probabilities.sum(),1)
    def test_large_normalization(self): self.assertTrue(np.isfinite(MathematicalQuantumState([1e300,1e300]).amplitudes).all())
    def test_tiny_normalization(self): self.assertAlmostEqual(MathematicalQuantumState([1e-300,1e-300]).probabilities.sum(),1)
    def test_zero_rejected(self):
        with self.assertRaises(ValueError): MathematicalQuantumState([0,0])
    def test_nan_rejected(self):
        with self.assertRaises(ValueError): MathematicalQuantumState([float('nan')])
    def test_shape_rejected(self):
        with self.assertRaises(ValueError): MathematicalQuantumState([[1,2]])
    def test_quota(self):
        with self.assertRaises(ValueError): MathematicalQuantumState(np.ones(4097))
    def test_hamiltonian_phase(self):
        result=HamiltonianEngine().evolve(MathematicalQuantumState([1,1]),np.diag([0,1]),math.pi)
        np.testing.assert_allclose(result.amplitudes,np.array([1,-1])/math.sqrt(2),atol=1e-12)
    def test_complex_hermitian(self):
        state=MathematicalQuantumState([1,0]); h=np.array([[0,1j],[-1j,0]])
        result=HamiltonianEngine().evolve(state,h,0.5)
        self.assertAlmostEqual(result.probabilities.sum(),1)
    def test_nonhermitian(self):
        with self.assertRaises(ValueError): HamiltonianEngine().evolve(MathematicalQuantumState([1,0]),[[0,1],[0,0]])
    def test_operator_mismatch(self):
        with self.assertRaises(ValueError): Operator(np.eye(2)).apply(MathematicalQuantumState([1]))
    def test_non_square(self):
        with self.assertRaises(ValueError): Operator(np.ones((2,3)))

class TransformTests(unittest.TestCase):
    def test_1d(self):
        a=np.arange(12); np.testing.assert_allclose(GoldenTransform().inverse(GoldenTransform().forward(a)),a,atol=1e-12)
    def test_2d(self):
        a=np.arange(12).reshape(3,4); np.testing.assert_allclose(GoldenTransform().inverse(GoldenTransform().forward(a)),a,atol=1e-12)
    def test_3d(self):
        a=np.arange(24).reshape(2,3,4); np.testing.assert_allclose(GoldenTransform().inverse(GoldenTransform().forward(a)),a,atol=1e-12)
    def test_lossless_bytes(self):
        data=GENESIS_HEADER*20; self.assertEqual(DataFoldingEngine().unfold(DataFoldingEngine().fold(data)),data)
    def test_corrupt_fold(self):
        with self.assertRaises(Exception): DataFoldingEngine().unfold(b'bad')
    def test_fold_bomb(self):
        f=DataFoldingEngine(); f.MAX_BYTES=16
        import zlib
        with self.assertRaises(ValueError): f.unfold(zlib.compress(b'a'*100))
    def test_empty_fold(self): self.assertEqual(DataFoldingEngine().unfold(DataFoldingEngine().fold(b'')),b'')
    def test_shape_rejected(self):
        with self.assertRaises(ValueError): GoldenTransform().forward(np.ones((1,1,1,1)))

class ComponentTests(unittest.TestCase):
    def test_mandelbrot_interior(self): self.assertEqual(MandelbrotResonanceEngine().escape_iterations(0j),32)
    def test_mandelbrot_escape(self): self.assertEqual(MandelbrotResonanceEngine().escape_iterations(3+0j),1)
    def test_mandelbrot_nonfinite(self):
        with self.assertRaises(ValueError): MandelbrotResonanceEngine().escape_iterations(complex(float('inf'),0))
    def test_fold_permutation(self): self.assertEqual(sorted(GoldenQuantumInfinityFold().rank(range(67))),list(range(67)))
    def test_coherence_normalized(self): self.assertTrue(QuantumCoherenceAnalyzer().analyze([1,0])['high_quality'])
    def test_coherence_bad(self): self.assertFalse(QuantumCoherenceAnalyzer().analyze([float('nan')])['high_quality'])
    def test_uci_immutable_registry(self):
        k=OmniscienceKernel(); result=k.parameterize(c=1)
        self.assertEqual(result['parameters']['c'],1); self.assertEqual(k.registry.snapshot()['c'],299792458)
        self.assertFalse(result['physical_constants_mutated'])
    def test_uci_invalid(self):
        with self.assertRaises(ValueError): OmniscienceKernel().parameterize(c=-1)
    def test_registry_cpu(self): self.assertEqual(SuperGPU().select('search')['backend'],'cpu_reference')
    def test_registry_hardware_closed(self):
        with self.assertRaises(RuntimeError): SuperGPU().select('search',True)
    def test_prime_gap(self): self.assertEqual(TransfiniteMemoryMapper().address(0)['gap'],1)
    def test_prime_gap_quota(self):
        with self.assertRaises(ValueError): TransfiniteMemoryMapper().address(10000)

class SearchTests(unittest.TestCase):
    def test_search_success_count(self):
        r=GoldenQuantumComputer().search(range(10),lambda x:x==3); self.assertTrue(r.success); self.assertEqual(r.evaluations,4)
    def test_no_fabricated_result(self):
        r=GoldenQuantumComputer().search(range(10),lambda x:False,3); self.assertFalse(r.success); self.assertIsNone(r.candidate); self.assertEqual(r.evaluations,3)
    def test_zero_budget(self): self.assertEqual(GoldenQuantumComputer().search(range(3),lambda x:True,0).evaluations,0)
    def test_budget_no_overconsume(self):
        consumed=[]
        def source():
            for x in range(10): consumed.append(x); yield x
        GoldenQuantumComputer().search(source(),lambda x:False,2); self.assertEqual(consumed,[0,1])
    def test_grover_four(self):
        r=GoldenQuantumComputer().simulate_grover(4,lambda n:n==2)
        self.assertTrue(r.success); self.assertEqual(r.candidate,2); self.assertEqual(r.oracle_calls,4)
        self.assertAlmostEqual(abs(r.amplitudes[2])**2,1)
    def test_grover_no_mark(self): self.assertFalse(GoldenQuantumComputer().simulate_grover(4,lambda n:False).success)
    def test_grover_quota(self):
        with self.assertRaises(ValueError): GoldenQuantumComputer().simulate_grover(4097,lambda n:True)

class MiningTests(unittest.TestCase):
    def test_nist_abc(self): self.assertEqual(AdvancedMathematicalOracles.sha256(b'abc').hex(),'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    def test_nist_empty(self): self.assertEqual(AdvancedMathematicalOracles.sha256(b'').hex(),'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
    def test_genesis(self): self.assertEqual(AdvancedMathematicalOracles.sha256d(GENESIS_HEADER)[::-1].hex(),GENESIS_HASH)
    def test_exact_target(self):
        digest=AdvancedMathematicalOracles.sha256d(GENESIS_HEADER); value=int.from_bytes(digest,'little')
        self.assertTrue(AdvancedMathematicalOracles.accepts(digest,value)); self.assertFalse(AdvancedMathematicalOracles.accepts(digest,value-1))
    def test_genesis_facade(self):
        with OneIGPU(golden_quantum_enabled=True) as gpu:
            r=gpu.mine(GENESIS_HEADER[:76],GENESIS_TARGET,NonceLease(GENESIS_NONCE,GENESIS_NONCE+1))
            self.assertTrue(r.verified); self.assertEqual(r.nonce,GENESIS_NONCE); self.assertEqual(r.sha256d_evaluations,1)
            self.assertEqual(r.verification_sha256d_evaluations,1); self.assertEqual(r.total_sha256d_evaluations,2)
            self.assertIsNone(r.pool_accepted); self.assertFalse(r.network_submitted)
    def test_no_success(self):
        r=OneIGPU().mine(GENESIS_HEADER[:76],0,NonceLease(0,10),max_evaluations=3)
        self.assertFalse(r.verified); self.assertIsNone(r.nonce); self.assertEqual(r.sha256d_evaluations,3)
    def test_partition_exact(self):
        parts=NonceLease(2,103).partition([1,3,2]); self.assertEqual([n for p in parts for n in range(p.start,p.stop)],list(range(2,103)))
    def test_partition_tiny(self): self.assertEqual(sum(p.stop-p.start for p in NonceLease(0,2).partition([1]*5)),2)
    def test_partition_bad_weight(self):
        with self.assertRaises(ValueError): NonceLease(0,2).partition([0])
    def test_duplicate_advice_rejected(self):
        with self.assertRaises(ValueError): GoldenRatioMining().scan(GENESIS_HEADER[:76],0,NonceLease(0,5),[1,1])
    def test_outside_advice_rejected(self):
        with self.assertRaises(ValueError): GoldenRatioMining().scan(GENESIS_HEADER[:76],0,NonceLease(0,5),[9])
    def test_stale_rejected(self):
        with self.assertRaises(ValueError): OneIGPU().mine(GENESIS_HEADER[:76],0,NonceLease(0,5,epoch=1),current_epoch=2)
    def test_deadline_rejected(self):
        with self.assertRaises(ValueError): OneIGPU().mine(GENESIS_HEADER[:76],0,NonceLease(0,5),deadline=time.perf_counter()-1)
    def test_zero_budget(self): self.assertEqual(OneIGPU().mine(GENESIS_HEADER[:76],0,NonceLease(0,5),max_evaluations=0).sha256d_evaluations,0)
    def test_classical_coverage_after_advice(self):
        from unittest.mock import patch
        seen=[]; original=AdvancedMathematicalOracles.nonce_digest
        def digest(prefix,nonce): seen.append(nonce); return original(prefix,nonce)
        with patch.object(AdvancedMathematicalOracles,'nonce_digest',side_effect=digest):
            r=GoldenRatioMining().scan(GENESIS_HEADER[:76],0,NonceLease(0,10),[4,3],10)
        self.assertEqual(len(seen),10); self.assertEqual(sorted(seen),list(range(10)))
    def test_bad_header(self):
        with self.assertRaises(ValueError): OneIGPU().mine(b'bad',0,NonceLease(0,5))
    def test_negative_target(self):
        with self.assertRaises(ValueError): OneIGPU().mine(GENESIS_HEADER[:76],-1,NonceLease(0,5))

class FacadeTests(unittest.TestCase):
    def test_modes_truthful(self):
        for mode in ['cpu_reference','integrated_iGPU','host_gpu_overlay']:
            gpu=OneIGPU(mode,working_width=32,prime_rom_limit=1000)
            r=gpu.dispatch([1,2,15]); self.assertEqual(r.backend,'cpu_reference'); self.assertTrue(r.verify())
            self.assertFalse(r.evidence['details']['hardware_accelerated'])
    def test_accelerator_fail_closed(self):
        with self.assertRaises(BackendAbsent): OneIGPU(require_accelerator=True)
    def test_invalid_mode(self):
        with self.assertRaises(ValueError): OneIGPU('fake')
    def test_record_tamper(self):
        r=OneIGPU(working_width=32,prime_rom_limit=1000).dispatch([15])
        with self.assertRaises(Exception): replace(r,records=(replace(r.records[0],value=123),)).verify()
    def test_default_runs_full_solve_pipeline(self):
        plan=OneIGPU().golden.plan(NonceLease(0,10))
        self.assertIn('S6_chronos_solver',plan['path']); self.assertEqual(plan['integration_mode'],'solve_first'); self.assertNotIn('experimental',plan)
    def test_explicit_classical_baseline(self):
        plan=OneIGPU(golden_quantum_enabled=False).golden.plan(NonceLease(0,10))
        self.assertEqual(plan['path'],('F3_classical',)); self.assertEqual(plan['integration_mode'],'classical_baseline')
    def test_solve_first(self):
        plan=OneIGPU(golden_quantum_enabled=True).golden.plan(NonceLease(0,10))
        self.assertEqual(plan['path'],('S1_fold_transform','S2_prime_checkpoint','S3_coherence','S4_mandelbrot','S5_infinity_fold','S6_chronos_solver','F3_classical_remainder'))
        self.assertEqual(sorted(plan['order']),list(range(10)))
    def test_solver_failure_fallback(self):
        plan=OneIGPU(golden_quantum_enabled=True).golden.plan(NonceLease(0,10),solver=lambda x: [])
        self.assertIn('F1_golden_quantum_fallback',plan['path']); self.assertIsNotNone(plan['reason'])
    def test_invalid_solver_cannot_change_lease(self):
        lease=NonceLease(0,10); plan=OneIGPU(golden_quantum_enabled=True).golden.plan(lease,solver=lambda x:[999])
        self.assertTrue(all(0<=n<10 for n in plan['order'])); self.assertEqual(lease.stop,10)
    def test_search_facade(self): self.assertEqual(OneIGPU().search(range(5),lambda n:n==2).candidate,2)
    def test_evolve_facade(self): self.assertAlmostEqual(OneIGPU().evolve([1,0],np.eye(2)).probabilities.sum(),1)
    def test_chain(self):
        gpu=OneIGPU(); gpu.search([1,2],lambda n:False); gpu.evolve([1],[[0]])
        self.assertTrue(verify_evidence(gpu.golden.events))
    def test_chain_tamper(self):
        gpu=OneIGPU(); gpu.search([1],lambda n:False); events=[dict(e) for e in gpu.golden.events]; events[0]['backend']='opencl'
        with self.assertRaises(ValueError): verify_evidence(events)
    def test_checkpoint_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'prime.db'
            with OneIGPU(db_path=path) as gpu: obj=gpu.checkpoint(GENESIS_HEADER)
            with OneIGPU(db_path=path) as gpu: self.assertEqual(gpu.restore(obj.object_id),GENESIS_HEADER)
    def test_checkpoint_plan(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            with OneIGPU(db_path=Path(d)/'prime.db',golden_quantum_enabled=True) as gpu:
                obj=gpu.checkpoint(json.dumps({'job_id':'x','epoch':1,'candidates':[3,2]}).encode())
                plan=gpu.golden.plan(NonceLease(0,5,'x',1),checkpoint_id=obj.object_id)
                self.assertEqual(sorted(plan['order']),[2,3])
    def test_stale_checkpoint_fallback(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            with OneIGPU(db_path=Path(d)/'prime.db',golden_quantum_enabled=True) as gpu:
                obj=gpu.checkpoint(json.dumps({'job_id':'x','epoch':1,'candidates':[3,2]}).encode())
                plan=gpu.golden.plan(NonceLease(0,5,'y',2),checkpoint_id=obj.object_id)
                self.assertIn('F1_golden_quantum_fallback',plan['path'])
    def test_quota_rejected(self):
        with self.assertRaises(ValueError): OneIGPU(max_candidates=129)


class TensorFacadeTests(unittest.TestCase):
    def test_tensor_matmul(self): np.testing.assert_array_equal(OneIGPU().tensor('matmul',np.eye(2),np.eye(2)),np.eye(2))
    def test_tensor_hadamard(self): np.testing.assert_array_equal(OneIGPU().tensor('hadamard',[1,2],[3,4]),[3,8])
    def test_tensor_bad_shape(self):
        with self.assertRaises(ValueError): OneIGPU().tensor('add',[1],[1,2])
    def test_mps_bell(self):
        m=OneIGPU().mps(2,bond_dim=2); m.apply_single_qubit_gate(0,np.array([[1,1],[1,-1]])/math.sqrt(2))
        m.apply_two_qubit_gate(0,[[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]])
        np.testing.assert_allclose(m.to_dense(),[1/math.sqrt(2),0,0,1/math.sqrt(2)],atol=1e-12)
    def test_mps_reject_lossy_transactionally(self):
        m=OneIGPU().mps(2,bond_dim=1); m.apply_single_qubit_gate(0,np.array([[1,1],[1,-1]])/math.sqrt(2)); before=m.to_dense().copy()
        with self.assertRaises(ValueError): m.apply_two_qubit_gate(0,[[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]])
        np.testing.assert_allclose(m.to_dense(),before)
    def test_mps_invalid_gate(self):
        with self.assertRaises(ValueError): OneIGPU().mps(2).apply_single_qubit_gate(0,[[1,1],[0,1]])
    def test_mps_budget(self):
        with self.assertRaises(MemoryError): OneIGPU().mps(1000,bond_dim=256)
    def test_mps_1000_product_memory(self): self.assertEqual(OneIGPU().mps(1000,bond_dim=2).memory_bytes(),32000)

if __name__=='__main__': unittest.main()
