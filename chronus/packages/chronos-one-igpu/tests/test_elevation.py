import sys,unittest,tempfile,subprocess,shutil,math,json
from pathlib import Path
from dataclasses import replace
from fractions import Fraction
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from chronos import OneIGPU,NonceLease
from chronos.igpu import ScaledPlan,ExactFoldState,WitnessCache,ComputeFabric,Guardian,SwarmCoordinator,GeneticPlanner,QXBuffer,QXExecutor,encoded_matrix
from chronos.igpu.geometry11d import phi_norm,fold_11d,unfold_11d,zeckendorf_certificate,restore_certificate
from chronos.lucas_engine import lucas
from chronos.adapters.base import DispatchError
class ScalingTests(unittest.TestCase):
    def test_independent_contract(self):
        d=OneIGPU().compose();self.assertEqual(d['contract_device']['device_id'],'chronos_igpu');self.assertTrue(d['contract_device']['independent_of_physical_gpu']);self.assertEqual(d['executors'][0]['backend'],'cpu_reference')
    def test_lucas_scaling(self):self.assertEqual(ScaledPlan(3,15).effective_items,4092)
    def test_stream_coverage(self):
        p=ScaledPlan(3,10,start=10);parts=list(p.chunks(7));self.assertEqual(parts[0][0],10);self.assertEqual(parts[-1][1],379);self.assertTrue(all(a[1]==b[0]for a,b in zip(parts,parts[1:])))
    def test_scale_clamp(self):self.assertEqual(ScaledPlan(2**31,110).effective_items,2**32)
    def test_off_ladder(self):
        with self.assertRaises(ValueError):ScaledPlan(1,14)
    def test_scaled_search(self):
        result=OneIGPU().scaled_search(1,lambda n:n==100,10,max_evaluations=123);self.assertTrue(result['result'].success);self.assertEqual(result['plan']['effective_items'],123)
    def test_overlay_no_gpu_still_native(self):
        gpu=OneIGPU('host_gpu_overlay',working_width=32,prime_rom_limit=1000)
        self.assertEqual(gpu.compose()['contract_device']['device_id'],'chronos_igpu');self.assertTrue(gpu.dispatch([1,2,15]).verify())
    def test_backend_is_distinct_from_identity(self):
        result=OneIGPU(working_width=32,prime_rom_limit=1000).dispatch([15]);self.assertEqual(result.plan['logical_device'],'chronos_igpu');self.assertEqual(result.plan['executor'],'cpu_reference')
    def test_host_overlay_rejects_wrong_result(self):
        class Bad:
            last_receipt=None
            def capability(self):return {'backend':'test_transport','device_id':'fault-injection','physical':False}
            def execute_lucas(self,rungs,width):return [0]*len(rungs)
        with self.assertRaises(DispatchError):OneIGPU(host_adapter=Bad(),working_width=32,prime_rom_limit=1000).dispatch([15])
    def test_host_overlay_dispatch_and_verify(self):
        class Transport:
            last_receipt={'physical':False,'executor':'test_transport'}
            def capability(self):return {'backend':'test_transport','device_id':'conformance-transport','physical':False}
            def execute_lucas(self,rungs,width):return [lucas(n)%(1<<width)for n in rungs]
        result=OneIGPU('host_gpu_overlay',host_adapter=Transport(),working_width=32,prime_rom_limit=1000).dispatch([1,2,15]);self.assertEqual(result.backend,'test_transport');self.assertTrue(result.verify());self.assertFalse(result.evidence['details']['hardware_accelerated'])
class FoldTests(unittest.TestCase):
    def test_exact_fraction(self):
        f=ExactFoldState.fold([1,Fraction(1,3),-7,8,9]);self.assertTrue(f.verify());self.assertEqual(f.unfold(),(1,Fraction(1,3),-7,8,9))
    def test_selective_independent(self):
        from unittest.mock import patch
        f=ExactFoldState.fold(range(11))
        with patch.object(ExactFoldState,'unfold',side_effect=AssertionError('full unfold forbidden')):self.assertEqual(f.unfold_partial([10,1,4]),(10,1,4))
    def test_folded_operator(self):self.assertEqual(ExactFoldState.fold(range(9)).scale(1364).unfold(),tuple(n*1364 for n in range(9)))
    def test_roundtrip_transport(self):
        f=ExactFoldState.fold([1,2,3]);self.assertEqual(ExactFoldState.from_dict(json.loads(json.dumps(f.to_dict()))).unfold(),(1,2,3))
    def test_tamper(self):
        f=ExactFoldState.fold([1,2,3]);d=f.to_dict();d['levels'][0][0][0][0]+=1
        with self.assertRaises(ValueError):ExactFoldState.from_dict(d)
    def test_11d_roundtrip(self):
        values=tuple(i/100 for i in range(11));np.testing.assert_allclose(unfold_11d(fold_11d(values)),values,atol=1e-12);self.assertLess(phi_norm(fold_11d(values)),1)
    def test_11d_exact_transport(self):
        values=tuple((-1)**i*(i+0.125)for i in range(11));self.assertEqual(restore_certificate(zeckendorf_certificate(values)),values)
    def test_11d_wrong_shape(self):
        with self.assertRaises(ValueError):fold_11d([1,2])
