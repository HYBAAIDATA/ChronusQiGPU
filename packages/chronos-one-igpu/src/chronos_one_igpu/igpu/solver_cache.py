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
        self.entries=entries;self.enabled=bool(enabled);self._lock=threading.RLock();self._cache=OrderedDict();self.hits=0;self.solves=0;self.mode="auto"
    def rank(self, amplitudes, phi):
        a=np.asarray(amplitudes,dtype=np.complex128)
        if a.ndim!=1 or not 1<=len(a)<=128 or not np.isfinite(a).all() or not np.isfinite(phi) or phi<=0:raise ValueError('finite bounded advisory state required')
        a=np.array(a,dtype='<c16',copy=True);n=len(a)
        key=hashlib.sha256(self.SPEC.encode()+self.mode.encode()+n.to_bytes(2,'little')+np.float64(phi).tobytes()+a.tobytes()).hexdigest()
        with self._lock:
            if self.enabled and key in self._cache:
                self.hits+=1;entry=self._cache.pop(key);self._cache[key]=entry
                return entry['order'],dict(entry['evidence'],cache_hit=True)
            from .structured_solver import StructuredHamiltonian,_structured_native
            operator=StructuredHamiltonian(a,phi);fallback_reason=None
            use_structured=self.mode=="structured" or(self.mode=="auto" and _structured_native is not None and n>=32)
            if use_structured:
                try:
                    result=operator.ground();v=result.vector;meta=dict(result.evidence)
                    probabilities=np.abs(v)**2
                    spacing=float(np.min(np.diff(np.sort(probabilities))))if n>1 else 1.0
                    error=meta["residual"]/max(meta["gap_lower"]-meta["residual"],1e-30)
                    if spacing<=max(8*error,2e-14):raise ArithmeticError("positional ordering numerically ambiguous")
                except (ArithmeticError,RuntimeError,ValueError)as exc:
                    fallback_reason=str(exc);result=operator.ground("dense");v=result.vector;meta=dict(result.evidence)
            else:
                result=operator.ground("dense");v=result.vector;meta=dict(result.evidence)
            order=tuple(int(i)for i in np.argsort(-np.abs(v)**2,kind="stable"))
            if sorted(order)!=list(range(n)):raise ValueError("invalid solver permutation")
            evidence={"spec":self.SPEC,"input_digest":key,**meta,"solver":meta["backend"],"cache_hit":False,"structured_requested":use_structured,"dense_fallback_reason":fallback_reason}
            self.solves+=1
            if self.enabled:
                self._cache[key]={'order':order,'evidence':evidence}
                while len(self._cache)>self.entries:self._cache.popitem(last=False)
            return order,dict(evidence)
    def stats(self):
        with self._lock:return {'enabled':self.enabled,'entries':len(self._cache),'entry_limit':self.entries,'hits':self.hits,'solves':self.solves,'cached_nonce_count':0}
    def clear(self):
        with self._lock:self._cache.clear()

    def set_mode(self,mode):
        if mode not in ("auto","dense","structured"):raise ValueError("unknown solver mode")
        with self._lock:self.mode=mode;self._cache.clear()
