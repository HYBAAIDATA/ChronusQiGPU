"""Bounded reuse of an identical deterministic advisory Hamiltonian.

Caches positional eigenvector ordering only, never job identities or nonces.
The dense Chronos engine remains the solver and original source authority.
"""
from collections import OrderedDict
import hashlib
import threading
import numpy as np
from ..engine import ChronosEngine

class DeterministicSolverCache:
    SPEC = 'chronos_advisory_ground_state_v1'
    def __init__(self, entries=8, enabled=True):
        if type(entries) is not int or not 1 <= entries <= 32:raise ValueError('bounded solver cache required')
        self.entries=entries;self.enabled=bool(enabled);self._lock=threading.RLock();self._cache=OrderedDict();self.hits=0;self.solves=0
    def rank(self, amplitudes, phi):
        a=np.asarray(amplitudes,dtype=np.complex128)
        if a.ndim!=1 or not 1<=len(a)<=128 or not np.isfinite(a).all() or not np.isfinite(phi) or phi<=0:raise ValueError('finite bounded advisory state required')
        a=np.array(a,dtype='<c16',copy=True);n=len(a)
        key=hashlib.sha256(self.SPEC.encode()+n.to_bytes(2,'little')+np.float64(phi).tobytes()+a.tobytes()).hexdigest()
        with self._lock:
            if self.enabled and key in self._cache:
                self.hits+=1;entry=self._cache.pop(key);self._cache[key]=entry
                return entry['order'],dict(entry['evidence'],cache_hit=True)
            h=np.diag(np.linspace(0,1,n));h-=np.real(np.outer(a,a.conj()))
            if n>1:h+=np.diag(np.full(n-1,-1/phi),1)+np.diag(np.full(n-1,-1/phi),-1)
            v=ChronosEngine().evolve(h);norm=float(np.linalg.norm(v));value=float(np.vdot(v,h@v).real);residual=float(np.linalg.norm(h@v-value*v))
            if not np.isfinite(v).all() or abs(norm-1)>1e-10 or residual>1e-10*max(1,float(np.linalg.norm(h))):raise ValueError('advisory eigenvector validation failed')
            order=tuple(int(i)for i in np.argsort(-np.abs(v)**2,kind='stable'))
            assert sorted(order)==list(range(n))
            evidence={'spec':self.SPEC,'input_digest':key,'dimension':n,'eigenvalue':value,'residual':residual,'vector_norm':norm,'solver':'original_ChronosEngine_dense','cache_hit':False}
            self.solves+=1
            if self.enabled:
                self._cache[key]={'order':order,'evidence':evidence}
                while len(self._cache)>self.entries:self._cache.popitem(last=False)
            return order,dict(evidence)
    def stats(self):
        with self._lock:return {'enabled':self.enabled,'entries':len(self._cache),'entry_limit':self.entries,'hits':self.hits,'solves':self.solves,'cached_nonce_count':0}
    def clear(self):
        with self._lock:self._cache.clear()
