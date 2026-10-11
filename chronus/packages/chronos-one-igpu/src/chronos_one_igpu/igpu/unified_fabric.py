"""Actual bounded host shared memory and logical-pad FIFO transport.

This is intra-host software execution, not Apple UltraFusion/RDMA/optical
hardware or a 4.4 TB/s claim. Read leases pin immutable content; workers handle
real descriptor messages and independently verify the shared payload digest.
"""
from collections import OrderedDict
from concurrent.futures import Future
from contextlib import contextmanager
import hashlib
import json
from multiprocessing import shared_memory
import queue
import threading
import time
from .resident import canonical
from .feature_profile import FeatureProfile


class UnifiedArena:
    def __init__(self,max_bytes=16*1024*1024,max_blocks=128):
        if type(max_bytes)is not int or not 1024<=max_bytes<=1024**3 or type(max_blocks)is not int or not 1<=max_blocks<=4096:
            raise ValueError('bounded host shared-memory policy required')
        self.max_bytes=max_bytes;self.max_blocks=max_blocks;self.blocks=OrderedDict();self.used=0;self.lock=threading.RLock();self.closed=False

    def _evict(self,needed):
        for key in list(self.blocks):
            if self.used+needed<=self.max_bytes and len(self.blocks)<self.max_blocks:break
            row=self.blocks[key]
            if row['leases']:continue
            self.blocks.pop(key);self.used-=row['allocated'];row['memory'].close();row['memory'].unlink()
        if self.used+needed>self.max_bytes or len(self.blocks)>=self.max_blocks:
            raise MemoryError('pinned unified memory/backpressure quota')

    def put(self,payload):
        if not isinstance(payload,bytes)or len(payload)>self.max_bytes:raise ValueError('bounded bytes required')
        key=hashlib.sha256(payload).hexdigest()
        with self.lock:
            if self.closed:raise RuntimeError('arena closed')
            if key in self.blocks:
                self.blocks.move_to_end(key);return dict(self.blocks[key]['handle'])
            allocated=max(1,len(payload));self._evict(allocated)
            memory=shared_memory.SharedMemory(create=True,size=allocated)
            try:memory.buf[:len(payload)]=payload
            except BaseException:memory.close();memory.unlink();raise
            handle={'sha256':key,'size':len(payload),'shared_memory':memory.name,'schema':'chronos.shared_block/1'}
            self.blocks[key]={'memory':memory,'handle':handle,'allocated':allocated,'leases':0};self.used+=allocated
            return dict(handle)

    @contextmanager
    def borrow(self,handle):
        with self.lock:
            if self.closed:raise RuntimeError('arena closed')
            if not isinstance(handle,dict)or handle.get('sha256')not in self.blocks:raise KeyError('unknown arena block')
            row=self.blocks[handle['sha256']]
            if handle!=row['handle']:raise ValueError('shared memory identity mismatch')
            row['leases']+=1;self.blocks.move_to_end(handle['sha256'])
            view=row['memory'].buf[:handle['size']].toreadonly()
        try:
            if hashlib.sha256(view).hexdigest()!=handle['sha256']:raise ValueError('shared payload corrupted')
            yield view
            if hashlib.sha256(view).hexdigest()!=handle['sha256']:raise ValueError('shared payload mutated during lease')
        finally:
            view.release()
            with self.lock:row['leases']-=1

    def inventory(self):
        with self.lock:
            return {'backend':'os_shared_memory','allocated_bytes':self.used,'configured_budget_bytes':self.max_bytes,
                    'blocks':len(self.blocks),'active_leases':sum(r['leases']for r in self.blocks.values()),
                    'gpu_zero_copy_qualified':False,'physical_bandwidth_bytes_per_second':None}

    def close(self):
        with self.lock:
            if self.closed:return
            if any(r['leases']for r in self.blocks.values()):raise RuntimeError('release shared-memory leases before close')
            for row in self.blocks.values():row['memory'].close();row['memory'].unlink()
            self.blocks.clear();self.used=0;self.closed=True


