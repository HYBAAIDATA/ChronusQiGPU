"""Bounded CPU tensor operations and guarded access to the shipped MPS engine.

tensor_operation computes in exact rational arithmetic (inputs are exact
dyadic values, so the arithmetic is lossless) and returns the certified
float64 projection; tensor_operation_exact exposes the exact result for
receipt-bound consumers. The FP64 numpy path is retained as
_tensor_operation_reference — explicitly non-production.
"""
import numpy as np
from fractions import Fraction
from ..academic.tensor_compression import MatrixProductState


def _to_exact(a):
    def conv(v):
        c = complex(v)
        return (Fraction(float(c.real)), Fraction(float(c.imag)))
    out = np.empty(a.shape, dtype=object)
    for idx in np.ndindex(a.shape):
        out[idx] = conv(a[idx])
    return out


def _mul(x, y):
    return (x[0] * y[0] - x[1] * y[1], x[0] * y[1] + x[1] * y[0])


def _exact_op(operation, a, b):
    if operation == 'matmul':
        n, k, m = a.shape[0], a.shape[1], b.shape[1]
        out = np.empty((n, m), dtype=object)
        for i in range(n):
            for j in range(m):
                acc = (Fraction(0), Fraction(0))
                for t in range(k):
                    acc = (acc[0] + _mul(a[i, t], b[t, j])[0],
                           acc[1] + _mul(a[i, t], b[t, j])[1])
                out[i, j] = acc
        return out
    if operation in {'add', 'hadamard'}:
        out = np.empty(a.shape, dtype=object)
        for idx in np.ndindex(a.shape):
            out[idx] = ((a[idx][0] + b[idx][0], a[idx][1] + b[idx][1]) if operation == 'add'
                        else _mul(a[idx], b[idx]))
        return out
    if operation == 'scale':
        out = np.empty(a.shape, dtype=object)
        for idx in np.ndindex(a.shape):
            out[idx] = _mul(a[idx], b[()])
        return out
    if operation == 'kron':
        ash, bsh = a.shape, b.shape
        if a.ndim == 1:
            a2 = np.empty((ash[0], 1), dtype=object)
            a2[:, 0] = a
        else:
            a2 = a
        if b.ndim == 1:
            b2 = np.empty((bsh[0], 1), dtype=object)
            b2[:, 0] = b
        else:
            b2 = b
        out = np.empty((a2.shape[0] * b2.shape[0], a2.shape[1] * b2.shape[1]), dtype=object)
        for i in range(a2.shape[0]):
            for j in range(a2.shape[1]):
                for p in range(b2.shape[0]):
                    for q in range(b2.shape[1]):
                        out[i * b2.shape[0] + p, j * b2.shape[1] + q] = _mul(a2[i, j], b2[p, q])
        if a.ndim == 1 and b.ndim == 1:
            out = out.reshape(-1)
        return out
    raise ValueError('unsupported tensor operation')


def tensor_operation_exact(operation, left, right=None):
    """Exact rational result of a bounded tensor operation.

    Returns the exact object array of (re, im) Fraction pairs; raises on the
    same contract violations as tensor_operation.
    """
    a = np.asarray(left)
    if a.size > 1000000 or not np.isfinite(a).all():
        raise ValueError('tensor input quota/nonfinite violation')
    b = np.asarray(right) if right is not None else None
    if b is not None and (b.size > 1000000 or not np.isfinite(b).all()):
        raise ValueError('tensor input quota/nonfinite violation')
    ae = _to_exact(a)
    be = _to_exact(b) if b is not None else None
    if operation == 'matmul':
        if be is None or ae.ndim != 2 or be.ndim != 2 or ae.shape[1] != be.shape[0] or ae.shape[0] * be.shape[1] > 1000000:
            raise ValueError('bounded compatible matrices required')
    elif operation in {'add', 'hadamard'}:
        if be is None or ae.shape != be.shape:
            raise ValueError('matching tensor shapes required')
    elif operation == 'scale':
        if be is None or be.ndim != 0:
            raise ValueError('scalar required')
    elif operation == 'kron':
        if be is None or not 1 <= ae.ndim <= 2 or not 1 <= be.ndim <= 2 or ae.size * be.size > 1000000:
            raise ValueError('bounded rank-1/2 Kronecker operands required')
    else:
        raise ValueError('unsupported tensor operation')
    return _exact_op(operation, ae, be)


