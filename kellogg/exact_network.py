"""Exact tensor networks over Q(zeta_8): tensor trains, MPS and MPO in custody.

Field: Q(zeta_8) = Q(i, sqrt 2) on integer coordinates (:class:`Q8`). Every
amplitude, gate entry, contraction, probability and certificate value is
exact; there is no float on this path.

Structure:

* Custody holds every core. A train keeps one content reference per site
  (the payload digest, which is also the site's Merkle leaf) and a bounded
  window of decoded cores. Identical cores share one custody block.
* Compression is structural. A two-site update ends in the exact rank
  factorization M = C F (C = pivot columns, F = RREF rows), so every bond
  equals the exact rank across its cut. ``compress()`` restores minimality
  after a non-unitary step. Nothing is truncated; SVD truncation lives in
  the float plane (``kellogg.tensor_network.tt_svd``).
* Every operation records a :class:`TensorCertificate` in custody binding
  the input and output state roots, the parameters, the invariants it
  checked, and the custody bytes it moved.

An MPS with bond dimension chi represents a state exactly iff the state's
Schmidt rank is at most chi at every cut. Entropy below log chi is
necessary but not sufficient, so Kellogg certifies ranks, not entropies.
"""

from __future__ import annotations

import hashlib
import random
from collections import OrderedDict
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import exact_linalg as la
from .certificate import CertificateLedger, MerkleTree, TensorCertificate, certify, cex_digest
from .custody import default_custody
from .cyclotomic import I8, ONE8, ZERO8, Q8
from .exact_tensor import GATES

FIELD = "Q(zeta8)"
MACHINE = "kellogg.exact_network/v1"
_CORE_MAGIC = b"KTC1"


class ExactNetworkError(ValueError):
    """A shape, gate, site or exactness contract was violated."""


@dataclass(frozen=True)
class Core:
    """Three-leg core (left, phys, right); data row-major over (l, s, r)."""

    left: int
    phys: int
    right: int
    data: Tuple[Q8, ...]

    def __post_init__(self) -> None:
        if min(self.left, self.phys, self.right) < 1:
            raise ExactNetworkError("core legs must be positive")
        if len(self.data) != self.left * self.phys * self.right:
            raise ExactNetworkError("core data length does not match its legs")

    def at(self, l: int, s: int, r: int) -> Q8:
        return self.data[(l * self.phys + s) * self.right + r]

    def matrix(self, s: int) -> List[List[Q8]]:
        return [[self.at(l, s, r) for r in range(self.right)] for l in range(self.left)]

    def params(self) -> int:
        return len(self.data)


def encode_core(core: Core) -> bytes:
    body = ";".join(q.canonical() for q in core.data)
    return _CORE_MAGIC + f"|{core.left},{core.phys},{core.right}|{body}".encode("ascii")


def decode_core(payload: bytes) -> Core:
    if not payload.startswith(_CORE_MAGIC):
        raise ExactNetworkError("payload is not a Kellogg tensor core")
    _, legs, body = payload[len(_CORE_MAGIC):].decode("ascii").split("|", 2)
    left, phys, right = (int(v) for v in legs.split(","))
    data = tuple(Q8(*(int(x) for x in item.split(","))) for item in body.split(";"))
    return Core(left, phys, right, data)


def _q(value: Any) -> Q8:
    return Q8.coerce(value)


_NAMED: Dict[str, Tuple[Tuple[Q8, ...], ...]] = {}


def _gate_matrix(gate: Any, size: int) -> Tuple[Tuple[Q8, ...], ...]:
    if isinstance(gate, str):
        if size != 2 or gate not in GATES:
            raise ExactNetworkError(f"unknown {size}x{size} gate {gate!r}")
        hit = _NAMED.get(gate)
        if hit is None:
            hit = tuple(tuple(_q(v) for v in row) for row in GATES[gate])
            _NAMED[gate] = hit
        return hit
    rows = tuple(tuple(_q(v) for v in row) for row in gate)
    if len(rows) != size or any(len(r) != size for r in rows):
        raise ExactNetworkError(f"gate must be {size}x{size}")
    return rows


_UNITARY_CACHE: Dict[Tuple, bool] = {}


def gate_is_unitary(matrix: Sequence[Sequence[Q8]]) -> bool:
    key = tuple(v.key() for row in matrix for v in row)
    hit = _UNITARY_CACHE.get(key)
    if hit is None:
        hit = la.is_unitary([list(r) for r in matrix])
        _UNITARY_CACHE[key] = hit
    return hit


def _ctrl(u: Sequence[Sequence[Q8]]) -> Tuple[Tuple[Q8, ...], ...]:
    z, o = ZERO8, ONE8
    return (
        (o, z, z, z),
        (z, o, z, z),
        (z, z, u[0][0], u[0][1]),
        (z, z, u[1][0], u[1][1]),
    )


CNOT = _ctrl(_gate_matrix("X", 2))
CZ = _ctrl(_gate_matrix("Z", 2))
SWAP = tuple(
    tuple(ONE8 if (r, c) in ((0, 0), (1, 2), (2, 1), (3, 3)) else ZERO8 for c in range(4))
    for r in range(4)
)
TWO_QUBIT_GATES = {"CNOT": CNOT, "CX": CNOT, "CZ": CZ, "SWAP": SWAP}


