"""Bounded CPU tensor operations and guarded access to the shipped MPS engine."""
import numpy as np
from ..academic.tensor_compression import MatrixProductState

class SafeMatrixProductState(MatrixProductState):
    def __init__(self, n_qubits, bond_dim=16, max_bytes=64*1024*1024, allow_lossy=False):
        if type(n_qubits) is not int or type(bond_dim) is not int or not 1 <= n_qubits <= 10000 or not 1 <= bond_dim <= 256:
            raise ValueError('bounded positive MPS dimensions required')
        estimate = n_qubits * 2 * bond_dim**2 * 16
        if estimate > max_bytes: raise MemoryError('MPS worst-case memory quota exceeded')
        super().__init__(n_qubits, bond_dim)
        self.allow_lossy = allow_lossy
    def _gate(self, site, gate, width, paired=False):
        limit = self.n-1 if paired else self.n
        if type(site) is not int or not 0 <= site < limit: raise ValueError('invalid MPS site')
        g = np.asarray(gate, dtype=np.complex128)
        if g.shape != (width,width) or not np.isfinite(g).all() or not np.allclose(g.conj().T@g,np.eye(width),atol=1e-12,rtol=1e-12):
            raise ValueError('finite unitary gate required')
        return g
    def apply_single_qubit_gate(self, site, gate):
        super().apply_single_qubit_gate(site, self._gate(site,gate,2))
    def apply_two_qubit_gate(self, site, gate):
        g = self._gate(site,gate,4,True)
        saved_left = self.tensors[site].copy(); saved_right = self.tensors[site+1].copy()
        saved_bond = self.bond_singular_values.get(site+1)
        error = super().apply_two_qubit_gate(site,g)
        if error > 1e-14 and not self.allow_lossy:
            self.tensors[site] = saved_left; self.tensors[site+1] = saved_right
            if saved_bond is None: self.bond_singular_values.pop(site+1,None)
            else: self.bond_singular_values[site+1] = saved_bond
            raise ValueError('lossy MPS truncation requires explicit allow_lossy=True')
        return error
    def memory_bytes(self): return sum(t.nbytes for t in self.tensors)


def tensor_operation(operation, left, right=None):
    a = np.asarray(left)
    if a.size > 1000000 or not np.isfinite(a).all(): raise ValueError('tensor input quota/nonfinite violation')
    b = np.asarray(right) if right is not None else None
    if b is not None and (b.size > 1000000 or not np.isfinite(b).all()): raise ValueError('tensor input quota/nonfinite violation')
    if operation == 'matmul':
        if b is None or a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[0] or a.shape[0]*b.shape[1] > 1000000:
            raise ValueError('bounded compatible matrices required')
        result = a @ b
    elif operation in {'add','hadamard'}:
        if b is None or a.shape != b.shape: raise ValueError('matching tensor shapes required')
        result = a+b if operation == 'add' else a*b
    elif operation == 'scale':
        if b is None or b.ndim != 0: raise ValueError('scalar required')
        result = a*b
    elif operation == 'kron':
        if b is None or not 1 <= a.ndim <= 2 or not 1 <= b.ndim <= 2 or a.size*b.size > 1000000: raise ValueError('bounded rank-1/2 Kronecker operands required')
        result = np.kron(a,b)
    else: raise ValueError('unsupported tensor operation')
    if not np.isfinite(result).all(): raise ValueError('nonfinite tensor output')
    return result
