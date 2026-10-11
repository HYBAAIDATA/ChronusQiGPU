import unittest,hashlib,tempfile,threading,time,json
from pathlib import Path
from chronos import OneIGPU
from chronos.igpu import MiningJob,JobEpochLedger,PreparedSHA256d,MiningFarm,ASICDriverBridge,Workload,VirtualRuntime
from chronos.golden_quantum import NonceLease,AdvancedMathematicalOracles as Oracle
from chronos.adapters.base import DispatchError,BackendAbsent
GENESIS=bytes.fromhex('01000000'+'00'*32+'3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a'+'29ab5f49'+'ffff001d'+'1dac2b7c')
class PreparedTests(unittest.TestCase):
    def test_hashlib_prepared_matches_host(self):
        p=PreparedSHA256d(prefer_native=False);values=[0,1,2083236893,2**32-1]
        self.assertEqual(p.execute_sha256d(GENESIS[:76],values),tuple(Oracle.nonce_digest(GENESIS[:76],n)for n in values))
    def test_real_genesis_vector(self):
        p=PreparedSHA256d();d=p.execute_sha256d(GENESIS[:76],[2083236893])[0]
        self.assertEqual(d[::-1].hex(),'000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f')
    def test_prefix_tail_rebind(self):
        p=PreparedSHA256d();a=bytes(76);b=bytes(64)+bytes(range(12))
        p.execute_sha256d(a,[0]);r=p.execute_sha256d(b,[17]);self.assertEqual(r[0],Oracle.nonce_digest(b,17));self.assertEqual(p.stats()['first_blocks_prepared'],1)
    def test_changed_first_block_invalidates(self):
        p=PreparedSHA256d();p.execute_sha256d(bytes(76),[0]);p.execute_sha256d(bytes(range(76)),[1]);self.assertEqual(p.stats()['first_blocks_prepared'],2)
    def test_bounded_cache(self):
        p=PreparedSHA256d(cache_entries=2)
        for i in range(4):p.execute_sha256d(bytes([i])*76,[0])
        self.assertEqual(p.stats()['entries'],2)
    def test_native_compact_success(self):
        p=PreparedSHA256d();job=MiningJob(bytes(76),2**256-1,'test',1);r=p.scan_span(job,NonceLease(0,100,'test',1));self.assertTrue(r['verified']);self.assertEqual(r['sha256d_evaluations'],1);self.assertEqual(r['verification_sha256d_evaluations'],1)
    def test_compact_no_success(self):
        p=PreparedSHA256d();job=MiningJob(bytes(76),0,'test',1);r=p.scan_span(job,NonceLease(0,100,'test',1));self.assertFalse(r['verified']);self.assertEqual(r['sha256d_evaluations'],100);self.assertEqual(r['output_bytes'],0)
    def test_nonce_quota(self):
        with self.assertRaises(ValueError):PreparedSHA256d().execute_sha256d(bytes(76),range(4097))
    def test_negative_nonce(self):
        with self.assertRaises(ValueError):PreparedSHA256d().execute_sha256d(bytes(76),[-1])
    def test_identity_mismatch(self):
        with self.assertRaises(ValueError):PreparedSHA256d().scan_span(MiningJob(bytes(76),0,'new',1),NonceLease(0,1,'old',1))
    def test_single_uint32_tail(self):
        p=PreparedSHA256d();job=MiningJob(bytes(76),0,'test',1);r=p.scan_span(job,NonceLease(2**32-1,2**32,'test',1));self.assertEqual(r['sha256d_evaluations'],1)
    def test_midstate_not_padded_digest(self):
        p=PreparedSHA256d()
        if not p.native:self.skipTest('native extension unavailable')
        ctx=p.native.prepare(bytes(76));self.assertNotEqual(p.native.midstate(ctx),hashlib.sha256(bytes(64)).digest())
    def test_native_many_vectors(self):
        p=PreparedSHA256d()
        if not p.native:self.skipTest('native extension unavailable')
        for prefix in (bytes(76),bytes(range(76)),GENESIS[:76]):
            values=list(range(257))+[2**32-1];self.assertEqual(p.execute_sha256d(prefix,values),tuple(Oracle.nonce_digest(prefix,n)for n in values))
    def test_raw_native_rebind_mismatch(self):
        p=PreparedSHA256d()
        if not p.native:self.skipTest('native extension unavailable')
        with self.assertRaises(ValueError):p.native.rebind(p.native.prepare(bytes(76)),bytes(range(76)))