def _split(theta: List[List[Q8]], left: int, p1: int, p2: int, right: int) -> Tuple[Core, Core]:
    """Exact rank factorization of a two-site block into two minimal cores."""
    c, f, pivots = la.cr_factor(theta)
    k = max(1, len(pivots))
    if not pivots:
        c = [[ZERO8] for _ in range(left * p1)]
        f = [[ZERO8] * (p2 * right)]
    a = Core(left, p1, k, tuple(v for row in c for v in row))
    b = Core(k, p2, right, tuple(v for row in f for v in row))
    return a, b


def _transfer(env: List[List[Q8]], bra: Core, ket: Core) -> List[List[Q8]]:
    """E'[r][r'] = sum conj(bra[l,s,r]) E[l][l'] ket[l',s,r']."""
    tmp = [[[ZERO8] * ket.right for _ in range(ket.phys)] for _ in range(bra.left)]
    for l in range(bra.left):
        row = env[l]
        for lp in range(ket.left):
            e = row[lp]
            if e.is_zero():
                continue
            for s in range(ket.phys):
                base = (lp * ket.phys + s) * ket.right
                acc = tmp[l][s]
                for rp in range(ket.right):
                    v = ket.data[base + rp]
                    if not v.is_zero():
                        acc[rp] = acc[rp] + e * v
    out = [[ZERO8] * ket.right for _ in range(bra.right)]
    for l in range(bra.left):
        for s in range(bra.phys):
            base = (l * bra.phys + s) * bra.right
            t = tmp[l][s]
            for r in range(bra.right):
                b = bra.data[base + r]
                if b.is_zero():
                    continue
                bc = b.conjugate()
                line = out[r]
                for rp in range(ket.right):
                    if not t[rp].is_zero():
                        line[rp] = line[rp] + bc * t[rp]
    return out


def _transfer_right(env: List[List[Q8]], bra: Core, ket: Core) -> List[List[Q8]]:
    """R'[l][l'] = sum conj(bra[l,s,r]) R[r][r'] ket[l',s,r']."""
    out = [[ZERO8] * ket.left for _ in range(bra.left)]
    for lp in range(ket.left):
        for s in range(ket.phys):
            kv = [ket.at(lp, s, rp) for rp in range(ket.right)]
            w = [ZERO8] * bra.right
            for r in range(bra.right):
                acc = ZERO8
                row = env[r]
                for rp in range(ket.right):
                    if not kv[rp].is_zero() and not row[rp].is_zero():
                        acc = acc + row[rp] * kv[rp]
                w[r] = acc
            for l in range(bra.left):
                acc = out[l][lp]
                for r in range(bra.right):
                    b = bra.at(l, s, r)
                    if not b.is_zero() and not w[r].is_zero():
                        acc = acc + b.conjugate() * w[r]
                out[l][lp] = acc
    return out


def _genesis(params: Any) -> str:
    return hashlib.sha256(b"kellogg.genesis/v1\0" + cex_digest(params).encode()).hexdigest()


