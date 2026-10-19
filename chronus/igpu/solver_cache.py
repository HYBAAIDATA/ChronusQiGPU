"""Bounded reuse of an identical deterministic advisory Hamiltonian.

Caches positional eigenvector ordering only, never job identities or nonces.
In 'auto' and 'structured' modes the ordering is produced by the certified
exact-arithmetic solver (igpu.exact_solver); a certified request never falls
back to an uncertified backend — certification failure raises. mode='dense'
is an explicitly named non-production reference path only.
"""
from collections import OrderedDict
import hashlib
import threading
import numpy as np
from ..v33.engine import ChronosEngine

class DeterministicSolverCache:
    SPEC = 'chronos_advisory_ground_state_v2_certified'
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
            from .structured_solver import StructuredHamiltonian
            operator=StructuredHamiltonian(a,phi)
            use_structured=self.mode in ("structured","auto")
            if use_structured:
                try:
                    result=operator.ground("certified");v=result.vector;meta=dict(result.evidence)
                    probabilities=np.abs(v)**2
                    spacing=float(np.min(np.diff(np.sort(probabilities))))if n>1 else 1.0
                    _gap=meta.get("gap_lower")
                    error=meta["residual"]/max(_gap-meta["residual"],1e-30)if _gap is not None else 0.0
                    if spacing<=max(8*error,2e-14):raise ArithmeticError("positional ordering numerically ambiguous")
                except (ArithmeticError,RuntimeError,ValueError)as exc:
                    raise ArithmeticError(
                        "certified solver ordering unavailable; failing "
                        f"closed (dense reference fallback is not "
                        f"authorised): {exc}") from exc
            else:
                result=operator.ground("dense");v=result.vector;meta=dict(result.evidence)
            order=tuple(int(i)for i in np.argsort(-np.abs(v)**2,kind="stable"))
            if sorted(order)!=list(range(n)):raise ValueError("invalid solver permutation")
            evidence={"spec":self.SPEC,"input_digest":key,**meta,"solver":meta["backend"],"cache_hit":False,"structured_requested":use_structured,"fallback_used":not use_structured,"fallback_reason":None if use_structured else "explicit non-production dense reference mode"}
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