class CacheTests(unittest.TestCase):
    def test_10000_witness(self):
        with tempfile.TemporaryDirectory()as d:
            cache=WitnessCache(d);identity=cache.put(bytes(1250),10000);record=cache.get(identity);self.assertEqual(len(record['bits']),1250);self.assertIsNone(record['hash_equivalent_operations']);self.assertLess(cache.capacity()['payload_only_upper_bound'],80000000);cache.close()
    def test_dedup(self):
        with tempfile.TemporaryDirectory()as d:
            cache=WitnessCache(d,image_bytes=0);a=cache.put(b'\x01',8);size=cache.usage();b=cache.put(b'\x01',8);self.assertEqual(a,b);self.assertEqual(cache.usage(),size);cache.close()
    def test_restart(self):
        with tempfile.TemporaryDirectory()as d:
            cache=WitnessCache(d,image_bytes=0);identity=cache.put(b'\xff',8);cache.close();cache=WitnessCache(d,image_bytes=0);self.assertEqual(cache.get(identity)['bits'],b'\xff');cache.close()
    def test_quota(self):
        with tempfile.TemporaryDirectory()as d:
            cache=WitnessCache(d,total_budget_bytes=100000,image_bytes=0)
            with self.assertRaises(OSError):cache.put(bytes(1250),10000)
            cache.close()
    def test_corruption(self):
        with tempfile.TemporaryDirectory()as d:
            cache=WitnessCache(d,image_bytes=0);identity=cache.put(b'\x01',8);p=next(Path(d).glob('shard-*.bin'))
            with open(p,'r+b')as f:f.seek(40);f.write(b'\x02')
            with self.assertRaises(ValueError):cache.get(identity)
            cache.close()
    def test_circuit(self):
        with tempfile.TemporaryDirectory()as d:
            cache=WitnessCache(d,image_bytes=0);result=cache.execute_permutation(10000,[('X',0),('CNOT',0,9999)]);self.assertEqual(result['bits'][0]&1,1);self.assertEqual(result['bits'][-1]>>7,1);cache.close()
    def test_crash_tail_recovery(self):
        with tempfile.TemporaryDirectory()as d:
            cache=WitnessCache(d,image_bytes=0);identity=cache.put(b'\x01',8);p=next(Path(d).glob('shard-*.bin'));end=p.stat().st_size
            with open(p,'ab')as f:f.write(b'orphan crash tail')
            cache.recover();self.assertEqual(p.stat().st_size,end);self.assertEqual(cache.get(identity)['bits'],b'\x01');cache.close()
class ControlTests(unittest.TestCase):
    def test_guardian_stale(self):
        with self.assertRaises(ValueError):Guardian().admit(NonceLease(0,10,epoch=1),10,epoch=2)
    def test_pipeline(self):self.assertEqual(list(SwarmCoordinator(3,2).pipeline(range(20),lambda n:n*n)),[n*n for n in range(20)])
    def test_swarm_disjoint_real_work(self):
        r=SwarmCoordinator(3).scan(bytes(76),0,NonceLease(0,50),max_evaluations=17);self.assertEqual(r['scan_sha256d_evaluations'],17);self.assertEqual([n for p in r['partitions']for n in range(p['start'],p['stop'])],list(range(17)));self.assertFalse(r['floor_met']);self.assertEqual(r['physical_gpu_workers'],0)
    def test_swarm_proof(self):
        r=SwarmCoordinator(2).scan(bytes(76),2**256-1,NonceLease(0,4),max_evaluations=4);self.assertEqual(r['verification_sha256d_evaluations'],2);self.assertFalse(r['network_submitted'])
    def test_genetic_observation_gate(self):
        g=GeneticPlanner();c=g.propose(16);self.assertLessEqual(c['lanes'],16);self.assertFalse(g.observe(c,10,1)['promoted']);self.assertFalse(g.observe(c,10,1)['promoted']);self.assertTrue(g.observe(c,10,1)['promoted'])
    def test_genetic_no_fixed_multiplier(self):
        g=GeneticPlanner(min_observations=1);a={'scale_index':15,'lanes':8};b={'scale_index':20,'lanes':16};g.observe(a,10,1);self.assertFalse(g.observe(b,1,1)['promoted'])
    def test_genetic_restart(self):
        g=GeneticPlanner(seed=7);g.propose();clone=GeneticPlanner.restore(json.loads(json.dumps(g.snapshot())));self.assertEqual(g.propose(),clone.propose())