class LedgerTests(unittest.TestCase):
    def test_new_epoch_replaces(self):
        l=JobEpochLedger();a=MiningJob(bytes(76),0,'a',1);b=MiningJob(bytes(76),0,'b',2);l.activate(a);l.activate(b);self.assertFalse(l.is_current(a));self.assertTrue(l.is_current(b))
    def test_same_epoch_different_target_rejected(self):
        l=JobEpochLedger();l.activate(MiningJob(bytes(76),0,'a',1))
        with self.assertRaises(ValueError):l.activate(MiningJob(bytes(76),1,'a',1))
    def test_revoked_epoch_not_reactivated(self):
        l=JobEpochLedger();a=MiningJob(bytes(76),0,'a',1);l.activate(a);l.revoke()
        with self.assertRaises(ValueError):l.activate(a)
    def test_manifest_custody(self):
        job=MiningJob(bytes(76),0,'test',1);self.assertEqual(MiningJob.from_manifest(job.manifest()),job)
class FarmTests(unittest.TestCase):
    def farm(self,**kw):
        f=MiningFarm(**kw);j=MiningJob(bytes(76),0,'test',1);f.ledger.activate(j);return f,j
    def test_parallel_exact_coverage(self):
        f,j=self.farm(lanes=4,batch_size=17,max_inflight=8);r=f.scan(j,NonceLease(0,503,'test',1),max_evaluations=503,weights=[1,2,3,4]);self.assertEqual(r['scan_sha256d_evaluations'],503);self.assertEqual(r['next_contiguous_nonce'],503);self.assertTrue(MiningFarm.verify_receipt(r));self.assertLessEqual(r['peak_inflight'],8)
    def test_budget_clamp(self):
        f,j=self.farm(lanes=3,batch_size=17);r=f.scan(j,NonceLease(0,1000,'test',1),max_evaluations=71);self.assertEqual(r['scan_sha256d_evaluations'],71)
    def test_stopped_before_dispatch(self):
        f,j=self.farm();e=threading.Event();e.set();r=f.scan(j,NonceLease(0,100,'test',1),stop_event=e);self.assertEqual(r['scan_sha256d_evaluations'],0);self.assertTrue(r['cancelled'])
    def test_replaced_during_batch(self):
        f,j=self.farm(batch_size=10);engine=f.engine
        class Replace:
            def capability(self):return engine.capability()
            def scan_span(self,*args):
                r=engine.scan_span(*args);f.ledger.activate(MiningJob(bytes(76),0,'next',2));return r
        f.engine=Replace();r=f.scan(j,NonceLease(0,100,'test',1));self.assertTrue(r['stale']);self.assertIsNone(r['winner']);self.assertGreater(r['scan_sha256d_evaluations'],0)
    def test_stale_initial_rejected(self):
        f,j=self.farm();f.ledger.revoke()
        with self.assertRaises(ValueError):f.scan(j,NonceLease(0,10,'test',1))
    def test_receipt_tamper(self):
        f,j=self.farm();r=f.scan(j,NonceLease(0,17,'test',1));r['scan_sha256d_evaluations']=18
        with self.assertRaises(ValueError):MiningFarm.verify_receipt(r)
    def test_uint32_exhaustion(self):
        f,j=self.farm();r=f.scan(j,NonceLease(2**32-2,2**32,'test',1));self.assertEqual(r['next_contiguous_nonce'],2**32)
    def test_facade_and_abi(self):
        with OneIGPU()as g:
            j=MiningJob(bytes(76),0,'abi',1);w=Workload('asic','local','asic_sha256d',{'job':j.manifest(),'lease':{'start':0,'stop':17,'job_id':'abi','epoch':1}},quota=17)
            r=g.execute_workload(w);self.assertTrue(VirtualRuntime.verify_receipt(r,w));self.assertEqual(r['output']['scan_sha256d_evaluations'],17)
    def test_intelligence_then_prepared_executor(self):
        with OneIGPU()as g:
            adapter=g.configure_asic_like();r=g.mine(bytes(76),0,NonceLease(0,20),max_evaluations=20);self.assertEqual(r.sha256d_evaluations,20);self.assertEqual(r.backend,adapter.capability()['backend']);self.assertIn('S6_chronos_solver',r.path)
