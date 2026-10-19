"""Guardian admission, horizontal partitioning, bounded pipelines and measured tuning."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import time,math,hashlib,json,random
from ..golden_quantum import NonceLease,GoldenRatioMining,AdvancedMathematicalOracles
from .scaled_plan import LADDER
class Guardian:
    def admit(self,lease,budget,epoch=None,deadline=None):
        if type(budget)is not int or not 0<=budget<=1000000:raise ValueError('Guardian work quota rejected')
        if epoch is not None and epoch!=lease.epoch:raise ValueError('Guardian stale epoch rejected')
        if deadline is not None and(not math.isfinite(deadline)or time.perf_counter()>=deadline):raise ValueError('Guardian deadline rejected')
        return {'lease':asdict(lease),'budget':budget,'epoch':lease.epoch,'policy':'exact_target_and_owned_work'}
    def verify_candidate(self,prefix,target,lease,result):
        if result.nonce is None:return not result.verified
        if not lease.start<=result.nonce<lease.stop:raise ValueError('Guardian nonce ownership violation')
        digest=AdvancedMathematicalOracles.nonce_digest(prefix,result.nonce)
        if not result.verified or digest.hex()!=result.digest_hex or not AdvancedMathematicalOracles.accepts(digest,target):raise ValueError('Guardian proof verification failed')
        return True
class SwarmCoordinator:
    def __init__(self,workers=1,max_inflight=8):
        if type(workers)is not int or not 1<=workers<=64 or type(max_inflight)is not int or not 1<=max_inflight<=128:raise ValueError('bounded worker/pipeline count required')
        self.workers=workers;self.max_inflight=max_inflight;self.guardian=Guardian()
    def pipeline(self,items,function):
        # Backpressure: no eager materialisation of an unbounded stream.
        iterator=iter(items)
        with ThreadPoolExecutor(max_workers=self.workers)as pool:
            pending=[]
            for _ in range(self.max_inflight):
                try:pending.append(pool.submit(function,next(iterator)))
                except StopIteration:break
            while pending:
                yield pending.pop(0).result()
                try:pending.append(pool.submit(function,next(iterator)))
                except StopIteration:pass
    def scan(self,prefix,target,lease,max_evaluations=65536,weights=None,current_epoch=None,deadline=None):
        self.guardian.admit(lease,max_evaluations,current_epoch,deadline)
        AdvancedMathematicalOracles.accepts(bytes(32),target)
        if not isinstance(prefix,bytes)or len(prefix)!=76:raise ValueError('76-byte header prefix required')
        weights=weights or[1]*self.workers
        if len(weights)!=self.workers:raise ValueError('weight/worker mismatch')
        bounded=NonceLease(lease.start,min(lease.stop,lease.start+max_evaluations),lease.job_id,lease.epoch)
        partitions=bounded.partition(weights);started=time.perf_counter()
        def execute(part):return GoldenRatioMining().scan(prefix,target,part,max_evaluations=part.stop-part.start,current_epoch=current_epoch,deadline=deadline)
        results=list(self.pipeline(partitions,execute));verification_hashes=0
        for part,result in zip(partitions,results):
            if result.sha256d_evaluations>part.stop-part.start:raise ValueError('worker exceeded owned work')
            self.guardian.verify_candidate(prefix,target,part,result);verification_hashes+=int(result.verified)
        duration=time.perf_counter()-started;hashes=sum(r.sha256d_evaluations for r in results)
        return {'logical_device':'chronos_igpu','executor':'cpu_reference','workers':self.workers,'physical_gpu_workers':0,
                'partitions':[asdict(p)for p in partitions],'results':[asdict(r)for r in results],
                'scan_sha256d_evaluations':hashes,'verification_sha256d_evaluations':verification_hashes,
                'elapsed_seconds':duration,'hashrate':hashes/duration if duration else 0,'pool_accepted':None,
                'network_submitted':False,'floor_hps':10**19,'floor_met':bool(duration and hashes/duration>=10**19)}
class GeneticPlanner:
    """Seeded candidate evolution; promotion depends only on observed work/time."""
    def __init__(self,seed=0,min_observations=3,attempt_limit=32):
        if type(min_observations)is not int or not 1<=min_observations<=1000 or type(attempt_limit)is not int or not 1<=attempt_limit<=10000:raise ValueError('bounded genetic observation/attempt windows required')
        self.random=random.Random(seed);self.min_observations=min_observations;self.attempt_limit=attempt_limit
        self.observations={};self.attempts=0;self.champion=None
    def propose(self,kernel_workgroup_limit=64):
        if type(kernel_workgroup_limit)is not int or kernel_workgroup_limit<1:raise ValueError('invalid kernel limit')
        if self.attempts>=self.attempt_limit:raise RuntimeError('genetic attempt limit reached')
        self.attempts+=1
        lanes=self.random.choice([v for v in(1,2,4,8,16,32,64)if v<=kernel_workgroup_limit])
        return {'scale_index':self.random.choice(LADDER),'lanes':lanes,'generation':self.attempts}
    def observe(self,candidate,completed_items,elapsed_seconds):
        if type(completed_items)is not int or completed_items<0 or not math.isfinite(elapsed_seconds)or elapsed_seconds<=0:raise ValueError('real execution observation required')
        if candidate['scale_index']not in LADDER or candidate['lanes']<1:raise ValueError('invalid genotype')
        key=(candidate['scale_index'],candidate['lanes']);samples=self.observations.setdefault(key,[]);samples.append(completed_items/elapsed_seconds)
        if len(samples)<self.min_observations:return {'promoted':False,'reason':'minimum observation window'}
        score=sum(samples)/len(samples)
        if self.champion is None or score>self.champion['measured_items_per_second']:
            self.champion={**candidate,'measured_items_per_second':score,'samples':len(samples)};return {'promoted':True,'champion':self.champion}
        return {'promoted':False,'reason':'measured regression','champion':self.champion}
    def snapshot(self):
        body={'attempts':self.attempts,'attempt_limit':self.attempt_limit,'min_observations':self.min_observations,'champion':self.champion,
              'observations':[[list(k),v]for k,v in sorted(self.observations.items())],'random_state':self.random.getstate()}
        return {**body,'digest':hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    @classmethod
    def restore(cls,data):
        body=dict(data);digest=body.pop('digest')
        if hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=digest:raise ValueError('genetic state digest failure')
        obj=cls(min_observations=body['min_observations'],attempt_limit=body['attempt_limit']);obj.attempts=body['attempts'];obj.champion=body['champion'];obj.observations={tuple(k):v for k,v in body['observations']}
        def tuples(x):return tuple(tuples(v)for v in x)if isinstance(x,(list,tuple))else x
        obj.random.setstate(tuples(body['random_state']));return obj
