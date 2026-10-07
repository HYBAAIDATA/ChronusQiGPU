"""Budgeted classical search and honest bounded Grover simulation."""
from dataclasses import dataclass
import math
import numpy as np
from .constants import GoldenConstants
from .quantum_state import MathematicalQuantumState
@dataclass(frozen=True)
class SearchResult:
    candidate: object
    success: bool
    evaluations: int
    oracle_calls: int
    amplitudes: tuple = ()
    backend: str = "cpu_reference"
class MathematicalQuantumSearchEngine:
    def search(self, candidates, predicate, max_evaluations=4096):
        if type(max_evaluations) is not int or not 0 <= max_evaluations <= 65536: raise ValueError("bounded evaluation budget required")
        import itertools
        for i, candidate in enumerate(itertools.islice(candidates, max_evaluations), 1):
            if predicate(candidate): return SearchResult(candidate, True, i, i)
        return SearchResult(None, False, i if 'i' in locals() else 0, i if 'i' in locals() else 0)
    def simulate_grover(self, size, oracle, iterations=1, phase=math.pi):
        if type(size) is not int or not 1 <= size <= 4096 or type(iterations) is not int or not 0 <= iterations <= 64 or not math.isfinite(phase):
            raise ValueError("bounded simulation required")
        # Evaluating the complete oracle mask on a CPU is O(N) work and is counted.
        marked = np.array([bool(oracle(i)) for i in range(size)])
        a = np.full(size, 1/math.sqrt(size), dtype=np.complex128)
        for _ in range(iterations):
            a[marked] *= np.exp(1j*phase)
            a = 2*a.mean()-a
        state = MathematicalQuantumState(a)
        candidate = int(np.argmax(state.probabilities))
        return SearchResult(candidate if marked[candidate] else None, bool(marked[candidate]), size, size,
                            tuple(complex(x) for x in state.amplitudes))
class GoldenQuantumComputer(MathematicalQuantumSearchEngine):
    def prioritize(self, candidates):
        values = list(candidates)
        # Finite golden-angle ordering only, never a claim of a cryptographic solve.
        return sorted(values, key=lambda n: ((n/GoldenConstants().phi**2) % 1, n))

def _golden_feedback(self,size,oracle,iterations=4):
    if type(size)is not int or not 1<=size<=4096 or type(iterations)is not int or not 1<=iterations<=64:raise ValueError('bounded golden phase search required')
    marked=np.array([bool(oracle(i))for i in range(size)]);a=np.full(size,1/math.sqrt(size),dtype=np.complex128)
    angle=GoldenConstants().golden_angle
    for step in range(iterations):
        marked_probability=float(np.sum(np.abs(a[marked])**2))
        feedback=(1-marked_probability)*math.sin((step+1)*angle)/GoldenConstants().phi
        a[marked]*=np.exp(1j*(math.pi+feedback));a=2*a.mean()-a
        if abs(float(np.vdot(a,a).real)-1)>1e-10:raise ValueError('phase feedback norm invariant failed')
    indices=np.flatnonzero(marked)
    candidate=int(indices[np.argmax(np.abs(a[indices])**2)])if len(indices)else None
    return SearchResult(candidate,candidate is not None,size,size,tuple(complex(x)for x in a))
GoldenQuantumComputer.simulate_golden_feedback=_golden_feedback
