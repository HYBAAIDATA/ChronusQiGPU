"""Exact channels, Hamiltonians and Fisher information over Q(zeta_8).

Kraus maps. A channel {K_i} is trace preserving iff sum K_i^dagger K_i = I,
decided exactly. Its Stinespring isometry V = sum K_i (x) |i> satisfies
V^dagger V = I iff the channel is trace preserving; the Kraus rank (the
minimal number of Kraus operators) is the rank of the Choi matrix and is
the dimension of the purifying ancilla. The Liouville superoperator
S = sum K (x) conj(K) acts on vectorized density matrices, so a product of
local channels is a bond-one MPO on the doubled sites. The Kraus rank is a
purification dimension, not a spatial MPO bond dimension.

Hamiltonians. Real Pauli-sum coefficients make H exactly Hermitian; a real
spectrum follows by the spectral theorem. exp(-i theta P) for a Pauli string
P is cos(theta) I - i sin(theta) P, exact exactly when theta is a multiple of
pi/4. Other times leave the field and raise NotInF4; eigenvalues are a
float-plane computation.

Fisher information. For a pure state and Hermitian generators G_i,
F_ij = 4 Re(<G_i G_j> - <G_i><G_j>) lies in Q(sqrt 2). PSD-ness, the
Cramer-Rao inequality and the Heisenberg bound are decided exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, List, Sequence, Tuple

from . import exact_linalg as la
from .cyclotomic import I8, ONE8, ZERO8, Q8
from .exact_network import Core, ExactMPO, ExactMPS
from .exact_tensor import NotInF4

Matrix = List[List[Q8]]

PAULI: dict = {
    "I": [[ONE8, ZERO8], [ZERO8, ONE8]],
    "X": [[ZERO8, ONE8], [ONE8, ZERO8]],
    "Y": [[ZERO8, -I8], [I8, ZERO8]],
    "Z": [[ONE8, ZERO8], [ZERO8, -ONE8]],
}

HALF = Q8(1, 0, 0, 0, 2)
INV_SQRT2 = Q8(0, 1, 0, 0, 2)


class ChannelError(ValueError):
    """A Kraus set, Hamiltonian or Fisher input violates its contract."""


def _m(rows: Sequence[Sequence[Any]]) -> Matrix:
    return [[Q8.coerce(v) for v in row] for row in rows]


def _scale(m: Matrix, c: Q8) -> Matrix:
    return [[c * v for v in row] for row in m]


def _add(a: Matrix, b: Matrix) -> Matrix:
    return [[x + y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


@dataclass(frozen=True)
class KrausChannel:
    ops: Tuple[Tuple[Tuple[Q8, ...], ...], ...]

    @classmethod
    def of(cls, ops: Sequence[Sequence[Sequence[Any]]]) -> "KrausChannel":
        if not ops:
            raise ChannelError("a channel needs at least one Kraus operator")
        mats = tuple(tuple(tuple(r) for r in _m(k)) for k in ops)
        shapes = {la.shape(m) for m in mats}
        if len(shapes) != 1:
            raise ChannelError("Kraus operators must share one shape")
        return cls(mats)

    @property
    def dims(self) -> Tuple[int, int]:
        rows, cols = la.shape(self.ops[0])
        return rows, cols

    def completeness(self) -> Matrix:
        d_in = self.dims[1]
        acc = [[ZERO8] * d_in for _ in range(d_in)]
        for k in self.ops:
            acc = _add(acc, la.matmul(la.adjoint(k), k))
        return acc

    def is_trace_preserving(self) -> bool:
        d_in = self.dims[1]
        return la.equal(self.completeness(), la.identity(d_in, ONE8))

    def apply(self, rho: Sequence[Sequence[Any]]) -> Matrix:
        r = _m(rho)
        d_out = self.dims[0]
        out = [[ZERO8] * d_out for _ in range(d_out)]
        for k in self.ops:
            out = _add(out, la.matmul(la.matmul(k, r), la.adjoint(k)))
        return out

    def compose(self, first: "KrausChannel") -> "KrausChannel":
        """self after first: {A_i B_j}."""
        return KrausChannel.of([la.matmul(a, b) for a in self.ops for b in first.ops])

    def stinespring(self) -> Matrix:
        """V = sum_i K_i (x) |i>, rows indexed (i, out)."""
        return [list(row) for k in self.ops for row in k]

    def is_isometric_dilation(self) -> bool:
        v = self.stinespring()
        return la.equal(la.matmul(la.adjoint(v), v), la.identity(self.dims[1], ONE8))

    def superoperator(self) -> Matrix:
        """Liouville S = sum K (x) conj(K); vec(K rho K^dagger) = S vec(rho), row-major."""
        d_out, d_in = self.dims
        acc = [[ZERO8] * (d_in * d_in) for _ in range(d_out * d_out)]
        for k in self.ops:
            acc = _add(acc, la.kron(k, [[v.conjugate() for v in row] for row in k]))
        return acc

    def choi(self) -> Matrix:
        """J = sum_ab |a><b| (x) E(|a><b|)."""
        d_out, d_in = self.dims
        size = d_in * d_out
        j = [[ZERO8] * size for _ in range(size)]
        for a in range(d_in):
            for b in range(d_in):
                unit = [[ONE8 if (x, y) == (a, b) else ZERO8 for y in range(d_in)] for x in range(d_in)]
                image = self.apply(unit)
                for x in range(d_out):
                    for y in range(d_out):
                        j[a * d_out + x][b * d_out + y] = image[x][y]
        return j

    def kraus_rank(self) -> int:
        return la.rank(self.choi())


def channel_mpo(channels: Sequence[KrausChannel], **kwargs: Any) -> ExactMPO:
    """Product of local channels as a bond-one MPO on vectorized (doubled) sites."""
    sups = [c.superoperator() for c in channels]
    if any(len(s) != len(s[0]) for s in sups):
        raise ChannelError("channel_mpo needs square local channels")
    return ExactMPO.from_local(sups, **kwargs)


def amplitude_damping_half() -> KrausChannel:
    """gamma = 1/2: K0 = diag(1, 1/sqrt 2), K1 = (1/sqrt 2)|0><1|."""
    return KrausChannel.of([[[ONE8, ZERO8], [ZERO8, INV_SQRT2]], [[ZERO8, INV_SQRT2], [ZERO8, ZERO8]]])


def dephasing_half() -> KrausChannel:
    return KrausChannel.of([_scale(PAULI["I"], INV_SQRT2), _scale(PAULI["Z"], INV_SQRT2)])


def depolarizing_full() -> KrausChannel:
    return KrausChannel.of([_scale(PAULI[p], HALF) for p in "IXYZ"])


# -- Hamiltonians --------------------------------------------------------------


@dataclass(frozen=True)
class PauliTerm:
    coeff: Q8
    word: str

    def __post_init__(self) -> None:
        if not self.coeff.is_real():
            raise ChannelError("Pauli-sum coefficients must be real for Hermiticity")
        if any(ch not in PAULI for ch in self.word):
            raise ChannelError(f"invalid Pauli word {self.word!r}")


@dataclass(frozen=True)
class PauliHamiltonian:
    n: int
    terms: Tuple[PauliTerm, ...]

    @classmethod
    def of(cls, n: int, terms: Sequence[Tuple[Any, str]]) -> "PauliHamiltonian":
        built = tuple(PauliTerm(Q8.coerce(c), w) for c, w in terms)
        if any(len(t.word) != n for t in built):
            raise ChannelError("every Pauli word must have length n")
        return cls(int(n), built)

    def matrix(self, *, max_qubits: int = 10) -> Matrix:
        if self.n > max_qubits:
            raise ChannelError(f"dense Hamiltonian of {self.n} qubits exceeds {max_qubits}")
        size = 1 << self.n
        acc = [[ZERO8] * size for _ in range(size)]
        for t in self.terms:
            op: Matrix = [[ONE8]]
            for ch in t.word:
                op = la.kron(op, PAULI[ch])
            acc = _add(acc, _scale(op, t.coeff))
        return acc

    def is_hermitian(self) -> bool:
        return la.is_hermitian(self.matrix())

    def mpo(self, **kwargs: Any) -> ExactMPO:
        """Exact Pauli-sum MPO: direct sum of product terms, then exact compression."""
        if not self.terms:
            raise ChannelError("empty Hamiltonian")
        t_count = len(self.terms)
        cores = []
        for site in range(self.n):
            left = 1 if site == 0 else t_count
            right = 1 if site == self.n - 1 else t_count
            data = []
            for lb in range(left):
                for o in range(2):
                    for i in range(2):
                        for rb in range(right):
                            term = lb if site > 0 else rb
                            if site > 0 and site < self.n - 1 and lb != rb:
                                data.append(ZERO8)
                                continue
                            if site == self.n - 1:
                                term = lb
                            t = self.terms[term]
                            v = PAULI[t.word[site]][o][i]
                            data.append(t.coeff * v if site == 0 else v)
            cores.append(Core(left, 4, right, tuple(data)))
        if self.n == 1:
            total = [[ZERO8, ZERO8], [ZERO8, ZERO8]]
            for t in self.terms:
                total = _add(total, _scale(PAULI[t.word], t.coeff))
            return ExactMPO.from_local([total], **kwargs)
        kwargs.setdefault("genesis", {"kind": "mpo", "pauli_terms": [(t.coeff, t.word) for t in self.terms]})
        out = ExactMPO(cores, d=2, **kwargs)
        out.compress()
        return out


def _cos_sin_eighth(k: int) -> Tuple[Q8, Q8]:
    table = [
        (ONE8, ZERO8),
        (INV_SQRT2, INV_SQRT2),
        (ZERO8, ONE8),
        (-INV_SQRT2, INV_SQRT2),
        (-ONE8, ZERO8),
        (-INV_SQRT2, -INV_SQRT2),
        (ZERO8, -ONE8),
        (INV_SQRT2, -INV_SQRT2),
    ]
    return table[k % 8]


def pauli_rotation(word: str, theta_over_pi: Fraction | int, **kwargs: Any) -> ExactMPO:
    """exp(-i theta P) as an exact bond-two MPO; theta/pi must lie in Z/4."""
    eighths = Fraction(theta_over_pi) * 4
    if eighths.denominator != 1:
        raise NotInF4(f"exp(-i pi*{theta_over_pi} P) leaves Q(zeta_8); only pi/4 multiples are exact")
    c, s = _cos_sin_eighth(int(eighths))
    neg_is = -(I8 * s)
    n = len(word)
    if n == 1:
        m = _add(_scale(PAULI["I"], c), _scale(PAULI[word], neg_is))
        return ExactMPO.from_local([m], **kwargs)
    cores = []
    for site, ch in enumerate(word):
        left = 1 if site == 0 else 2
        right = 1 if site == n - 1 else 2
        data = []
        for lb in range(left):
            for o in range(2):
                for i in range(2):
                    for rb in range(right):
                        branch = rb if site == 0 else lb
                        if 0 < site < n - 1 and lb != rb:
                            data.append(ZERO8)
                            continue
                        op = PAULI["I"] if branch == 0 else PAULI[ch]
                        coeff = (c if branch == 0 else neg_is) if site == 0 else ONE8
                        data.append(coeff * op[o][i])
        cores.append(Core(left, 4, right, tuple(data)))
    kwargs.setdefault("genesis", {"kind": "mpo", "rotation": word, "theta_over_pi": Fraction(theta_over_pi)})
    out = ExactMPO(cores, d=2, **kwargs)
    out.compress()
    return out


# -- Fisher information --------------------------------------------------------


def fisher_matrix(state: ExactMPS, generators: Sequence[ExactMPO]) -> Matrix:
    """F_ij = 4 Re(<G_i G_j> - <G_i><G_j>) for a pure state, exactly."""
    norm = state.inner(state)
    applied = [g.apply(state) for g in generators]
    means = [state.inner(a) / norm for a in applied]
    k = len(generators)
    out = [[ZERO8] * k for _ in range(k)]
    for i in range(k):
        for j in range(k):
            second = applied[i].inner(applied[j]) / norm
            out[i][j] = Q8(4) * (second - means[i].conjugate() * means[j]).real()
    for a in applied:
        a.close()
    return out


def quantum_fisher_information(state: ExactMPS, generator: ExactMPO) -> Q8:
    return fisher_matrix(state, [generator])[0][0]


def cramer_rao_holds(variance: Any, fisher: Any, repetitions: int = 1) -> bool:
    """Var * nu * F >= 1, decided exactly."""
    lhs = Q8.coerce(variance) * Q8(int(repetitions)) * Q8.coerce(fisher)
    return lhs >= ONE8


def heisenberg_bound_holds(fisher: Any, n: int) -> bool:
    """For G = sum_i Z_i / 2 on n qubits, F <= n^2."""
    return Q8.coerce(fisher) <= Q8(n * n)


def natural_gradient_step(
    theta: Sequence[Any], gradient: Sequence[Any], fisher: Sequence[Sequence[Any]], eta: Any
) -> List[Q8]:
    """theta - eta F^-1 grad, exactly (F must be non-singular)."""
    f = _m(fisher)
    step = la.solve(f, [Q8.coerce(g) for g in gradient])
    e = Q8.coerce(eta)
    return [Q8.coerce(t) - e * s for t, s in zip(theta, step)]


def total_z_half(n: int, **kwargs: Any) -> ExactMPO:
    """G = sum_i Z_i / 2 as an exact Pauli-sum MPO."""
    return PauliHamiltonian.of(
        n, [(HALF, "".join("Z" if j == i else "I" for j in range(n))) for i in range(n)]
    ).mpo(**kwargs)


__all__ = [
    "ChannelError",
    "KrausChannel",
    "PAULI",
    "PauliHamiltonian",
    "PauliTerm",
    "amplitude_damping_half",
    "channel_mpo",
    "cramer_rao_holds",
    "dephasing_half",
    "depolarizing_full",
    "fisher_matrix",
    "heisenberg_bound_holds",
    "natural_gradient_step",
    "pauli_rotation",
    "quantum_fisher_information",
    "total_z_half",
]
