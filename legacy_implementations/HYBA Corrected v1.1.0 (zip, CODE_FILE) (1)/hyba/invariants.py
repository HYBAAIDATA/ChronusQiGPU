"""
HYBA Invariants — Mathematical Guarantees (Corrected)
Uses corrected cassini_integrity_check with full structural validation.
"""

from typing import Dict, Any, List, Tuple
import math
from python_backend.hyba.core import HYBACore


class HYBAInvariants:
    """
    HYBA Mathematical Invariants

    Provides verification of:
    - Cassini: det(M_φ^n) = (-1)^n
    - Volume preservation: |det(M_φ^n)| = 1
    - Pisot: |φ^n - L_n| = |ψ^n|
    - Binet: F(n) = (φ^n - ψ^n)/√5
    - Matrix: M_φ^a · M_φ^b = M_φ^(a+b)
    - Integrity: cassini_integrity_check rejects impostors
    """

    def __init__(self):
        self._core = HYBACore()
        self._phi = (1 + math.sqrt(5)) / 2
        self._psi = (1 - math.sqrt(5)) / 2

    def verify_cassini(self, n_max: int = 100) -> Dict[str, Any]:
        results = {'passed': True, 'failures': []}
        for n in range(1, n_max + 1):
            det = self._core.matrix_det(self._core.matrix_power(n))
            expected = -1 if n % 2 == 1 else 1
            if det != expected:
                results['passed'] = False
                results['failures'].append({'n': n, 'det': det, 'expected': expected})
        return results

    def verify_volume_preservation(self, n_max: int = 100) -> bool:
        for n in range(1, n_max + 1):
            det = self._core.matrix_det(self._core.matrix_power(n))
            if abs(det) != 1:
                return False
        return True

    def verify_pisot_convergence(self, n_values: List[int] = None) -> Dict[str, Any]:
        """Verify |φ^n - L_n| = |ψ^n| using Decimal for precision."""
        from decimal import Decimal, localcontext
        if n_values is None:
            n_values = [5, 10, 15, 20, 30, 50]
        results = {'passed': True, 'failures': []}
        for n in n_values:
            with localcontext() as ctx:
                ctx.prec = max(50, n * 2 + 20)
                sqrt5 = Decimal(5).sqrt()
                phi_d = (Decimal(1) + sqrt5) / Decimal(2)
                psi_d = (Decimal(1) - sqrt5) / Decimal(2)
                phi_n = phi_d ** n
                L_n = Decimal(self._core.lucas(n))
                error = abs(phi_n - L_n)
                expected = abs(psi_d) ** n
                ratio = error / expected if expected > 0 else Decimal(0)
                if abs(ratio - Decimal(1)) > Decimal('1e-20'):
                    results['passed'] = False
                    results['failures'].append({'n': n, 'ratio': float(ratio)})
        return results

    def verify_pisot_monotonic(self, n_max: int = 50) -> bool:
        """Verify error strictly decreases with n (using Decimal)."""
        from decimal import Decimal, localcontext
        errors = []
        for n in range(2, n_max + 1):
            with localcontext() as ctx:
                ctx.prec = max(50, n * 2 + 20)
                sqrt5 = Decimal(5).sqrt()
                phi_d = (Decimal(1) + sqrt5) / Decimal(2)
                phi_n = phi_d ** n
                L_n = Decimal(self._core.lucas(n))
                errors.append(abs(phi_n - L_n))
        for i in range(1, len(errors)):
            if errors[i] >= errors[i-1]:
                return False
        return True

    def verify_binet_exactness(self, n_values: List[int] = None) -> Dict[str, Any]:
        if n_values is None:
            n_values = [0, 1, 5, 10, 20, 50, 100, 500, 1000]
        results = {'passed': True, 'failures': []}
        for n in n_values:
            f_exact = self._core.fibonacci(n)
            f_binet = self._core.binet_f(n)
            if f_exact != f_binet:
                results['passed'] = False
                results['failures'].append({'n': n, 'exact': f_exact, 'binet': f_binet})
        return results

    def verify_lucas_binet(self, n_values: List[int] = None) -> Dict[str, Any]:
        if n_values is None:
            n_values = [0, 1, 5, 10, 20, 50, 100, 500]
        results = {'passed': True, 'failures': []}
        for n in n_values:
            l_exact = self._core.lucas(n)
            l_binet = self._core.binet_l(n)
            if l_exact != l_binet:
                results['passed'] = False
                results['failures'].append({'n': n, 'exact': l_exact, 'binet': l_binet})
        return results

    def verify_matrix_power_law(self, pairs: List[Tuple[int, int]] = None) -> Dict[str, Any]:
        if pairs is None:
            pairs = [(1, 1), (2, 3), (5, 8), (8, 13), (10, 15)]
        results = {'passed': True, 'failures': []}
        for a, b in pairs:
            Ma = self._core.matrix_power(a)
            Mb = self._core.matrix_power(b)
            M_ab = self._core.matrix_power(a + b)
            prod = self._core.matrix_multiply(Ma, Mb)
            if prod != M_ab:
                results['passed'] = False
                results['failures'].append({'a': a, 'b': b, 'computed': prod, 'expected': M_ab})
        return results

    def verify_commutativity(self, pairs: List[Tuple[int, int]] = None) -> Dict[str, Any]:
        if pairs is None:
            pairs = [(1, 2), (3, 5), (8, 13), (10, 20)]
        results = {'passed': True, 'failures': []}
        for a, b in pairs:
            Ma = self._core.matrix_power(a)
            Mb = self._core.matrix_power(b)
            prod_ab = self._core.matrix_multiply(Ma, Mb)
            prod_ba = self._core.matrix_multiply(Mb, Ma)
            if prod_ab != prod_ba:
                results['passed'] = False
                results['failures'].append({'a': a, 'b': b})
        return results

    def verify_integrity_rejects_impostors(self) -> Dict[str, Any]:
        """Verify that cassini_integrity_check rejects known impostors."""
        impostors = [
            [[0, 1], [1, 4]],   # trace=4=L(3), det=-1=(-1)^3, but not Q^3
            [[1, 2], [3, 4]],   # Not symmetric
            [[2, 1], [1, 2]],   # Symmetric but a-d=0≠1
            [[-1, 1], [1, 0]],  # Negative entry
            [[0, 0], [0, 0]],   # Zero matrix
        ]
        results = {'passed': True, 'failures': []}
        for m in impostors:
            if self._core.cassini_integrity_check(m):
                results['passed'] = False
                results['failures'].append({'matrix': m, 'issue': 'impostor accepted'})
        return results

    def verify_all(self) -> Dict[str, Any]:
        return {
            'cassini': self.verify_cassini(),
            'volume_preservation': self.verify_volume_preservation(),
            'pisot': self.verify_pisot_convergence(),
            'pisot_monotonic': self.verify_pisot_monotonic(),
            'binet': self.verify_binet_exactness(),
            'lucas_binet': self.verify_lucas_binet(),
            'matrix_power': self.verify_matrix_power_law(),
            'commutativity': self.verify_commutativity(),
            'integrity_impostors': self.verify_integrity_rejects_impostors(),
        }