class ExactTensorTrain:
    """Custody-backed exact tensor train with structural lossless compression."""

    kind = "tensor_train"

    def __init__(
        self,
        cores: Sequence[Core],
        *,
        custody: Any = None,
        window: int = 64,
        retain_ledger: bool = True,
        genesis: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not cores:
            raise ExactNetworkError("a tensor train needs at least one core")
        if cores[0].left != 1 or cores[-1].right != 1:
            raise ExactNetworkError("boundary bonds must be one")
        for a, b in zip(cores, cores[1:]):
            if a.right != b.left:
                raise ExactNetworkError("adjacent bonds do not match")
        self.custody = custody if custody is not None else default_custody()
        self.window = max(2, int(window))
        self._cache: "OrderedDict[str, Core]" = OrderedDict()
        self._refcount: Dict[str, int] = {}
        self.refs: List[str] = []
        self.legs: List[Tuple[int, int, int]] = []
        written = 0
        for core in cores:
            payload = encode_core(core)
            ref = self.custody.put(payload)
            written += len(payload)
            self._hold(ref)
            self.refs.append(ref)
            self.legs.append((core.left, core.phys, core.right))
            self._remember(ref, core)
        self._tree = MerkleTree(self.refs)
        self.ledger = CertificateLedger(sink=self.custody.record, retain=retain_ledger)
        params = dict(genesis or {"kind": self.kind, "sites": len(cores)})
        self._emit(
            "create",
            _genesis(params),
            params,
            {"bonds": self.bonds(), "custody_bytes_written": written},
        )

    # -- custody plumbing -------------------------------------------------

    def _hold(self, ref: str) -> None:
        self._refcount[ref] = self._refcount.get(ref, 0) + 1

    def _drop(self, ref: str) -> None:
        count = self._refcount.get(ref, 0) - 1
        if count <= 0:
            self._refcount.pop(ref, None)
            self._cache.pop(ref, None)
        else:
            self._refcount[ref] = count
        self.custody.release(ref)

    def close(self) -> None:
        """Release every hold this train has in custody."""
        for ref in self.refs:
            self._drop(ref)
        self.refs = []
        self._cache.clear()

    def __enter__(self) -> "ExactTensorTrain":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _remember(self, ref: str, core: Core) -> None:
        self._cache[ref] = core
        self._cache.move_to_end(ref)
        while len(self._cache) > self.window:
            self._cache.popitem(last=False)

    def core(self, site: int) -> Core:
        ref = self.refs[site]
        hit = self._cache.get(ref)
        if hit is not None:
            self._cache.move_to_end(ref)
            return hit
        core = decode_core(self.custody.get(ref))
        self._remember(ref, core)
        return core

    def _set(self, site: int, core: Core) -> int:
        payload = encode_core(core)
        ref = self.custody.put(payload)
        old = self.refs[site]
        self._hold(ref)
        if ref != old:
            self.refs[site] = ref
            self._tree.update(site, ref)
        self._drop(old)
        self.legs[site] = (core.left, core.phys, core.right)
        self._remember(ref, core)
        return len(payload)

    def _emit(
        self,
        op: str,
        input_boundary: str,
        parameters: Dict[str, Any],
        invariants: Dict[str, Any],
    ) -> TensorCertificate:
        cert = certify(op, FIELD, MACHINE, input_boundary, self.root, parameters, invariants)
        return self.ledger.record(cert)

    # -- structure ---------------------------------------------------------

    @property
    def sites(self) -> int:
        return len(self.refs)

    @property
    def root(self) -> str:
        return self._tree.root()

    def bonds(self) -> List[int]:
        return [self.legs[0][0]] + [legs[2] for legs in self.legs]

    def phys_dims(self) -> List[int]:
        return [legs[1] for legs in self.legs]

    def parameter_count(self) -> int:
        return sum(left * phys * right for left, phys, right in self.legs)

    def unique_blocks(self) -> int:
        return len(self._refcount)

    def representation(self) -> Dict[str, Any]:
        """Representation accounting: parameters held versus dense amplitudes.

        A representation ratio, never a physical compression claim.
        """
        dense_bits = sum(d.bit_length() - 1 for d in self.phys_dims())
        params = self.parameter_count()
        return {
            "sites": self.sites,
            "parameters": params,
            "unique_custody_blocks": self.unique_blocks(),
            "dense_amplitudes_log2": dense_bits if all(
                d & (d - 1) == 0 for d in self.phys_dims()
            ) else None,
            "classification": "representation_ratio",
        }

    # -- exact contractions ------------------------------------------------

    def inner(self, other: "ExactTensorTrain") -> Q8:
        if other.phys_dims() != self.phys_dims():
            raise ExactNetworkError("inner product needs matching physical legs")
        env = [[ONE8]]
        for i in range(self.sites):
            env = _transfer(env, self.core(i), other.core(i))
        return env[0][0]

    def norm2(self) -> Q8:
        value = self.inner(self)
        self._emit("norm2", self.root, {}, {"value": value, "real": value.is_real()})
        return value

    def _right_envs(self) -> List[List[List[Q8]]]:
        envs: List[List[List[Q8]]] = [None] * (self.sites + 1)  # type: ignore[list-item]
        envs[self.sites] = [[ONE8]]
        for i in range(self.sites - 1, -1, -1):
            c = self.core(i)
            envs[i] = _transfer_right(envs[i + 1], c, c)
        return envs

    def _left_envs(self, upto: int) -> List[List[Q8]]:
        env = [[ONE8]]
        for i in range(upto):
            c = self.core(i)
            env = _transfer(env, c, c)
        return env

    def entry(self, index: Sequence[int]) -> Q8:
        if len(index) != self.sites:
            raise ExactNetworkError("index length does not match the train")
        vec = [ONE8]
        for i, s in enumerate(index):
            c = self.core(i)
            vec = [
                sum((vec[l] * c.at(l, s, r) for l in range(c.left)), ZERO8)
                for r in range(c.right)
            ]
        value = vec[0]
        self._emit("entry", self.root, {"index": list(index)}, {"value": value})
        return value

    def to_dense(self, *, max_entries: int = 1 << 16) -> List[Q8]:
        total = 1
        for d in self.phys_dims():
            total *= d
        if total > max_entries:
            raise ExactNetworkError(f"dense expansion of {total} entries exceeds {max_entries}")
        rows = [[ONE8]]
        for i in range(self.sites):
            c = self.core(i)
            nxt = []
            for vec in rows:
                for s in range(c.phys):
                    nxt.append([
                        sum((vec[l] * c.at(l, s, r) for l in range(c.left)), ZERO8)
                        for r in range(c.right)
                    ])
            rows = nxt
        return [row[0] for row in rows]

    # -- structural compression -------------------------------------------

    def compress(self) -> TensorCertificate:
        """Exact two-sweep rank reduction; bonds become exact cut ranks."""
        before_root, before = self.root, self.bonds()
        moved = 0
        for i in range(self.sites - 1):
            a, b = self.core(i), self.core(i + 1)
            m = [[a.at(l, s, r) for r in range(a.right)] for l in range(a.left) for s in range(a.phys)]
            c, f, piv = la.cr_factor(m)
            k = max(1, len(piv))
            if not piv:
                c, f = [[ZERO8] for _ in m], [[ZERO8] * a.right]
            new_a = Core(a.left, a.phys, k, tuple(v for row in c for v in row))
            mixed = [
                [sum((f[j][t] * b.at(t, s, r) for t in range(b.left)), ZERO8)
                 for s in range(b.phys) for r in range(b.right)]
                for j in range(k)
            ]
            new_b = Core(k, b.phys, b.right, tuple(v for row in mixed for v in row))
            moved += self._set(i, new_a) + self._set(i + 1, new_b)
        for i in range(self.sites - 1, 0, -1):
            a, b = self.core(i - 1), self.core(i)
            m = [[b.at(l, s, r) for s in range(b.phys) for r in range(b.right)] for l in range(b.left)]
            c, f, piv = la.cr_factor(m)
            k = max(1, len(piv))
            if not piv:
                c, f = [[ZERO8] for _ in m], [[ZERO8] * (b.phys * b.right)]
            new_b = Core(k, b.phys, b.right, tuple(v for row in f for v in row))
            mixed = [
                [sum((a.at(l, s, t) * c[t][j] for t in range(a.right)), ZERO8) for j in range(k)]
                for l in range(a.left) for s in range(a.phys)
            ]
            new_a = Core(a.left, a.phys, k, tuple(v for row in mixed for v in row))
            moved += self._set(i, new_b) + self._set(i - 1, new_a)
        return self._emit(
            "compress",
            before_root,
            {"method": "exact_rank_factorization"},
            {
                "bonds_before": before,
                "bonds_after": self.bonds(),
                "lossless": True,
                "custody_bytes_written": moved,
            },
        )

    @classmethod
    def from_dense(
        cls,
        values: Sequence[Any],
        dims: Sequence[int],
        **kwargs: Any,
    ) -> "ExactTensorTrain":
        """Exact TT of a dense tensor: sequential rank factorizations, no truncation."""
        dims = [int(d) for d in dims]
        total = 1
        for d in dims:
            total *= d
        flat = [_q(v) for v in values]
        if len(flat) != total:
            raise ExactNetworkError("dense value count does not match dims")
        cores: List[Core] = []
        carry = [flat]  # rows: left bond, cols: remaining
        left = 1
        rest = total
        for d in dims[:-1]:
            rest //= d
            m = [
                [carry[l][s * rest + j] for j in range(rest)]
                for l in range(left) for s in range(d)
            ]
            c, f, piv = la.cr_factor(m)
            k = max(1, len(piv))
            if not piv:
                c, f = [[ZERO8] for _ in m], [[ZERO8] * rest]
            cores.append(Core(left, d, k, tuple(v for row in c for v in row)))
            carry = f
            left = k
        cores.append(Core(left, dims[-1], 1, tuple(v for row in carry for v in row)))
        kwargs.setdefault("genesis", {"kind": cls.kind, "dims": dims, "from": "dense"})
        return cls(cores, **kwargs)


def _ket(bits: Sequence[int]) -> List[Core]:
    zero = Core(1, 2, 1, (ONE8, ZERO8))
    one = Core(1, 2, 1, (ZERO8, ONE8))
    return [one if b else zero for b in bits]


class ExactMPS(ExactTensorTrain):
    """Exact qubit MPS: Clifford+T and every gate with entries in Q(zeta_8)."""

    kind = "mps"

    @classmethod
    def basis(cls, bits: Sequence[int], **kwargs: Any) -> "ExactMPS":
        bits = [int(b) for b in bits]
        if any(b not in (0, 1) for b in bits):
            raise ExactNetworkError("basis bits must be 0 or 1")
        kwargs.setdefault("genesis", {"kind": "mps", "basis": "".join(map(str, bits))})
        return cls(_ket(bits), **kwargs)

    @classmethod
    def zeros(cls, n: int, **kwargs: Any) -> "ExactMPS":
        kwargs.setdefault("genesis", {"kind": "mps", "zeros": int(n)})
        return cls(_ket([0] * int(n)), **kwargs)

    def _check_site(self, site: int) -> None:
        if not 0 <= site < self.sites:
            raise ExactNetworkError(f"site {site} outside 0..{self.sites - 1}")

    def apply_1q(self, site: int, gate: Any) -> TensorCertificate:
        self._check_site(site)
        u = _gate_matrix(gate, 2)
        if not gate_is_unitary(u):
            raise ExactNetworkError("gate is not exactly unitary")
        before = self.root
        a = self.core(site)
        data = []
        for l in range(a.left):
            for t in range(2):
                for r in range(a.right):
                    acc = ZERO8
                    for s in range(2):
                        g = u[t][s]
                        if not g.is_zero():
                            v = a.at(l, s, r)
                            if not v.is_zero():
                                acc = acc + g * v
                    data.append(acc)
        moved = self._set(site, Core(a.left, 2, a.right, tuple(data)))
        return self._emit(
            "apply_1q",
            before,
            {"site": site, "gate": gate if isinstance(gate, str) else [[v for v in r] for r in u]},
            {"gate_unitary": True, "bonds_unchanged": True, "custody_bytes_written": moved},
        )

    def apply_2q(self, site: int, gate: Any) -> TensorCertificate:
        """Gate on (site, site+1); index order |s_site s_site+1>."""
        self._check_site(site)
        self._check_site(site + 1)
        if isinstance(gate, str):
            if gate not in TWO_QUBIT_GATES:
                raise ExactNetworkError(f"unknown two-qubit gate {gate!r}")
            name, g = gate, TWO_QUBIT_GATES[gate]
        else:
            name, g = None, _gate_matrix(gate, 4)
        if not gate_is_unitary(g):
            raise ExactNetworkError("gate is not exactly unitary")
        before = self.root
        a, b = self.core(site), self.core(site + 1)
        left, right = a.left, b.right
        theta = [[[ZERO8] * right for _ in range(4)] for _ in range(left)]
        for l in range(left):
            for s1 in range(2):
                for k in range(a.right):
                    av = a.at(l, s1, k)
                    if av.is_zero():
                        continue
                    for s2 in range(2):
                        line = theta[l][s1 * 2 + s2]
                        for r in range(right):
                            bv = b.at(k, s2, r)
                            if not bv.is_zero():
                                line[r] = line[r] + av * bv
        m = [[ZERO8] * (2 * right) for _ in range(2 * left)]
        for l in range(left):
            for t in range(4):
                row = m[l * 2 + (t >> 1)]
                col0 = (t & 1) * right
                for s in range(4):
                    gv = g[t][s]
                    if gv.is_zero():
                        continue
                    src = theta[l][s]
                    for r in range(right):
                        if not src[r].is_zero():
                            row[col0 + r] = row[col0 + r] + gv * src[r]
        new_a, new_b = _split(m, left, 2, 2, right)
        moved = self._set(site, new_a) + self._set(site + 1, new_b)
        return self._emit(
            "apply_2q",
            before,
            {"site": site, "gate": name or [[v for v in r] for r in g]},
            {
                "gate_unitary": True,
                "bond_after": new_a.right,
                "bond_is_exact_cut_rank": True,
                "lossless": True,
                "custody_bytes_written": moved,
            },
        )

    def apply_gate_pair(self, first: int, second: int, gate: Any) -> List[TensorCertificate]:
        """Two-qubit gate on any pair, index order |s_first s_second>, via exact SWAPs."""
        self._check_site(first)
        self._check_site(second)
        if first == second:
            raise ExactNetworkError("a two-qubit gate needs two distinct sites")
        g = TWO_QUBIT_GATES[gate] if isinstance(gate, str) else _gate_matrix(gate, 4)
        certs: List[TensorCertificate] = []
        if first < second:
            route = list(range(second - 1, first, -1))
            at, oriented = first, g
        else:
            route = list(range(second, first - 1))
            at = first - 1
            oriented = tuple(
                tuple(
                    sum((SWAP[i][k] * g[k][m] * SWAP[m][j] for k in range(4) for m in range(4)), ZERO8)
                    for j in range(4)
                )
                for i in range(4)
            )
        for s in route:
            certs.append(self.apply_2q(s, "SWAP"))
        certs.append(self.apply_2q(at, oriented))
        for s in reversed(route):
            certs.append(self.apply_2q(s, "SWAP"))
        return certs

    def cnot(self, control: int, target: int) -> List[TensorCertificate]:
        if target == control + 1:
            return [self.apply_2q(control, "CNOT")]
        return self.apply_gate_pair(control, target, "CNOT")

    # -- exact readout -----------------------------------------------------

    def site_density(self, site: int) -> List[List[Q8]]:
        """Unnormalized reduced density matrix of one qubit, exactly."""
        self._check_site(site)
        left = self._left_envs(site)
        right = [[ONE8]]
        for i in range(self.sites - 1, site, -1):
            c = self.core(i)
            right = _transfer_right(right, c, c)
        a = self.core(site)
        rho = [[ZERO8, ZERO8], [ZERO8, ZERO8]]
        for s in range(2):
            for sp in range(2):
                acc = ZERO8
                for l in range(a.left):
                    for lp in range(a.left):
                        e = left[l][lp]
                        if e.is_zero():
                            continue
                        for r in range(a.right):
                            bra = a.at(l, sp, r)
                            if bra.is_zero():
                                continue
                            for rp in range(a.right):
                                f = right[r][rp]
                                ket = a.at(lp, s, rp)
                                if not f.is_zero() and not ket.is_zero():
                                    acc = acc + bra.conjugate() * e * ket * f
                rho[s][sp] = acc
        return rho

    def probability(self, site: int, outcome: int) -> Q8:
        """Exact Born probability of one qubit's outcome, in Q(sqrt 2)."""
        rho = self.site_density(site)
        total = rho[0][0] + rho[1][1]
        value = rho[outcome][outcome] / total
        self._emit("probability", self.root, {"site": site, "outcome": outcome}, {"value": value})
        return value

    def expectation(self, site: int, pauli: str) -> Q8:
        mats = {"X": GATES["X"], "Y": GATES["Y"], "Z": GATES["Z"]}
        if pauli not in mats:
            raise ExactNetworkError("pauli must be X, Y or Z")
        p = _gate_matrix(mats[pauli], 2)
        rho = self.site_density(site)
        total = rho[0][0] + rho[1][1]
        value = sum((p[sp][s] * rho[s][sp] for s in range(2) for sp in range(2)), ZERO8) / total
        self._emit("expectation", self.root, {"site": site, "pauli": pauli}, {"value": value})
        return value

    def cut_purity(self, bond: int) -> Q8:
        """Tr(rho_A^2) for the cut after site ``bond``, exactly in Q(sqrt 2)."""
        if not 0 <= bond < self.sites - 1:
            raise ExactNetworkError("bond must index an internal cut")
        gl = self._left_envs(bond + 1)
        gr = [[ONE8]]
        for i in range(self.sites - 1, bond, -1):
            c = self.core(i)
            gr = _transfer_right(gr, c, c)
        k = len(gl)
        cmat = [[gr[j][i] for j in range(k)] for i in range(k)]
        prod = la.matmul(la.matmul(cmat, gl), la.matmul(cmat, gl))
        norm = la.trace(la.matmul(cmat, gl))
        value = la.trace(prod) / (norm * norm)
        self._emit("cut_purity", self.root, {"bond": bond}, {"value": value})
        return value

    def marginal(self, qubits: Sequence[int], *, max_outcomes: int = 4096) -> Dict[str, Q8]:
        """Exact marginal distribution on ``qubits``, keyed by bitstring in site order.

        Branches on each listed qubit and traces out the rest; zero-weight
        branches are pruned. More than ``max_outcomes`` nonzero outcomes is
        refused rather than truncated.
        """
        sites = sorted({int(q) for q in qubits})
        if not sites:
            raise ExactNetworkError("marginal needs at least one qubit")
        for s in sites:
            self._check_site(s)
        rights = self._right_envs()

        def project(core: Core, s: int) -> Core:
            return Core(core.left, 1, core.right, tuple(
                core.at(l, s, r) for l in range(core.left) for r in range(core.right)
            ))

        frontier: List[Tuple[str, List[List[Q8]], int]] = [("", [[ONE8]], 0)]
        weights: Dict[str, Q8] = {}
        for site in sites:
            grown: List[Tuple[str, List[List[Q8]], int, Q8]] = []
            for key, env, pos in frontier:
                for k in range(pos, site):
                    c = self.core(k)
                    env = _transfer(env, c, c)
                core = self.core(site)
                for s in (0, 1):
                    sub = project(core, s)
                    branch = _transfer(env, sub, sub)
                    tail = rights[site + 1]
                    w = ZERO8
                    for r, row in enumerate(branch):
                        for rp, v in enumerate(row):
                            if not v.is_zero() and not tail[r][rp].is_zero():
                                w = w + v * tail[r][rp]
                    if not w.is_zero():
                        grown.append((key + str(s), branch, site + 1, w))
            if len(grown) > max_outcomes:
                raise ExactNetworkError(
                    f"marginal on {len(sites)} qubits has more than {max_outcomes} outcomes; "
                    "refused rather than truncated"
                )
            frontier = [(k, e, p) for k, e, p, _ in grown]
            weights = {k: w for k, _, _, w in grown}
        total = ZERO8
        for w in weights.values():
            total = total + w
        dist = {k: w / total for k, w in sorted(weights.items())}
        self._emit("marginal", self.root, {"qubits": sites}, {"outcomes": len(dist), "sum_is_one": True})
        return dist

    def schmidt_rank(self, bond: int) -> int:
        """Exact Schmidt rank across the cut after ``bond`` (bonds are minimal)."""
        return self.bonds()[bond + 1]

    def sample(self, seed: int) -> Tuple[int, ...]:
        """Deterministic exact sampling: seeded rationals against exact marginals."""
        rng = random.Random(seed)
        rights = self._right_envs()
        vec = [ONE8]
        bits: List[int] = []
        for i in range(self.sites):
            c = self.core(i)
            weights = []
            branches = []
            for s in range(2):
                w = [
                    sum((vec[l] * c.at(l, s, r) for l in range(c.left) if not vec[l].is_zero()), ZERO8)
                    for r in range(c.right)
                ]
                env = rights[i + 1]
                p = ZERO8
                for r in range(c.right):
                    if w[r].is_zero():
                        continue
                    for rp in range(c.right):
                        if not w[rp].is_zero() and not env[r][rp].is_zero():
                            p = p + w[r].conjugate() * env[r][rp] * w[rp]
                weights.append(p)
                branches.append(w)
            total = weights[0] + weights[1]
            u = Fraction(rng.getrandbits(64), 1 << 64)
            pick = 0 if (Q8.from_fractions(u) * total - weights[0]).sign() < 0 else 1
            if weights[pick].is_zero():
                pick = 1 - pick
            bits.append(pick)
            w = branches[pick]
            pivot = next(v for v in w if not v.is_zero())
            inv = pivot.inverse()
            vec = [v * inv for v in w]
        self._emit("sample", self.root, {"seed": seed}, {"bits_digest": cex_digest(bits)})
        return tuple(bits)


class ExactMPO(ExactTensorTrain):
    """Exact operator train; physical leg packs (out, in) as out * d + in."""

    kind = "mpo"

    def __init__(self, cores: Sequence[Core], *, d: int = 2, **kwargs: Any) -> None:
        self.d = int(d)
        if any(c.phys != self.d * self.d for c in cores):
            raise ExactNetworkError("MPO physical legs must have size d*d")
        super().__init__(cores, **kwargs)

    @classmethod
    def from_local(cls, ops: Sequence[Sequence[Sequence[Any]]], **kwargs: Any) -> "ExactMPO":
        """Bond-one MPO: a tensor product of single-site operators."""
        cores = []
        for op in ops:
            m = [[_q(v) for v in row] for row in op]
            d = len(m)
            cores.append(Core(1, d * d, 1, tuple(m[o][i] for o in range(d) for i in range(d))))
        kwargs.setdefault("genesis", {"kind": "mpo", "from": "local", "sites": len(ops)})
        return cls(cores, d=len(ops[0]), **kwargs)

    @classmethod
    def identity(cls, n: int, d: int = 2, **kwargs: Any) -> "ExactMPO":
        eye = [[ONE8 if i == j else ZERO8 for j in range(d)] for i in range(d)]
        kwargs.setdefault("genesis", {"kind": "mpo", "identity": n, "d": d})
        return cls.from_local([eye] * n, **kwargs)

    @classmethod
    def from_matrix(cls, matrix: Sequence[Sequence[Any]], n: int, d: int = 2, **kwargs: Any) -> "ExactMPO":
        """Exact MPO of a d^n x d^n matrix (exact TT of the interleaved operator)."""
        size = d ** n
        if len(matrix) != size or any(len(r) != size for r in matrix):
            raise ExactNetworkError("matrix size does not match d**n")
        values = []
        for idx in range((d * d) ** n):
            out_digits, in_digits = [], []
            rem = idx
            pairs = []
            for _ in range(n):
                pairs.append(rem % (d * d))
                rem //= d * d
            pairs.reverse()
            for p in pairs:
                out_digits.append(p // d)
                in_digits.append(p % d)
            row = 0
            col = 0
            for o, i in zip(out_digits, in_digits):
                row = row * d + o
                col = col * d + i
            values.append(matrix[row][col])
        tt = ExactTensorTrain.from_dense(values, [d * d] * n, custody=kwargs.get("custody"))
        cores = [tt.core(i) for i in range(tt.sites)]
        kwargs.setdefault("genesis", {"kind": "mpo", "from": "matrix", "n": n, "d": d})
        return cls(cores, d=d, **kwargs)

    def op_at(self, site: int) -> Core:
        return self.core(site)

    def adjoint(self) -> "ExactMPO":
        d = self.d
        cores = []
        for i in range(self.sites):
            c = self.core(i)
            data = [
                c.at(l, i_ * d + o, r).conjugate()
                for l in range(c.left) for o in range(d) for i_ in range(d) for r in range(c.right)
            ]
            cores.append(Core(c.left, d * d, c.right, tuple(data)))
        out = ExactMPO(cores, d=d, custody=self.custody, genesis={"adjoint_of": self.root})
        self._emit("adjoint", self.root, {"result": out.root}, {})
        return out

    def compose(self, other: "ExactMPO") -> "ExactMPO":
        """(self . other)(x) = self(other(x))."""
        if other.sites != self.sites or other.d != self.d:
            raise ExactNetworkError("compose needs matching sites and d")
        d = self.d
        cores = []
        for i in range(self.sites):
            a, b = self.core(i), other.core(i)
            data = []
            for la_ in range(a.left):
                for lb in range(b.left):
                    for o in range(d):
                        for i_ in range(d):
                            for ra in range(a.right):
                                for rb in range(b.right):
                                    acc = ZERO8
                                    for k in range(d):
                                        x = a.at(la_, o * d + k, ra)
                                        y = b.at(lb, k * d + i_, rb)
                                        if not x.is_zero() and not y.is_zero():
                                            acc = acc + x * y
                                    data.append(acc)
            cores.append(Core(a.left * b.left, d * d, a.right * b.right, tuple(data)))
        out = ExactMPO(cores, d=d, custody=self.custody, genesis={"compose": [self.root, other.root]})
        out.compress()
        self._emit("compose", self.root, {"other": other.root, "result": out.root}, {"bonds": out.bonds()})
        return out

    def trace(self) -> Q8:
        d = self.d
        vec = [ONE8]
        for i in range(self.sites):
            c = self.core(i)
            vec = [
                sum(
                    (vec[l] * c.at(l, s * d + s, r) for l in range(c.left) for s in range(d)),
                    ZERO8,
                )
                for r in range(c.right)
            ]
        value = vec[0]
        self._emit("trace", self.root, {}, {"value": value})
        return value

    def hs_inner(self, other: "ExactMPO") -> Q8:
        """Tr(self^dagger other)."""
        with self.adjoint() as adj, adj.compose(other) as prod:
            return prod.trace()

    def is_unitary(self) -> bool:
        """Exact: ||U^dagger U - I||_HS^2 == 0, computed as MPO traces."""
        with self.adjoint() as adj, adj.compose(self) as x:
            dim = Q8(self.d ** self.sites)
            value = x.hs_inner(x) - x.trace() - x.trace().conjugate() + dim
        result = value.is_zero()
        self._emit("is_unitary", self.root, {}, {"hs_residual": value, "unitary": result})
        return result

    def is_hermitian(self) -> bool:
        """Exact: ||H - H^dagger||_HS^2 == 2 Tr(H^dag H) - 2 Re Tr(H H) == 0."""
        hh = self.hs_inner(self)
        with self.compose(self) as square:
            sq = square.trace()
        value = hh + hh - sq - sq.conjugate()
        result = value.is_zero()
        self._emit("is_hermitian", self.root, {}, {"hs_residual": value, "hermitian": result})
        return result

    def apply(self, state: ExactMPS) -> ExactMPS:
        """Exact MPO|psi>: bond product, then structural compression."""
        if state.sites != self.sites or self.d != 2:
            raise ExactNetworkError("MPO and MPS must have matching sites and qubit legs")
        cores = []
        for i in range(self.sites):
            w, a = self.core(i), state.core(i)
            data = []
            for lw in range(w.left):
                for la_ in range(a.left):
                    for o in range(2):
                        for rw in range(w.right):
                            for ra in range(a.right):
                                acc = ZERO8
                                for s in range(2):
                                    x = w.at(lw, o * 2 + s, rw)
                                    y = a.at(la_, s, ra)
                                    if not x.is_zero() and not y.is_zero():
                                        acc = acc + x * y
                                data.append(acc)
            cores.append(Core(w.left * a.left, 2, w.right * a.right, tuple(data)))
        out = ExactMPS(cores, custody=state.custody, genesis={"apply": [self.root, state.root]})
        out.compress()
        state._emit("mpo_apply", state.root, {"mpo": self.root, "result": out.root}, {"bonds": out.bonds()})
        return out


def ising_mpo(n: int, coupling: Any = 1, field: Any = Fraction(1, 2), **kwargs: Any) -> ExactMPO:
    """H = -J sum Z_i Z_{i+1} - h sum X_i as an exact bond-3 MPO."""
    j, h = _q(coupling), _q(field)
    eye = [[ONE8, ZERO8], [ZERO8, ONE8]]
    x = [[ZERO8, ONE8], [ONE8, ZERO8]]
    z = [[ONE8, ZERO8], [ZERO8, -ONE8]]
    zero = [[ZERO8, ZERO8], [ZERO8, ZERO8]]
    neg = lambda m, c: [[-(c * v) for v in row] for row in m]  # noqa: E731
    bulk = [[eye, z, neg(x, h)], [zero, zero, neg(z, j)], [zero, zero, eye]]
    return _mpo_from_blocks(bulk, n, **kwargs)


def heisenberg_mpo(n: int, coupling: Any = 1, **kwargs: Any) -> ExactMPO:
    """H = J sum (X X + Y Y + Z Z) as an exact bond-5 MPO."""
    j = _q(coupling)
    eye = [[ONE8, ZERO8], [ZERO8, ONE8]]
    x = [[ZERO8, ONE8], [ONE8, ZERO8]]
    y = [[ZERO8, -I8], [I8, ZERO8]]
    z = [[ONE8, ZERO8], [ZERO8, -ONE8]]
    zero = [[ZERO8, ZERO8], [ZERO8, ZERO8]]
    sc = lambda m: [[j * v for v in row] for row in m]  # noqa: E731
    bulk = [
        [eye, x, y, z, zero],
        [zero, zero, zero, zero, sc(x)],
        [zero, zero, zero, zero, sc(y)],
        [zero, zero, zero, zero, sc(z)],
        [zero, zero, zero, zero, eye],
    ]
    return _mpo_from_blocks(bulk, n, **kwargs)


def _mpo_from_blocks(bulk: List[List[List[List[Q8]]]], n: int, **kwargs: Any) -> ExactMPO:
    if n < 2:
        raise ExactNetworkError("interaction MPOs need at least two sites")
    w = len(bulk)

    def core(rows: Sequence[int], cols: Sequence[int]) -> Core:
        data = []
        for a in rows:
            for o in range(2):
                for i in range(2):
                    for b in cols:
                        data.append(bulk[a][b][o][i])
        return Core(len(rows), 4, len(cols), tuple(data))

    cores = [core([0], range(w))]
    cores += [core(range(w), range(w)) for _ in range(n - 2)]
    cores.append(core(range(w), [w - 1]))
    kwargs.setdefault("genesis", {"kind": "mpo", "hamiltonian_sites": n, "bond": w})
    return ExactMPO(cores, d=2, **kwargs)


def ghz_circuit(n: int, **kwargs: Any) -> ExactMPS:
    """|GHZ_n> = (|0..0> + |1..1>)/sqrt 2 by H then a CNOT chain, exactly."""
    psi = ExactMPS.zeros(n, **kwargs)
    psi.apply_1q(0, "H")
    for i in range(n - 1):
        psi.apply_2q(i, "CNOT")
    return psi


__all__ = [
    "CNOT",
    "CZ",
    "Core",
    "ExactMPO",
    "ExactMPS",
    "ExactNetworkError",
    "ExactTensorTrain",
    "FIELD",
    "MACHINE",
    "SWAP",
    "decode_core",
    "encode_core",
    "gate_is_unitary",
    "ghz_circuit",
    "heisenberg_mpo",
    "ising_mpo",
]
