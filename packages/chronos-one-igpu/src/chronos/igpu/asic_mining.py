"""ASIC-like prepared hashing and scheduled lanes atop ONE iGPU's exact authority."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from dataclasses import dataclass,asdict
import hashlib,json,math,threading,time
from itertools import islice
from ..adapters.base import BackendAbsent,DispatchError
from ..golden_quantum import NonceLease,AdvancedMathematicalOracles as Oracle

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

@dataclass(frozen=True)
class MiningJob:
    header_prefix:bytes
    target:int
    job_id:str='offline'
    epoch:int=0
    def __post_init__(self):
        if not isinstance(self.header_prefix,bytes)or len(self.header_prefix)!=76:raise ValueError('76-byte immutable header prefix required')
        Oracle.accepts(bytes(32),self.target)
        if not isinstance(self.job_id,str)or not 1<=len(self.job_id)<=128 or type(self.epoch)is not int or self.epoch<0:raise ValueError('bounded job identity and nonnegative epoch required')
    def manifest(self):return {'schema':'chronos_mining_job_v1','header_prefix':self.header_prefix.hex(),'target':str(self.target),'job_id':self.job_id,'epoch':self.epoch}
    @property
    def commitment(self):return hashlib.sha256(canonical(self.manifest())).hexdigest()
    @classmethod
    def from_manifest(cls,m):
        if m.get('schema')!='chronos_mining_job_v1'or set(m)!={'schema','header_prefix','target','job_id','epoch'}:raise ValueError('unknown mining-job schema/fields')
        return cls(bytes.fromhex(m['header_prefix']),int(m['target']),m['job_id'],m['epoch'])

class JobEpochLedger:
    def __init__(self):self.lock=threading.RLock();self.current=None;self.generation=0;self._epoch_floor=-1
    def activate(self,job):
        if not isinstance(job,MiningJob):raise ValueError('MiningJob required')
        with self.lock:
            if self.current is not None:
                if job.commitment==self.current.commitment:return self.generation
                if job.epoch<=self.current.epoch:raise ValueError('new work requires a strictly newer epoch')
            if job.epoch<=self._epoch_floor:raise ValueError('revoked epoch cannot be reactivated')
            self.current=job;self._epoch_floor=job.epoch;self.generation+=1;return self.generation
    def is_current(self,job):
        with self.lock:return self.current is not None and self.current.commitment==job.commitment
    def revoke(self):
        with self.lock:self.current=None;self.generation+=1
    def snapshot(self):
        with self.lock:return {'generation':self.generation,'current_job':self.current.manifest()if self.current else None,'commitment':self.current.commitment if self.current else None}

class PreparedSHA256d:
    """Prepared first SHA block; native C or explicit OpenSSL/hashlib-copy executor."""
    def __init__(self,prefer_native=True,require_native=False,cache_entries=64):
        if type(cache_entries)is not int or not 1<=cache_entries<=1024:raise ValueError('bounded midstate cache required')
        self.native=None
        if prefer_native or require_native:
            try:from . import _sha256d_native;self.native=_sha256d_native
            except ImportError:
                if require_native:raise BackendAbsent('native midstate extension is not installed')
        self.cache_entries=cache_entries;self.base_cache=OrderedDict();self.lock=threading.RLock();self.last_receipt=None
        self.prepares=0;self.cache_hits=0
    def capability(self):return {'device_id':'host_native_sha256d'if self.native else'host_hashlib_midstate','backend':self.native.implementation()['backend']if self.native else'hashlib_copy_midstate','physical':False,'physical_asic':False,'operations':['sha256d'],'asic_like':True,'compression_model':'one prepared first block + two compression blocks per nonce','compact_candidates':bool(self.native),'native_gil_released':bool(self.native)}
    def _prepare(self,prefix):
        if not isinstance(prefix,bytes)or len(prefix)!=76:raise ValueError('76-byte immutable prefix required')
        key=prefix[:64]
        with self.lock:
            if key in self.base_cache:
                base=self.base_cache.pop(key);self.base_cache[key]=base;self.cache_hits+=1;prepared_blocks=0
            else:
                if self.native:base=self.native.prepare(prefix)
                else:base=hashlib.sha256(key)
                self.base_cache[key]=base;self.prepares+=1;prepared_blocks=1
                if len(self.base_cache)>self.cache_entries:self.base_cache.popitem(last=False)
            context=self.native.rebind(base,prefix)if self.native else base
        return context,prepared_blocks
    @staticmethod
    def _nonce_values(nonces):
        values=list(islice(nonces,4097))
        if len(values)>4096 or any(type(n)is not int or not 0<=n<2**32 for n in values):raise ValueError('bounded uint32 nonce batch required')
        return values
    def execute_sha256d(self,prefix,nonces):
        values=self._nonce_values(nonces);started=time.perf_counter();context,prepared=self._prepare(prefix)
        if self.native:
            raw=self.native.hash_batch(context,values);outputs=tuple(raw[i:i+32]for i in range(0,len(raw),32))
        else:
            out=[]
            for n in values:
                h=context.copy();h.update(prefix[64:]+n.to_bytes(4,'little'));out.append(hashlib.sha256(h.digest()).digest())
            outputs=tuple(out)
        self.last_receipt={**self.capability(),'operation':'sha256d','items_executed':len(values),'prefix_digest':hashlib.sha256(prefix).hexdigest(),'first_blocks_prepared':prepared,'compression_blocks_executed':prepared+2*len(values),'wall_seconds':time.perf_counter()-started}
        return outputs
    def scan_nonce_batch(self,prefix,nonces,target):
        values=self._nonce_values(nonces);Oracle.accepts(bytes(32),target);started=time.perf_counter();context,prepared=self._prepare(prefix)
        if self.native:completed,nonce,digest=self.native.scan_batch(context,values,target.to_bytes(32,'little'))
        else:
            completed=0;nonce=digest=None
            for n in values:
                h=context.copy();h.update(prefix[64:]+n.to_bytes(4,'little'));d=hashlib.sha256(h.digest()).digest();completed+=1
                if Oracle.accepts(d,target):nonce=n;digest=d;break
        self.last_receipt={**self.capability(),'operation':'fused_ordered_scan','items_executed':completed,'first_blocks_prepared':prepared,'compression_blocks_executed':prepared+2*completed,'wall_seconds':time.perf_counter()-started,'output_digest_bytes':32 if nonce is not None else 0,'candidate_independently_host_verified':False}
        return {'completed':completed,'nonce':nonce,'digest':digest}
    def scan_span(self,job,lease,max_evaluations=4096):
        if not isinstance(job,MiningJob)or not isinstance(lease,NonceLease)or lease.job_id!=job.job_id or lease.epoch!=job.epoch:raise ValueError('job/lease identity mismatch')
        if type(max_evaluations)is not int or not 0<=max_evaluations<=4096:raise ValueError('native compact batch quota')
        count=min(max_evaluations,lease.stop-lease.start);started=time.perf_counter();context,prepared=self._prepare(job.header_prefix)
        if self.native and count:completed,nonce,digest=self.native.scan_range(context,lease.start,count,job.target.to_bytes(32,'little'))
        else:
            completed=0;nonce=digest=None
            for n in range(lease.start,lease.start+count):
                h=context.copy();h.update(job.header_prefix[64:]+n.to_bytes(4,'little'));d=hashlib.sha256(h.digest()).digest();completed+=1
                if Oracle.accepts(d,job.target):nonce=n;digest=d;break
        verify_hashes=0
        if nonce is not None:
            expected=Oracle.nonce_digest(job.header_prefix,nonce);verify_hashes=1
            if digest!=expected or not Oracle.accepts(expected,job.target):raise DispatchError('compact mining result failed independent host verification')
        duration=time.perf_counter()-started
        return {'schema':'chronos_asic_like_batch_v1','job_commitment':job.commitment,'job_id':job.job_id,'epoch':job.epoch,'lease':asdict(lease),'nonce':nonce,'digest_hex':digest.hex()if digest else None,'verified':nonce is not None,'sha256d_evaluations':completed,'verification_sha256d_evaluations':verify_hashes,'first_blocks_prepared':prepared,'compression_blocks_executed':prepared+2*completed,'backend':self.capability()['backend'],'elapsed_seconds':duration,'output_bytes':32 if nonce is not None else 0,'physical_asic':False,'pool_accepted':None,'network_submitted':False}
    def stats(self):
        with self.lock:return {'entries':len(self.base_cache),'capacity':self.cache_entries,'first_blocks_prepared':self.prepares,'midstate_cache_hits':self.cache_hits,'native':bool(self.native)}

class ASICDriverBridge:
    """Explicit configured full-digest driver contract; never fabricates a device."""
    def __init__(self,driver):
        if not hasattr(driver,'capability')or not hasattr(driver,'execute_sha256d'):raise BackendAbsent('configured ASIC-compatible driver required')
        c=driver.capability()
        if 'sha256d'not in c.get('operations',[])or not c.get('device_id')or not c.get('backend'):raise BackendAbsent('driver lacks SHA256d capability/identity')
        self.driver=driver;self.last_receipt=None
    def capability(self):
        c=dict(self.driver.capability());c['driver_identity_is_not_hardware_root']=True;return c
    def execute_sha256d(self,prefix,nonces):
        values=PreparedSHA256d._nonce_values(nonces)
        if not isinstance(prefix,bytes)or len(prefix)!=76:raise ValueError('76-byte prefix required')
        started=time.perf_counter();outputs=tuple(islice(self.driver.execute_sha256d(prefix,values),len(values)+1))
        if len(outputs)!=len(values)or any(not isinstance(d,bytes)or len(d)!=32 for d in outputs):raise DispatchError('ASIC driver result shape violation')
        # This full-digest bridge verifies all outputs. Candidate-only devices need a
        # separate native vendor protocol; no output count is inferred from a winner.
        for n,d in zip(values,outputs):
            if d!=Oracle.nonce_digest(prefix,n):raise DispatchError('ASIC driver digest failed host verification')
        self.last_receipt={**self.capability(),'items_executed':len(values),'verification_sha256d_evaluations':len(values),'wall_seconds':time.perf_counter()-started,'host_verified':True,'hardware_root_claimed':False}
        return outputs

class MiningFarm:
    """Measured lane scheduling, bounded queues, epoch cancellation and resume cursor."""
    def __init__(self,engine=None,lanes=1,batch_size=1024,max_inflight=2,ledger=None):
        if any(type(v)is not int for v in(lanes,batch_size,max_inflight))or not 1<=lanes<=16 or not 1<=batch_size<=4096 or not 1<=max_inflight<=32:raise ValueError('bounded lane/batch/queue dimensions required')
        self.engine=engine or PreparedSHA256d();self.lanes=lanes;self.batch_size=batch_size;self.max_inflight=max_inflight;self.ledger=ledger or JobEpochLedger()
    def scan(self,job,lease,max_evaluations=65536,weights=None,deadline=None,stop_event=None):
        from .control import Guardian
        Guardian().admit(lease,max_evaluations,job.epoch,deadline)
        if lease.job_id!=job.job_id:raise ValueError('job/lease identity mismatch')
        if not self.ledger.is_current(job):raise ValueError('inactive or stale mining job')
        if weights is None:weights=[1]*self.lanes
        if len(weights)!=self.lanes:raise ValueError('lane weight dimension mismatch')
        bounded=NonceLease(lease.start,min(lease.stop,lease.start+max_evaluations),lease.job_id,lease.epoch);parts=bounded.partition(weights)
        expected_batches=sum((p.stop-p.start+self.batch_size-1)//self.batch_size for p in parts)
        if expected_batches>4096:raise ValueError('receipt/batch quota exceeded; raise batch_size or lower evaluation budget')
        def batches():
            # Interleave lane batches rather than front-loading one lane.
            cursors=[p.start for p in parts]
            while any(c<p.stop for c,p in zip(cursors,parts)):
                for lane,p in enumerate(parts):
                    if cursors[lane]<p.stop:
                        a=cursors[lane];b=min(p.stop,a+self.batch_size);cursors[lane]=b;yield lane,NonceLease(a,b,p.job_id,p.epoch)
        def current():return self.ledger.is_current(job)and not(stop_event and stop_event.is_set())and not(deadline is not None and time.perf_counter()>=deadline)
        started=time.perf_counter();submitted=0;rows=[];winner=None;tasks=iter(batches());pending={};peak=0
        def execute(lane,part):
            if not current():return None
            result=self.engine.scan_span(job,part,part.stop-part.start);return {'lane':lane,**result}
        with ThreadPoolExecutor(max_workers=self.lanes)as pool:
            exhausted=False
            while pending or not exhausted:
                while not exhausted and len(pending)<self.max_inflight and winner is None and current():
                    try:lane,part=next(tasks)
                    except StopIteration:exhausted=True;break
                    future=pool.submit(execute,lane,part);pending[future]=(lane,part);submitted+=1;peak=max(peak,len(pending))
                if not current()or winner is not None:exhausted=True
                if not pending:break
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    pending.pop(future);row=future.result()
                    if row is None:continue
                    if row['job_commitment']!=job.commitment:raise DispatchError('batch job custody mismatch')
                    rows.append(row)
                    if row['verified']and winner is None and current():winner=row
        # All already-dispatched work is collected and counted, even after a hit.
        active=self.ledger.is_current(job);stale=not active
        if stale:winner=None
        elapsed=time.perf_counter()-started;count=sum(x['sha256d_evaluations']for x in rows);verify=sum(x['verification_sha256d_evaluations']for x in rows)
        spans=sorted((x['lease']['start'],x['lease']['start']+x['sha256d_evaluations'])for x in rows)
        resume=bounded.start
        for a,b in spans:
            if a==resume:resume=b
            elif a>resume:break
        result={'schema':'chronos_mining_farm_v1','job':job.manifest(),'job_commitment':job.commitment,'backend':self.engine.capability()['backend'],'logical_device':'chronos_igpu','physical_asic':False,'lanes':self.lanes,'partitions':[asdict(p)for p in parts],'batches_submitted':submitted,'peak_inflight':peak,'batches':sorted(rows,key=lambda x:x['lease']['start']),'winner':winner,'stale':stale,'cancelled':bool(stop_event and stop_event.is_set()),'deadline_reached':bool(deadline is not None and time.perf_counter()>=deadline),'scan_sha256d_evaluations':count,'verification_sha256d_evaluations':verify,'elapsed_seconds':elapsed,'measured_hashrate':count/elapsed if elapsed else 0,'next_contiguous_nonce':resume,'bounded_stop':bounded.stop,'pool_accepted':None,'network_submitted':False}
        result['receipt_digest']=hashlib.sha256(canonical(result)).hexdigest();return result
    @staticmethod
    def verify_receipt(result):
        body=dict(result);digest=body.pop('receipt_digest')
        if hashlib.sha256(canonical(body)).hexdigest()!=digest:raise ValueError('mining farm receipt digest mismatch')
        job=MiningJob.from_manifest(body['job'])
        if body['job_commitment']!=job.commitment:raise ValueError('mining farm job identity mismatch')
        if sum(x['sha256d_evaluations']for x in body['batches'])!=body['scan_sha256d_evaluations']:raise ValueError('mining farm accounting mismatch')
        spans=[]
        for row in body['batches']:
            p=row['lease'];a=p['start'];b=a+row['sha256d_evaluations']
            if not a<=b<=p['stop']or row['job_commitment']!=job.commitment:raise ValueError('mining farm lease/custody violation')
            spans.append((a,b))
            if row['verified']:
                n=row['nonce'];d=Oracle.nonce_digest(job.header_prefix,n)
                if not a<=n<b or row['digest_hex']!=d.hex()or not Oracle.accepts(d,job.target):raise ValueError('mining farm proof mismatch')
        for prev,nxt in zip(sorted(spans),sorted(spans)[1:]):
            if prev[1]>nxt[0]:raise ValueError('overlapping executed nonce spans')
        if body['stale']and body['winner']is not None:raise ValueError('stale winner violation')
        return True