class DriverTests(unittest.TestCase):
    def driver(self,bad=False):
        class Driver:
            def capability(self):return {'device_id':'test_driver','backend':'test_simulated_driver','physical':False,'operations':['sha256d']}
            def execute_sha256d(self,prefix,nonces):return [bytes(32)if bad else Oracle.nonce_digest(prefix,n)for n in nonces]
        return Driver()
    def test_configured_driver(self):
        d=ASICDriverBridge(self.driver());self.assertEqual(len(d.execute_sha256d(bytes(76),[0,1])),2);self.assertEqual(d.last_receipt['verification_sha256d_evaluations'],2)
    def test_lying_digest_rejected(self):
        with self.assertRaises(DispatchError):ASICDriverBridge(self.driver(True)).execute_sha256d(bytes(76),[0])
    def test_no_driver_fabricated(self):
        with self.assertRaises(BackendAbsent):ASICDriverBridge(object())
    def test_driver_verification_count(self):
        with OneIGPU()as g:
            g.bind_asic_driver(self.driver());r=g.mine(bytes(76),0,NonceLease(0,17),max_evaluations=17);self.assertEqual(r.sha256d_evaluations,17);self.assertEqual(r.verification_sha256d_evaluations,17)
if __name__=='__main__':unittest.main()

class AdditionalMiningTests(unittest.TestCase):
    def test_checkpoint_restart(self):
        with tempfile.TemporaryDirectory()as d:
            path=Path(d)/'prime.db'
            with OneIGPU(db_path=path)as g:
                job=MiningJob(bytes(76),0,'checkpoint',1);r=g.mine_asic(job,NonceLease(0,71,'checkpoint',1),max_evaluations=71);obj=g.checkpoint_mining(r);identity=obj.object_id
            with OneIGPU(db_path=path)as g:self.assertEqual(g.restore_mining(identity)['next_contiguous_nonce'],71)
    def test_receipt_explosion_rejected(self):
        f=MiningFarm(batch_size=1);j=MiningJob(bytes(76),0,'quota',1);f.ledger.activate(j)
        with self.assertRaises(ValueError):f.scan(j,NonceLease(0,5000,'quota',1),max_evaluations=5000)
    def test_no_silent_native_requirement_fallback(self):
        p=PreparedSHA256d(prefer_native=False);self.assertIsNone(p.native);self.assertEqual(p.capability()['backend'],'hashlib_copy_midstate')

class IdempotencyMiningTests(unittest.TestCase):
    def test_duplicate_request_returns_identical_receipt(self):
        with OneIGPU()as g:
            j=MiningJob(bytes(76),0,'retry',1);w=Workload('retry','tenant','asic_sha256d',{'job':j.manifest(),'lease':{'start':0,'stop':17,'job_id':'retry','epoch':1}},quota=17)
            a=g.execute_workload(w);events=len(g.golden.events);b=g.execute_workload(w);self.assertEqual(a,b);self.assertEqual(events,len(g.golden.events))
    def test_reused_request_id_with_different_target_rejected(self):
        with OneIGPU()as g:
            a=Workload('same','tenant','lucas',{'rungs':[15]},quota=1);g.execute_workload(a)
            with self.assertRaises(ValueError):g.execute_workload(Workload('same','tenant','lucas',{'rungs':[20]},quota=1))
    def test_returned_receipt_mutation_cannot_change_cache(self):
        with OneIGPU()as g:
            w=Workload('same','tenant','lucas',{'rungs':[15]},quota=1);a=g.execute_workload(w);a['backend']='fiction'
            self.assertNotEqual(g.execute_workload(w)['backend'],'fiction')
    def test_concurrent_request_executes_once(self):
        from concurrent.futures import ThreadPoolExecutor
        with OneIGPU()as g:
            runtime=VirtualRuntime(g);w=Workload('concurrent','tenant','lucas',{'rungs':[15]},quota=1)
            with ThreadPoolExecutor(max_workers=8)as pool:receipts=list(pool.map(lambda i:runtime.execute_once(w),range(8)))
            self.assertTrue(all(r==receipts[0]for r in receipts));self.assertEqual(sum(e['operation']=='virtual_abi'for e in g.golden.events),1)
    def test_partial_failure_not_automatically_reexecuted(self):
        with OneIGPU()as g:
            runtime=VirtualRuntime(g);w=Workload('fail','tenant','lucas',{'rungs':[15,20]},quota=1)
            with self.assertRaises(ValueError):runtime.execute_once(w)
            with self.assertRaises(RuntimeError):runtime.execute_once(w)
    def test_true_genesis_candidate(self):
        p=PreparedSHA256d();target=0x00000000FFFF0000000000000000000000000000000000000000000000000000
        j=MiningJob(GENESIS[:76],target,'genesis',1);r=p.scan_span(j,NonceLease(2083236880,2083236900,'genesis',1));self.assertEqual(r['nonce'],2083236893);self.assertTrue(r['verified'])