def tensor_error_envelope(operation, left, right=None, unit=Fraction(1, 2 ** 52)):
    """Certified per-entry bound on |float_result - exact_result| for a
    tensor operation executed in floating point with machine epsilon `unit`
    (Fraction(1, 2**52) for FP64 pipelines, Fraction(1, 2**23) for FP32
    device pipelines). The envelope is derived from the inputs in exact
    arithmetic using the standard worst-case rounding bound for each op:

      * add/hadamard/scale/kron:  (4 + 16) * u * |term_i| + u * |exact_i|
        where |term_i| = |a_i| (add) or |a_i||b_j| (product ops)
      * matmul row entry i,j:     (4k + 16) * u * sum_t |a_it||b_tj|
                                  + u * |exact_ij|

    Returns (exact_result, tolerance) where exact_result is the exact
    (re, im) object array and tolerance is a same-shape Fraction array.
    Comparing |float(v) - exact| <= tolerance proves the float result is a
    correct bounded-precision rendering of the exact result; it is not a
    heuristic threshold.
    """
    exact = tensor_operation_exact(operation, left, right)
    a = np.asarray(left)
    ae = _to_exact(a)
    b = np.asarray(right) if right is not None else None
    be = _to_exact(b) if b is not None else None
    u = unit

    def mag(pair):
        return abs(pair[0]) + abs(pair[1])

    if operation == 'matmul':
        tol = np.empty(exact.shape, dtype=object)
        n, k, m = ae.shape[0], ae.shape[1], be.shape[1]
        row_terms = np.empty((n, m), dtype=object)
        for i in range(n):
            for j in range(m):
                acc = Fraction(0)
                for t in range(k):
                    acc += mag(ae[i, t]) * mag(be[t, j])
                row_terms[i, j] = acc
        for i in range(n):
            for j in range(m):
                tol[i, j] = (4 * k + 16) * u * row_terms[i, j] + u * mag(exact[i, j])
        return exact, tol
    if operation in {'add', 'hadamard', 'scale', 'kron'}:
        def term_mag(aij, bij):
            if operation == 'add':
                return mag(aij) + mag(bij)
            return mag(aij) * mag(bij)
        tol = np.empty(exact.shape, dtype=object)
        if operation == 'scale':
            bmag = mag(be[()])
            for idx in np.ndindex(exact.shape):
                tol[idx] = 20 * u * mag(ae[idx]) * bmag + u * mag(exact[idx])
        elif operation == 'kron':
            a2 = ae if ae.ndim == 2 else ae.reshape(-1, 1)
            b2 = be if be.ndim == 2 else be.reshape(-1, 1)
            tol = np.empty((a2.shape[0] * b2.shape[0], a2.shape[1] * b2.shape[1]), dtype=object)
            e2 = np.empty(tol.shape, dtype=object)
            for i in range(a2.shape[0]):
                for j in range(a2.shape[1]):
                    for p in range(b2.shape[0]):
                        for q in range(b2.shape[1]):
                            idx = (i * b2.shape[0] + p, j * b2.shape[1] + q)
                            e2[idx] = _mul(a2[i, j], b2[p, q])
                            tol[idx] = 20 * u * mag(a2[i, j]) * mag(b2[p, q]) + u * mag(e2[idx])
            if a.ndim == 1 and b.ndim == 1:
                e2 = e2.reshape(-1)
                tol = tol.reshape(-1)
            return e2, tol
        else:
            for idx in np.ndindex(exact.shape):
                tol[idx] = 20 * u * term_mag(ae[idx], be[idx]) + u * mag(exact[idx])
        return exact, tol
    raise ValueError('unsupported tensor operation')


def tensor_deviation_ok(operation, result, left, right=None, unit=Fraction(1, 2 ** 52)):
    """Certified host validation: True iff every entry of the floating
    `result` lies inside the tensor_error_envelope for the op at `unit`.
    Raises ValueError on contract violations (same as tensor_operation)."""
    r = np.asarray(result)
    exact, tol = tensor_error_envelope(operation, left, right, unit)
    if r.shape != exact.shape or not np.isfinite(r).all():
        raise ValueError('tensor result shape/finiteness violation')
    for idx in np.ndindex(exact.shape):
        re_, im_ = exact[idx]
        if abs(complex(r[idx]) - complex(float(re_), float(im_))) > float(tol[idx]):
            return False
    return True


def _tensor_operation_reference(operation, left, right=None):
    """FP64 numpy path — explicit non-production reference."""
    a = np.asarray(left)
    b = np.asarray(right) if right is not None else None
    if operation == 'matmul':
        return a @ b
    if operation in {'add', 'hadamard'}:
        return a + b if operation == 'add' else a * b
    if operation == 'scale':
        return a * b
    return np.kron(a, b)

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
    """Exact rational tensor operation, returned as a certified float64
    projection of the exact result (each entry is within 1 ulp of the exact
    value — the exact result is obtainable via tensor_operation_exact)."""
    exact = tensor_operation_exact(operation, left, right)
    result = np.empty(exact.shape, dtype=np.complex128)
    real_only = True
    for idx in np.ndindex(exact.shape):
        re_, im_ = exact[idx]
        result[idx] = complex(float(re_), float(im_))
        if im_ != 0:
            real_only = False
    if not np.isfinite(result).all(): raise ValueError('nonfinite tensor output')
    # Real-valued exact results keep the historical float64 dtype contract.
    if real_only:
        return result.real
    return result
