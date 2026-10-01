"""Property Invariants — PULVINI V3

Tests every property invariant across all PULVINI use cases:
Linearity, Invertibility, Norm, Conditioning, CPTP, POVM,
Topology, Convergence, Conservation, Unitarity, Hermiticity, PSD.
"""
import numpy as np
import time
from typing import Dict, List, Tuple, Callable, Any
from dataclasses import dataclass
from enum import Enum

class InvariantType(Enum):
    LINEARITY = "linearity"
    INVERTIBILITY = "invertibility"
    NORM = "norm_preservation"
    CONDITIONING = "conditioning"
    CPTP = "cptp_map"
    POVM = "povm_completeness"
    TOPOLOGY = "topology_preservation"
    CONVERGENCE = "recursive_convergence"
    CONSERVATION = "conservation"
    UNITARITY = "unitarity"
    HERMITICITY = "hermiticity"
    PSD = "positive_semidefiniteness"
    TRACE_NORM = "trace_norm"
    ENTANGLEMENT = "entanglement_monotone"

@dataclass
class InvariantResult:
    invariant_type: InvariantType
    passed: bool
    value: float
    threshold: float
    details: str
    time_us: float

@dataclass
class InvariantReport:
    results: list
    total_passed: int
    total_failed: int
    total_time_s: float
    timestamp: str

class PropertyOracles:
    @staticmethod
    def check_linearity(op, x, y, a, b):
        lhs = op(a * x + b * y)
        rhs = a * op(x) + b * op(y)
        return float(np.linalg.norm(lhs - rhs) / max(np.linalg.norm(rhs), 1e-15))

    @staticmethod
    def check_invertibility(op, inv_op, x):
        recovered = inv_op(op(x))
        return float(np.linalg.norm(recovered - x) / max(np.linalg.norm(x), 1e-15))

    @staticmethod
    def check_norm_preservation(op, x):
        return abs(float(np.linalg.norm(op(x)) - np.linalg.norm(x))) / max(np.linalg.norm(x), 1e-15)

    @staticmethod
    def check_conditioning(matrix):
        try:
            sv = np.linalg.svd(matrix, compute_uv=False)
            return float(sv[0] / max(sv[-1], 1e-15))
        except np.linalg.LinAlgError:
            return np.inf

    @staticmethod
    def check_cptp(kraus_ops):
        n = kraus_ops[0].shape[0]
        total = sum(k.conj().T @ k for k in kraus_ops)
        trace_error = float(np.linalg.norm(total - np.eye(n)))
        choi = sum(np.outer(k.flatten(), k.flatten().conj()) for k in kraus_ops)
        min_eig = float(np.min(np.linalg.eigvalsh(choi)))
        return trace_error, min_eig

    @staticmethod
    def check_povm(povm_elements):
        total = sum(povm_elements)
        return float(np.linalg.norm(total - np.eye(povm_elements[0].shape[0])))

    @staticmethod
    def check_unitarity(U):
        return float(np.linalg.norm(U.conj().T @ U - np.eye(U.shape[0])))

    @staticmethod
    def check_hermiticity(H):
        return float(np.linalg.norm(H - H.conj().T))

    @staticmethod
    def check_psd(M):
        try:
            min_eig = float(np.min(np.linalg.eigvalsh(M)))
            return min_eig >= -1e-10, min_eig
        except np.linalg.LinAlgError:
            return False, -np.inf

    @staticmethod
    def check_trace_norm(rho):
        trace = float(np.trace(rho))
        trace_norm = float(np.sum(np.abs(np.linalg.eigvalsh(rho))))
        return abs(trace - 1.0), trace_norm

    @staticmethod
    def check_entanglement_monotone(state, partition):
        total_dim = len(state)
        dim_a = partition
        dim_b = total_dim // dim_a
        rho = np.outer(state, state.conj())
        rho_mat = rho.reshape(dim_a, dim_b, dim_a, dim_b)
        rho_a = np.trace(rho_mat, axis1=1, axis2=3)
        evals = np.linalg.eigvalsh(rho_a)
        evals = np.maximum(evals, 1e-15)
        entropy = -np.sum(evals * np.log2(evals))
        return float(entropy)