class FusedPipelineTests(unittest.TestCase):
    def test_ordered_candidate_and_actual_work(self):
        p=PreparedSHA256d();r=p.scan_nonce_batch(bytes(76),[17,10,1],2**256-1);self.assertEqual(r['nonce'],17);self.assertEqual(r['completed'],1);self.assertEqual(r['digest'],Oracle.nonce_digest(bytes(76),17))
    def test_fused_unchanged_domain_negative_control(self):
        p=PreparedSHA256d();r=p.scan_nonce_batch(bytes(76),[17,10,1],0);self.assertIsNone(r['nonce']);self.assertEqual(r['completed'],3);self.assertEqual(p.last_receipt['output_digest_bytes'],0)
    def test_host_verification_counts_in_full_path(self):
        with OneIGPU()as g:
            g.configure_asic_like();r=g.mine(bytes(76),2**256-1,NonceLease(0,20),max_evaluations=20);self.assertTrue(r.verified);self.assertEqual(r.sha256d_evaluations,1);self.assertEqual(r.verification_sha256d_evaluations,2)
    def test_direct_native_unbounded_generator_rejected(self):
        p=PreparedSHA256d()
        if not p.native:self.skipTest('native extension unavailable')
        ctx=p.native.prepare(bytes(76))
        with self.assertRaises(ValueError):p.native.hash_batch(ctx,iter(range(10000)))
    def test_fused_hashlib_fallback(self):
        r=PreparedSHA256d(prefer_native=False).scan_nonce_batch(bytes(76),[17,10],2**256-1);self.assertEqual(r['nonce'],17)

class MiningServiceLifecycleTests(unittest.TestCase):
    def test_authenticated_service_retry_and_sigterm(self):
        import subprocess,sys,os,socket,secrets,urllib.request
        with socket.socket()as reserve:reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
        token=secrets.token_urlsafe(32);env=dict(os.environ,CHRONOS_SERVICE_TOKEN=token)
        with tempfile.TemporaryDirectory()as d:
            child=subprocess.Popen([sys.executable,'-m','chronos.igpu.service','--port',str(port),'--mining-backend','prepared','--db-path',str(Path(d)/'state.db')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                base=f'http://127.0.0.1:{port}';ready=False
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(base+'/health',timeout=.2)as response:ready=json.loads(response.read())['status']=='ready'
                        if ready:break
                    except Exception:time.sleep(.03)
                self.assertTrue(ready)
                job=MiningJob(bytes(76),0,'service',1);w=Workload('repeat','local','asic_sha256d',{'job':job.manifest(),'lease':{'start':0,'stop':29,'job_id':'service','epoch':1}},quota=29)
                def post():
                    request=urllib.request.Request(base+'/v1/workloads',data=json.dumps(w.body()).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                    with urllib.request.urlopen(request,timeout=5)as response:return json.loads(response.read())
                a,b=post(),post();self.assertEqual(a,b);self.assertEqual(a['result']['output']['scan_sha256d_evaluations'],29)
                child.terminate();self.assertEqual(child.wait(timeout=5),0)
            finally:
                if child.poll()is None:child.kill();child.wait()
