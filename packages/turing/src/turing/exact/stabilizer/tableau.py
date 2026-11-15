"""
Turing Exact Quantum Library — Symplectic Weyl-Heisenberg Stabilizer Tableau over F_p
"""

from __future__ import annotations
from typing import List, Tuple, Optional
from turing.exact.errors import DimensionMismatchError
from turing.exact.ring.utils import is_prime


class StabilizerTableauZetaP:
    """
    Exact qudit stabilizer tableau over the finite field F_p.
    Folds the exponential p^n x p^n Hilbert space into O(n^2) symplectic generators.
    Weyl-Heisenberg algebra: Z * X = zeta_p * X * Z.
    """
    __slots__ = ('p', 'n_qudits', 'num_rows', 'x_mat', 'z_mat', 'phases')

    def __init__(self, p: int, n_qudits: int, x_mat: List[List[int]], z_mat: List[List[int]], phases: List[int]):
        if not is_prime(p):
            raise ValueError(f"p={p} must be prime")
        self.p = p
        self.n_qudits = n_qudits
        self.num_rows = len(x_mat)
        if len(z_mat) != self.num_rows or len(phases) != self.num_rows:
            raise DimensionMismatchError("Tableau dimension mismatch between X, Z, and phase vectors")
        if any(len(r) != n_qudits for r in x_mat) or any(len(r) != n_qudits for r in z_mat):
            raise DimensionMismatchError("Qudit width mismatch in tableau generators")
        self.x_mat = [[c % p for c in row] for row in x_mat]
        self.z_mat = [[c % p for c in row] for row in z_mat]
        self.phases = [ph % p for ph in phases]

    @classmethod
    def zero_state(cls, p: int, n_qudits: int) -> 'StabilizerTableauZetaP':
        """Initializes the |0...0> qudit stabilizer state (stabilized by Z_1, ..., Z_n)."""
        x_mat = [[0] * n_qudits for _ in range(n_qudits)]
        z_mat = [[1 if i == j else 0 for j in range(n_qudits)] for i in range(n_qudits)]
        phases = [0] * n_qudits
        return cls(p, n_qudits, x_mat, z_mat, phases)

    def apply_x(self, q: int) -> None:
        """Applies Pauli X gate on qudit q (shifts phase by z_mat[r][q])."""
        if not (0 <= q < self.n_qudits):
            raise DimensionMismatchError(f"Qudit index {q} out of range for {self.n_qudits} qudits")
        for r in range(self.num_rows):
            self.phases[r] = (self.phases[r] + self.z_mat[r][q]) % self.p

    def apply_z(self, q: int) -> None:
        """Applies Pauli Z gate on qudit q (shifts phase by -x_mat[r][q])."""
        if not (0 <= q < self.n_qudits):
            raise DimensionMismatchError(f"Qudit index {q} out of range for {self.n_qudits} qudits")
        for r in range(self.num_rows):
            self.phases[r] = (self.phases[r] - self.x_mat[r][q]) % self.p

    def apply_fourier(self, q: int) -> None:
        """
        Symplectic Fourier conjugation: (x, z) -> (-z mod p, x mod p).
        """
        if not (0 <= q < self.n_qudits):
            raise DimensionMismatchError(f"Qudit index {q} out of range for {self.n_qudits} qudits")
        for r in range(self.num_rows):
            nx = (-self.z_mat[r][q]) % self.p
            nz = self.x_mat[r][q] % self.p
            self.x_mat[r][q] = nx
            self.z_mat[r][q] = nz

    def apply_cnot(self, ctrl: int, tgt: int) -> None:
        """
        Symplectic CNOT conjugation: x_tgt += x_ctrl, z_ctrl -= z_tgt (mod p).
        """
        if not (0 <= ctrl < self.n_qudits and 0 <= tgt < self.n_qudits):
            raise DimensionMismatchError("Control or target qudit index out of range")
        if ctrl == tgt:
            raise DimensionMismatchError("Control and target qudits must be distinct")
        for r in range(self.num_rows):
            self.x_mat[r][tgt] = (self.x_mat[r][tgt] + self.x_mat[r][ctrl]) % self.p
            self.z_mat[r][ctrl] = (self.z_mat[r][ctrl] - self.z_mat[r][tgt]) % self.p

    def measure_z(self, q: int, outcome_override: Optional[int] = None) -> Tuple[int, bool]:
        """
        Exact stabilizer measurement of qudit q in the computational Z-basis over F_p.
        Computes whether an observable commutes with all stabilizer generators (deterministic)
        or anticommutes with at least one generator (random outcome in F_p).
        Updates the tableau in-place using symplectic Gaussian elimination and projection.
        Returns: (outcome: int, is_deterministic: bool)
        """
        if not (0 <= q < self.n_qudits):
            raise DimensionMismatchError(f"Qudit index {q} out of range for {self.n_qudits} qudits")

        p = self.p

        # 1. Check for anticommuting generators: Z_q does not commute with g_r iff x_mat[r][q] != 0
        pivot = -1
        for r in range(self.num_rows):
            if self.x_mat[r][q] != 0:
                pivot = r
                break

        if pivot == -1:
            # Deterministic outcome: Z_q is in the stabilizer group (or commutes with all generators)
            # Find vector c in F_p^num_rows such that sum_r c_r * z_mat[r] == e_q
            # Solve Z^T c = e_q over F_p
            n = self.num_rows
            A = [[self.z_mat[r][col] for r in range(n)] + [1 if col == q else 0] for col in range(self.n_qudits)]

            row = 0
            pivots = {}
            for col in range(n):
                piv = -1
                for r in range(row, self.n_qudits):
                    if A[r][col] != 0:
                        piv = r
                        break
                if piv == -1:
                    continue
                A[row], A[piv] = A[piv], A[row]
                inv = pow(A[row][col], p - 2, p)
                A[row] = [(x * inv) % p for x in A[row]]
                for r in range(self.n_qudits):
                    if r != row and A[r][col] != 0:
                        f = A[r][col]
                        A[r] = [(A[r][k] - f * A[row][k]) % p for k in range(n + 1)]
                pivots[col] = row
                row += 1

            c = [0] * n
            for col, r in pivots.items():
                c[col] = A[r][-1]

            outcome = sum(c[r] * self.phases[r] for r in range(n)) % p
            return outcome, True

        # Random outcome: at least one generator anticommutes with Z_q
        outcome = outcome_override % p if outcome_override is not None else 0
        inv_pivot_x = pow(self.x_mat[pivot][q], p - 2, p)

        # 2. Symplectic Gaussian elimination: eliminate x_mat[r][q] for all other rows r != pivot
        for r in range(self.num_rows):
            if r != pivot and self.x_mat[r][q] != 0:
                factor = (self.x_mat[r][q] * inv_pivot_x) % p
                k = (-factor) % p  # multiply g_r by g_pivot^k

                # Compute Weyl-Heisenberg multiplication phase:
                b_dot_c = sum(self.z_mat[r][j] * self.x_mat[pivot][j] for j in range(self.n_qudits)) % p
                d_dot_c = sum(self.z_mat[pivot][j] * self.x_mat[pivot][j] for j in range(self.n_qudits)) % p
                k_choose_2 = (k * (k - 1) * pow(2, p - 2, p)) % p

                phase_shift = (k * self.phases[pivot] + k * b_dot_c + k_choose_2 * d_dot_c) % p
                self.phases[r] = (self.phases[r] + phase_shift) % p

                for j in range(self.n_qudits):
                    self.x_mat[r][j] = (self.x_mat[r][j] + k * self.x_mat[pivot][j]) % p
                    self.z_mat[r][j] = (self.z_mat[r][j] + k * self.z_mat[pivot][j]) % p

        # 3. Replace pivot row with measurement projector Z_q with eigenvalue outcome
        self.x_mat[pivot] = [0] * self.n_qudits
        self.z_mat[pivot] = [1 if j == q else 0 for j in range(self.n_qudits)]
        self.phases[pivot] = outcome

        # 4. Eliminate Z_q component in all other rows r != pivot
        for r in range(self.num_rows):
            if r != pivot and self.z_mat[r][q] != 0:
                z_factor = self.z_mat[r][q]
                self.z_mat[r][q] = 0
                self.phases[r] = (self.phases[r] - z_factor * outcome) % p

        return outcome, False

    def __repr__(self) -> str:
        return f"StabilizerTableauZetaP(p={self.p}, n_qudits={self.n_qudits}, num_rows={self.num_rows})"