class QXTests(unittest.TestCase):
    def test_evolve_expectation(self):
        commands=[{'op':'allocate','amplitudes':encoded_matrix([1,0])},{'op':'bind_hamiltonian','matrix':encoded_matrix([[0,1],[1,0]])},{'op':'evolve','time':math.pi/2},{'op':'expectation','matrix':encoded_matrix([[1,0],[0,-1]]),'output':'z'},{'op':'barrier'},{'op':'synchronize'}]
        result=QXExecutor().execute(QXBuffer.seal(commands));self.assertAlmostEqual(result['readouts']['z'],-1);self.assertEqual(len(result['events']),2)
    def test_tamper(self):
        b=QXBuffer.seal([])
        with self.assertRaises(ValueError):QXExecutor().execute(replace(b,digest='bad'))
    def test_nonunitary_correction(self):
        commands=[{'op':'allocate','amplitudes':encoded_matrix([1,0])},{'op':'correct','matrix':encoded_matrix([[1,1],[0,1]])}]
        with self.assertRaises(ValueError):QXExecutor().execute(QXBuffer.seal(commands))
    def test_invalid_input_norm(self):
        with self.assertRaises(ValueError):QXExecutor().execute(QXBuffer.seal([{'op':'allocate','amplitudes':encoded_matrix([2,0])}]))
    def test_weak_measure(self):
        b=QXBuffer.seal([{'op':'allocate','amplitudes':encoded_matrix([1,0])},{'op':'weak_measure','strength':1}]);self.assertEqual(QXExecutor().execute(b)['readouts']['weak']['outcome'],0)
class KernelTests(unittest.TestCase):
    def test_exact_opencl_kernel_source_under_native_cpu_conformance(self):
        compiler=shutil.which('g++')
        if not compiler:self.skipTest('C++ compiler unavailable')
        kernel=Path(__file__).resolve().parent.parent/'src/chronos/igpu/kernels/lucas256.cl'
        source='#include <cstdint>\n#include <iostream>\n#include <iomanip>\nusing uint=uint32_t; using ulong=uint64_t;\n#define __kernel\n#define __global\n#define get_global_id(x) 0\n'+kernel.read_text()+'\nint main(){ulong n;while(std::cin>>n){uint out[8];chronos_lucas256(&n,out,1);for(int j=7;j>=0;j--)std::cout<<std::hex<<std::setw(8)<<std::setfill(\'0\')<<out[j];std::cout<<std::endl<<std::dec;}}'
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'kernel.cpp';p.write_text(source);binary=Path(d)/'kernel';subprocess.run([compiler,'-std=c++17','-O2',str(p),'-o',str(binary)],check=True,capture_output=True)
            rungs=list(range(130))+[255,256,511,512,1024,5000]
            output=subprocess.run([str(binary)],input='\n'.join(map(str,rungs)),text=True,capture_output=True,check=True).stdout.splitlines()
            self.assertEqual([int(v,16)for v in output],[lucas(n)%(1<<256)for n in rungs])