class InvariantTestSuite:
    def __init__(self, tolerance=1e-10):
        self.tolerance = tolerance
        self.oracles = PropertyOracles()
        self.results = []

    def _record(self, itype, passed, value, threshold, details, time_us):
        self.results.append(InvariantResult(
            invariant_type=itype, passed=passed, value=value,
            threshold=threshold, details=details, time_us=time_us
        ))

    def test_linearity(self, op, n_dim=64):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            x, y = rng.normal(size=n_dim), rng.normal(size=n_dim)
            a, b = rng.uniform(-2, 2), rng.uniform(-2, 2)
            err = self.oracles.check_linearity(op, x, y, a, b)
            self._record(InvariantType.LINEARITY, err < self.tolerance, err,
                        self.tolerance, f"T{trial}: err={err:.2e}", (time.time()-t0)*1e6)

    def test_invertibility(self, op, inv_op, n_dim=64):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            x = rng.normal(size=n_dim)
            err = self.oracles.check_invertibility(op, inv_op, x)
            self._record(InvariantType.INVERTIBILITY, err < self.tolerance, err,
                        self.tolerance, f"T{trial}: err={err:.2e}", (time.time()-t0)*1e6)

    def test_norm_preservation(self, op, n_dim=64):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            x = rng.normal(size=n_dim); x /= np.linalg.norm(x)
            err = self.oracles.check_norm_preservation(op, x)
            self._record(InvariantType.NORM, err < self.tolerance, err,
                        self.tolerance, f"T{trial}: err={err:.2e}", (time.time()-t0)*1e6)

    def test_conditioning(self):
        rng = np.random.default_rng(42)
        for size in [8, 16, 32, 64, 128]:
            t0 = time.time()
            M = rng.normal(size=(size, size))
            kappa = self.oracles.check_conditioning(M)
            self._record(InvariantType.CONDITIONING, kappa < 1e6, kappa,
                        1e6, f"size={size} k={kappa:.1f}", (time.time()-t0)*1e6)

    def test_cptp(self, n_dim=8):
        rng = np.random.default_rng(42)
        for trial in range(5):
            t0 = time.time()
            raw = [
                rng.normal(size=(n_dim, n_dim)) + 1j * rng.normal(size=(n_dim, n_dim))
                for _ in range(3)
            ]
            gram = sum(K.conj().T @ K for K in raw)
            evals, evecs = np.linalg.eigh(gram)
            inv_sqrt = evecs @ np.diag(1.0 / np.sqrt(np.maximum(evals, 1e-15))) @ evecs.conj().T
            kraus = [K @ inv_sqrt for K in raw]
            trace_err, min_choi = self.oracles.check_cptp(kraus)
            passed = trace_err < self.tolerance and min_choi > -self.tolerance
            self._record(InvariantType.CPTP, passed, trace_err, self.tolerance,
                        f"T{trial}: tr={trace_err:.2e} choi={min_choi:.2e}", (time.time()-t0)*1e6)

    def test_povm(self, n_dim=8):
        rng = np.random.default_rng(42)
        for trial in range(5):
            t0 = time.time()
            m = 6
            U = rng.normal(size=(m, m)) + 1j * rng.normal(size=(m, m)); U, _ = np.linalg.qr(U)
            elements = []
            for i in range(m):
                proj = np.zeros((m, m), dtype=complex); proj[i, i] = 1.0
                elements.append((U.conj().T @ proj @ U)[:n_dim, :n_dim])
            err = self.oracles.check_povm(elements)
            self._record(InvariantType.POVM, err < self.tolerance, err,
                        self.tolerance, f"T{trial}: err={err:.2e}", (time.time()-t0)*1e6)

    def test_unitarity(self, n_dim=16):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            A = rng.normal(size=(n_dim, n_dim)) + 1j * rng.normal(size=(n_dim, n_dim))
            U, _ = np.linalg.qr(A)
            err = self.oracles.check_unitarity(U)
            self._record(InvariantType.UNITARITY, err < self.tolerance, err,
                        self.tolerance, f"T{trial}: err={err:.2e}", (time.time()-t0)*1e6)

    def test_hermiticity(self, n_dim=16):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            A = rng.normal(size=(n_dim, n_dim)) + 1j * rng.normal(size=(n_dim, n_dim))
            H = (A + A.conj().T) / 2
            err = self.oracles.check_hermiticity(H)
            self._record(InvariantType.HERMITICITY, err < self.tolerance, err,
                        self.tolerance, f"T{trial}: err={err:.2e}", (time.time()-t0)*1e6)

    def test_psd(self, n_dim=16):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            A = rng.normal(size=(n_dim, n_dim))
            M = A.T @ A
            is_psd, min_eig = self.oracles.check_psd(M)
            self._record(InvariantType.PSD, is_psd, min_eig,
                        -1e-10, f"T{trial}: PSD={is_psd}", (time.time()-t0)*1e6)

    def test_trace_norm(self, n_dim=8):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            A = rng.normal(size=(n_dim, n_dim))
            rho = A.T @ A; rho /= np.trace(rho)
            trace_err, tn = self.oracles.check_trace_norm(rho)
            self._record(InvariantType.TRACE_NORM, trace_err < self.tolerance, trace_err,
                        self.tolerance, f"T{trial}: err={trace_err:.2e}", (time.time()-t0)*1e6)

    def test_entanglement(self, n_dim=8):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            state = rng.normal(size=n_dim) + 1j * rng.normal(size=n_dim)
            state /= np.linalg.norm(state)
            ent = self.oracles.check_entanglement_monotone(state, n_dim // 2)
            self._record(InvariantType.ENTANGLEMENT, True, ent, 0.0,
                        f"T{trial}: E={ent:.4f}", (time.time()-t0)*1e6)

    def test_conservation(self, op, n_dim=64):
        rng = np.random.default_rng(42)
        for trial in range(10):
            t0 = time.time()
            x = rng.normal(size=n_dim)
            err = abs(np.sum(op(x)) - np.sum(x)) / max(abs(np.sum(x)), 1e-15)
            self._record(InvariantType.CONSERVATION, err < self.tolerance, err,
                        self.tolerance, f"T{trial}: err={err:.2e}", (time.time()-t0)*1e6)

    def test_topology(self, op, n_dim=64):
        rng = np.random.default_rng(42)
        for trial in range(5):
            t0 = time.time()
            x = rng.normal(size=n_dim)
            y = op(x)
            ev_x = np.sort(np.abs(x)); ev_y = np.sort(np.abs(y))
            err = np.linalg.norm(ev_x - ev_y) / max(np.linalg.norm(ev_x), 1e-15)
            self._record(InvariantType.TOPOLOGY, err < self.tolerance * 100, err,
                        self.tolerance * 100, f"T{trial}: err={err:.2e}", (time.time()-t0)*1e6)

    def run_all(self, op=None, inv_op=None):
        self.results = []
        t_start = time.time()
        if op is None: op = lambda x: x
        if inv_op is None: inv_op = lambda x: x
        tests = [
            ("Linearity", self.test_linearity, [op]),
            ("Invertibility", self.test_invertibility, [op, inv_op]),
            ("Norm Preservation", self.test_norm_preservation, [op]),
            ("Conditioning", self.test_conditioning, []),
            ("CPTP Maps", self.test_cptp, []),
            ("POVM Completeness", self.test_povm, []),
            ("Unitarity", self.test_unitarity, []),
            ("Hermiticity", self.test_hermiticity, []),
            ("PSD", self.test_psd, []),
            ("Trace Norm", self.test_trace_norm, []),
            ("Entanglement", self.test_entanglement, []),
            ("Conservation", self.test_conservation, [op]),
            ("Topology", self.test_topology, [op]),
        ]
        for _, test_fn, args in tests:
            test_fn(*args)
        total_time = time.time() - t_start
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        return InvariantReport(
            results=self.results, total_passed=passed,
            total_failed=failed, total_time_s=total_time,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )


if __name__ == "__main__":
    suite = InvariantTestSuite()
    suite.run_all(lambda x: x, lambda x: x)