class LocalPadTransport:
    def __init__(self,profile,arena,max_inflight=4,max_records=128):
        if not isinstance(profile,FeatureProfile)or not isinstance(arena,UnifiedArena):raise TypeError('real profile and shared arena required')
        if type(max_inflight)is not int or not 1<=max_inflight<=32 or type(max_records)is not int or not 1<=max_records<=4096:raise ValueError('transport quotas')
        self.profile=profile;self.arena=arena;self.max_records=max_records;self.limit=threading.BoundedSemaphore(max_inflight)
        self.queues=[queue.Queue(maxsize=max_inflight)for _ in profile.pad_qubits];self.records={};self.lock=threading.RLock();self.idle=threading.Condition(self.lock);self.active=0;self.closed=False
        self.threads=[threading.Thread(target=self._worker,args=(i,),name=f'chronos-pad-{i}',daemon=True)for i in range(len(self.queues))]
        for worker in self.threads:worker.start()

    def route(self,source,target):
        n=len(self.profile.pad_qubits)
        if any(type(v)is not int or not 0<=v<n for v in(source,target)):raise ValueError('logical endpoint required')
        adjacency=[[]for _ in range(n)]
        for a,b in self.profile.edges:adjacency[a].append(b);adjacency[b].append(a)
        paths=queue.Queue();paths.put((source,));seen={source}
        while not paths.empty():
            path=paths.get();last=path[-1]
            if last==target:return path
            for nxt in sorted(adjacency[last]):
                if nxt not in seen:seen.add(nxt);paths.put(path+(nxt,))
        raise ValueError('no authorised logical fabric path')

    def _worker(self,pad):
        while True:
            item=self.queues[pad].get()
            if item is None:self.queues[pad].task_done();return
            descriptor,future=item
            try:
                if descriptor['pad']!=pad or descriptor['profile_digest']!=self.profile.digest:raise ValueError('pad message identity mismatch')
                with self.arena.borrow(descriptor['handle'])as view:
                    verified=hashlib.sha256(view).hexdigest()
                body={'pad':pad,'message_digest':hashlib.sha256(canonical(descriptor)).hexdigest(),'payload_digest':verified,
                      'executor':'local_pad_worker','physical_interdie_transfer':False}
                body['digest']=hashlib.sha256(canonical(body)).hexdigest();future.set_result(body)
            except BaseException as exc:future.set_exception(exc)
            finally:self.queues[pad].task_done()

    def transfer(self,handle,source,target,workload_id,tenant='default',timeout=10):
        if not isinstance(workload_id,str)or not 1<=len(workload_id)<=128 or not isinstance(tenant,str)or not 1<=len(tenant)<=128 or type(timeout)not in(int,float)or not 0<timeout<=60:raise ValueError('bounded transport identity/timeout')
        route=self.route(source,target)
        request={'handle':dict(handle),'route':list(route),'profile_digest':self.profile.digest,'workload_id':workload_id,'tenant':tenant}
        request_digest=hashlib.sha256(canonical(request)).hexdigest();identity=(tenant,workload_id)
        with self.lock:
            if self.closed:raise RuntimeError('transport closed')
            if identity in self.records:
                old=self.records[identity]
                if old['request_digest']!=request_digest:raise ValueError('workload identity reused with different transfer')
                record=old['future'];owner=False
            else:
                if len(self.records)>=self.max_records:raise RuntimeError('transport retry-ledger quota')
                record=Future();self.records[identity]={'request_digest':request_digest,'future':record};self.active+=1;owner=True
        if not owner:return json.loads(record.result(timeout=timeout))
        started=time.perf_counter();deadline=started+timeout;acquired=False
        try:
            acquired=self.limit.acquire(timeout=timeout)
            if not acquired:raise TimeoutError('transport admission deadline')
            hops=[];descriptor_bytes=0
            # A read lease pins this actual shared segment through every hop.
            with self.arena.borrow(handle):
                for sequence,pad in enumerate(route):
                    message={'pad':pad,'sequence':sequence,'handle':dict(handle),'profile_digest':self.profile.digest,'workload_id':workload_id,'tenant':tenant}
                    future=Future();remaining=deadline-time.perf_counter()
                    if remaining<=0:raise TimeoutError('transport deadline')
                    self.queues[pad].put((message,future),timeout=remaining)
                    hop=future.result(timeout=max(0,deadline-time.perf_counter()))
                    if hop['payload_digest']!=handle['sha256']:raise ValueError('transport payload mismatch')
                    descriptor_bytes+=len(canonical(message));hops.append(hop)
            result={'schema':'chronos.local_pad_transfer/1','request':request,'request_digest':request_digest,'hops':hops,
                    'payload_bytes':handle['size'],'payload_bytes_copied_between_pads':0,'descriptor_bytes_sent':descriptor_bytes,
                    'backend':'host_shared_memory_fifo','physical_network_bytes':None,'elapsed_seconds':time.perf_counter()-started}
            result['receipt_digest']=hashlib.sha256(canonical(result)).hexdigest();self.verify(result,handle,source,target,workload_id,tenant)
            encoded=canonical(result);record.set_result(encoded);return json.loads(encoded)
        except BaseException as exc:record.set_exception(RuntimeError('transfer failed; reconcile before a new workload ID: '+type(exc).__name__));raise
        finally:
            if acquired:self.limit.release()
            with self.idle:self.active-=1;self.idle.notify_all()

    def verify(self,result,handle,source,target,workload_id,tenant='default'):
        request={'handle':dict(handle),'route':list(self.route(source,target)),'profile_digest':self.profile.digest,'workload_id':workload_id,'tenant':tenant}
        body=dict(result);seal=body.pop('receipt_digest')
        if hashlib.sha256(canonical(body)).hexdigest()!=seal or result['request']!=request or result['request_digest']!=hashlib.sha256(canonical(request)).hexdigest():raise ValueError('transport request/custody mismatch')
        if len(result['hops'])!=len(request['route'])or result['backend']!='host_shared_memory_fifo'or result['physical_network_bytes']is not None or result['payload_bytes']!=handle['size']or result['payload_bytes_copied_between_pads']!=0:raise ValueError('transport work/substrate mismatch')
        for sequence,(pad,hop)in enumerate(zip(request['route'],result['hops'])):
            descriptor={'pad':pad,'sequence':sequence,'handle':dict(handle),'profile_digest':self.profile.digest,'workload_id':workload_id,'tenant':tenant}
            expected={'pad':pad,'message_digest':hashlib.sha256(canonical(descriptor)).hexdigest(),'payload_digest':handle['sha256'],
                      'executor':'local_pad_worker','physical_interdie_transfer':False}
            expected['digest']=hashlib.sha256(canonical(expected)).hexdigest()
            if hop!=expected:raise ValueError('logical hop identity mismatch')
        return True

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True
            while self.active:self.idle.wait()
        # Settle queues before closing the shared arena. No abandoned worker.
        for q in self.queues:q.join();q.put(None)
        for thread in self.threads:thread.join()