if __name__=='__main__':unittest.main()
class AdditionalCoreTests(unittest.TestCase):
    def test_golden_phase_feedback(self):
        from chronos.golden_quantum import GoldenQuantumComputer
        r=GoldenQuantumComputer().simulate_golden_feedback(8,lambda n:n==3)
        self.assertEqual(r.candidate,3);self.assertEqual(r.oracle_calls,8);self.assertAlmostEqual(sum(abs(x)**2 for x in r.amplitudes),1)
    def test_fallback_actual_oracle_accounting(self):
        result=OneIGPU().mine(bytes(76),0,NonceLease(0,20),max_evaluations=20,solver=lambda x:[])
        self.assertFalse(result.verified);self.assertEqual(result.sha256d_evaluations,20);self.assertIn('F1_golden_quantum_fallback',result.path);self.assertIn('F2_golden_nonce',result.path)
    def test_fallback_actual_success(self):
        result=OneIGPU().mine(bytes(76),2**256-1,NonceLease(0,8),max_evaluations=8,solver=lambda x:[])
        self.assertTrue(result.verified);self.assertEqual(result.sha256d_evaluations,8);self.assertEqual(result.verification_sha256d_evaluations,1)
    def test_one_gpu_alias(self):
        from chronos.golden_quantum import SuperGPU,InfinityGPU
        gpu=OneIGPU();facade=SuperGPU(gpu);self.assertIs(facade.gpu,gpu);self.assertIs(SuperGPU,InfinityGPU);self.assertIs(gpu.golden.fabric,gpu.fabric)
    def test_abi_custody(self):
        from chronos.igpu import Workload,VirtualRuntime
        gpu=OneIGPU(working_width=32,prime_rom_limit=1000);w=Workload('unit','tenant','lucas',{'rungs':[15]},quota=1)
        r=gpu.execute_workload(w);self.assertTrue(VirtualRuntime.verify_receipt(r,w));self.assertEqual(r['output']['values'],[1364])
    def test_abi_wrong_root_rejected(self):
        from chronos.igpu import Workload
        with self.assertRaises(ValueError):OneIGPU().execute_workload(Workload('liar','tenant','lucas',{'rungs':[15]},trust_class='hardware_root'))
    def test_paradigm_spine(self):
        from chronos.paradigm import run_triad
        self.assertTrue(run_triad().passed)
    def test_golden_bijection(self):
        from chronos.paradigm import nonce_walk
        for n in [1,11,64,257,600]:self.assertEqual(sorted(nonce_walk(n)),list(range(n)))
    def test_sha_opencl_source_under_native_cpu_conformance(self):
        import hashlib
        compiler=shutil.which('g++')
        if not compiler:self.skipTest('C++ compiler unavailable')
        kernel=Path(__file__).resolve().parent.parent/'src/chronos/igpu/kernels/sha256d.cl'
        source='#include <cstdint>\n#include <iostream>\n#include <iomanip>\nusing uint=uint32_t;using uchar=unsigned char;\n#define __kernel\n#define __global\n#define __constant const\n#define get_global_id(x) 0\n'+kernel.read_text()+'\nint main(){uchar prefix[76];for(int i=0;i<76;i++)prefix[i]=(uchar)i;uint n;while(std::cin>>n){uint out[8];chronos_sha256d(prefix,&n,out,1);for(int j=0;j<8;j++)std::cout<<std::hex<<std::setw(8)<<std::setfill(\'0\')<<out[j];std::cout<<std::endl<<std::dec;}}'
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'kernel.cpp';p.write_text(source);binary=Path(d)/'kernel';subprocess.run([compiler,'-std=c++17','-O2',str(p),'-o',str(binary)],check=True,capture_output=True)
            nonces=[0,1,2,15,65535,2083236893,2**32-1]
            actual=subprocess.run([str(binary)],input='\n'.join(map(str,nonces)),text=True,capture_output=True,check=True).stdout.splitlines()
            expected=[hashlib.sha256(hashlib.sha256(bytes(range(76))+n.to_bytes(4,'little')).digest()).hexdigest()for n in nonces]
            self.assertEqual(actual,expected)
class CertifiedObjectTests(unittest.TestCase):
    def test_all_views(self):
        from chronos.igpu import CertifiedMLAObject
        obj=CertifiedMLAObject.create([1,Fraction(1,3),1+2j])
        for mode in('GET EXACT','GET FOLDED','GET PROJECTION','GET PROOF','GET EXECUTABLE'):self.assertEqual(obj.retrieve(mode)['object_id'],obj.object_id)
        self.assertFalse(obj.retrieve('GET EXACT')['rehydrated_internally']);self.assertFalse(obj.retrieve('GET PROJECTION')['authoritative'])
    def test_unknown_view_rejected(self):
        from chronos.igpu import CertifiedMLAObject
        with self.assertRaises(ValueError):CertifiedMLAObject.create([1]).retrieve('GET FICTION')
    def test_certified_persistence(self):
        with tempfile.TemporaryDirectory()as d:
            with OneIGPU(db_path=Path(d)/'prime.db')as gpu:obj=gpu.ingest_certified([1,2,3]);identity=obj.object_id
            with OneIGPU(db_path=Path(d)/'prime.db')as gpu:self.assertTrue(gpu.retrieve_certified(identity,'GET PROOF')['fold_valid'])
    def test_symbolic_large_address(self):
        from chronos.golden_quantum import TransfiniteMemoryMapper
        address=TransfiniteMemoryMapper().logical_address(2**100);self.assertEqual(address['index'],str(2**100));self.assertFalse(address['physical_storage_allocated'])
    def test_mandelbrot_boundary(self):
        from chronos.golden_quantum import MandelbrotResonanceEngine
        result=MandelbrotResonanceEngine().snap_boundary(3+0j);self.assertLess(result['bracket_width'],1e-10)
    def test_uci_time_binding(self):
        from chronos.golden_quantum import OmniscienceKernel
        k=OmniscienceKernel();result=k.evolve([1,0],[[0,1],[1,0]],time=math.pi,h=2*k.registry.snapshot()['h']);self.assertAlmostEqual(result['state'].probabilities[1],1)
class ReplayTests(unittest.TestCase):
    def test_circuit_replay(self):
        with tempfile.TemporaryDirectory()as d:
            cache=WitnessCache(d,image_bytes=0);result=cache.execute_permutation(10000,[('X',0),('CNOT',0,9999),('SWAP',0,1)]);self.assertTrue(cache.replay_execution(result['execution_receipt']));cache.close()
    def test_signed_evidence(self):
        from chronos.igpu import verify_evidence
        key=bytes(range(32));gpu=OneIGPU(evidence_key=key);gpu.search([1,2],lambda n:n==2)
        head=gpu.golden.events[-1]['digest'];self.assertTrue(verify_evidence(gpu.golden.events,key,head))
        with self.assertRaises(ValueError):verify_evidence(gpu.golden.events,b'x'*32,head)
    def test_truncated_chain_rejected(self):
        from chronos.igpu import verify_evidence
        gpu=OneIGPU();gpu.search([1],lambda n:False);gpu.search([2],lambda n:False)
        with self.assertRaises(ValueError):verify_evidence(gpu.golden.events[:1],expected_head=gpu.golden.events[-1]['digest'])
class ServiceTests(unittest.TestCase):
    def test_service_missing_token_rejected(self):
        from chronos.igpu.service import AcceleratorService
        with self.assertRaises(ValueError):AcceleratorService(OneIGPU(),'')
    def test_remote_plaintext_nonlocal_rejected(self):
        from chronos.igpu import RemoteOverlay
        with self.assertRaises(ValueError):RemoteOverlay('http://example.com','x'*32)
    def test_authenticated_native_remote_roundtrip(self):
        from http.server import HTTPServer
        from chronos.igpu.service import AcceleratorService
        from chronos.igpu import RemoteOverlay
        import threading
        gpu=OneIGPU(working_width=32,prime_rom_limit=1000);server=HTTPServer(('127.0.0.1',0),AcceleratorService(gpu,'unit-test-key-not-a-production-secret').handler())
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            remote=RemoteOverlay(f'http://127.0.0.1:{server.server_port}','unit-test-key-not-a-production-secret')
            self.assertFalse(remote.capability()['physical']);self.assertEqual(remote.execute_lucas([1,2,15],32),(1,3,1364))
            from chronos.golden_quantum import AdvancedMathematicalOracles
            self.assertEqual(remote.execute_sha256d(bytes(76),[0,1]),tuple(AdvancedMathematicalOracles.nonce_digest(bytes(76),n)for n in[0,1]))
        finally:server.shutdown();server.server_close();thread.join(timeout=2);gpu.close()

class ReleaseIntegrityTests(unittest.TestCase):
    def test_rehashed_projection_rejected(self):
        from chronos.igpu import CertifiedMLAObject
        import hashlib,json
        data=CertifiedMLAObject.create([1,2]).to_dict();data['body']['binet_view']['authoritative']=True
        data['object_id']=hashlib.sha256(json.dumps(data['body'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self.assertRaises(ValueError):CertifiedMLAObject.from_dict(data)
    def test_rehashed_trust_change_rejected(self):
        from chronos.igpu import Workload,VirtualRuntime
        from chronos.igpu.virtual_abi import canonical
        import hashlib
        gpu=OneIGPU(working_width=32,prime_rom_limit=1000);w=Workload('trust','tenant','lucas',{'rungs':[15]},quota=1)
        receipt=gpu.execute_workload(w);receipt['trust_class']='unsigned_local';body=dict(receipt);body.pop('receipt_digest');receipt['receipt_digest']=hashlib.sha256(canonical(body)).hexdigest()
        with self.assertRaises(ValueError):VirtualRuntime.verify_receipt(receipt,w)
    def test_scaling_preserves_unknown_image_size(self):
        from chronos.igpu.scaling_validation import scaling_report
        r=scaling_report(completed_hashes=100,elapsed_seconds=1,native_available=True)
        self.assertIsNone(r['checks']['SCALE1']);self.assertFalse(r['floor_met']);self.assertFalse(r['checks']['SCALE4']['used_as_hashrate_multiplier'])
    def test_genetic_configuration_bounded(self):
        from chronos.igpu import GeneticPlanner
        with self.assertRaises(ValueError):GeneticPlanner(min_observations=0)
