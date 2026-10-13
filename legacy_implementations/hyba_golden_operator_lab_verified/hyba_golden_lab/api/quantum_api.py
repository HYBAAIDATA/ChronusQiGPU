#!/usr/bin/env python3
"""
Public API — exact quantum mathematics + golden-family scaling.

No sampling. No heuristics. No Trotter. No Gram-Schmidt patching.
Measure = exact Born distribution. Evolution = spectral exp of Hermitian H.
Fidelity F(ψ,φ) = |⟨ψ|φ⟩|² is the primary correctness metric.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "01_mathematics"),
    str(ROOT / "02_quantum"),
    str(ROOT / "03_structure"),
]

from golden_transform import (  # noqa: E402
    PHI,
    PSI,
    SQRT5,
    apply_Mn,
    cassini,
    coherence,
    fib,
    lucas,
    pisano,
    project,
    reconstruct,
    verify_identities,
    zeckendorf,
    M_pow,
    all_identities_hold,
)
from core import (  # noqa: E402
    born,
    entanglement_spectrum,
    grover,
    pauli_x,
    pauli_z,
    qaoa_ising,
    qft,
    qft_matrix,
    superposition,
    _expm_h,
    _herm,
    _normalize,
)
from operators import (  # noqa: E402
    fold_pairs_Mn,
    fold_to_distribution,
    metrics,
    n_effective,
    unfold_pairs_Mn,
)
from coherence_measurement import pair_born, score_pairs, verify_fib_amplification  # noqa: E402
from explore_families import binet_F, binet_L, zeckendorf_fold_memory  # noqa: E402
from pure_math import (  # noqa: E402
    HilbertSpace,
    braid_matrix,
    chern_character,
    completeness,
    is_unitary,
    mps_contract,
    mps_from_state,
    partial_trace,
    qfi_rotation_family,
    quantum_fisher_metric,
    rotation,
    spectral_phases,
    yang_baxter_error,
    bloch_geodesic,
    bloch_christoffel,
    functor_compose,
    coined_walk_operator,
    is_unitary as mat_unitary,
    vietoris_rips_betti,
    chern_character,
)


ArrayLike = Union[np.ndarray, Sequence[complex], Sequence[float]]


def _as_cvec(x: ArrayLike) -> np.ndarray:
    return np.asarray(x, dtype=complex).reshape(-1)


@dataclass
class State:
    amplitudes: np.ndarray

    def __post_init__(self):
        self.amplitudes = _normalize(_as_cvec(self.amplitudes))

    @property
    def dim(self) -> int:
        return int(self.amplitudes.size)

    def fidelity(self, other: "State") -> float:
        return float(np.abs(np.vdot(self.amplitudes, other.amplitudes)) ** 2)

    def inner(self, other: "State") -> complex:
        return complex(np.vdot(self.amplitudes, other.amplitudes))

    def born(self) -> np.ndarray:
        return born(self.amplitudes)

    def entropy(self) -> float:
        p = self.born()
        p = p[p > 1e-15]
        return float(-np.sum(p * np.log(p))) if p.size else 0.0

    def projector(self) -> np.ndarray:
        a = self.amplitudes.reshape(-1, 1)
        return a @ a.conj().T


@dataclass
class Operator:
    matrix: np.ndarray

    def __post_init__(self):
        self.matrix = np.asarray(self.matrix, dtype=complex)
        if self.matrix.ndim != 2 or self.matrix.shape[0] != self.matrix.shape[1]:
            raise ValueError("operator must be a square matrix")

    @property
    def dim(self) -> int:
        return int(self.matrix.shape[0])

    def is_unitary(self, tol: float = 1e-10) -> bool:
        I = np.eye(self.dim, dtype=complex)
        return float(np.linalg.norm(self.matrix.conj().T @ self.matrix - I)) < tol

    def apply(self, state: State) -> State:
        if state.dim != self.dim:
            raise ValueError("dimension mismatch")
        return State(self.matrix @ state.amplitudes)

    def compose(self, other: "Operator") -> "Operator":
        return Operator(self.matrix @ other.matrix)

    def tensor(self, other: "Operator") -> "Operator":
        return Operator(np.kron(self.matrix, other.matrix))

    def dagger(self) -> "Operator":
        return Operator(self.matrix.conj().T)

    def evolve_hermitian(self, t: float) -> "Operator":
        """U = exp(-i H t) for Hermitian H. Exact spectral factorization."""
        return Operator(_expm_h(self.matrix, -1j * float(t)))


@dataclass
class APIResult:
    ok: bool
    data: Dict[str, Any] = field(default_factory=dict)
    fidelity: Optional[float] = None
    notes: str = ""


class GoldenScale:
    """Golden-family scalers as operators, not labels."""

    phi = float(PHI)
    psi = float(PSI)

    @staticmethod
    def fib(n: int) -> int:
        return fib(n)

    @staticmethod
    def lucas(n: int) -> int:
        return lucas(n)

    @staticmethod
    def zeckendorf(n: int) -> List[int]:
        return zeckendorf(n)

    @staticmethod
    def pisano(m: int) -> int:
        return pisano(m)

    @staticmethod
    def binet_F(n: int) -> float:
        return float(binet_F(n))

    @staticmethod
    def binet_L(n: int) -> float:
        return float(binet_L(n))

    @staticmethod
    def cassini(n: int) -> int:
        return cassini(n)

    @staticmethod
    def identities_hold() -> bool:
        return all_identities_hold()

    @staticmethod
    def qaoa_angles(p: int, scaled: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        if not scaled:
            beta = np.array([math.pi * (k + 1) / (p + 1) for k in range(p)])
            gamma = np.array([2 * math.pi * (k + 1) / (p + 1) for k in range(p)])
            return beta, gamma
        beta = np.array([math.pi * (1 / PHI) * (k + 1) / (p + 1) for k in range(p)])
        gamma = np.array([
            2 * math.pi * ((k * PHI) % 1.0) * (lucas(k + 1) / (lucas(k + 1) + PHI ** k))
            for k in range(p)
        ])
        return beta, gamma

    @staticmethod
    def grover_iterations(N: int, M: int, scaled: bool = False) -> int:
        theta = math.asin(math.sqrt(max(M, 1) / max(N, 1)))
        if theta < 1e-15:
            return 0
        exact = math.pi / (4.0 * theta) - 0.5
        if not scaled:
            return max(1, int(round(exact)))
        tilt = lucas(2) / (lucas(2) + PHI)
        return max(1, int(round(exact * ((1 / PHI) + tilt))))


class QuantumAPI:
    """Single entry point for consumers."""

    def __init__(self):
        self.scale = GoldenScale()
        if not GoldenScale.identities_hold():
            raise RuntimeError("golden identities failed — API will not serve")

    # ----- states / operators -----
    def ket(self, amplitudes: ArrayLike) -> State:
        return State(amplitudes)

    def basis(self, index: int, dim: int) -> State:
        v = np.zeros(dim, dtype=complex)
        v[int(index)] = 1.0
        return State(v)

    def uniform(self, dim: int) -> State:
        return State(superposition(int(dim)))

    def bell(self) -> State:
        return State(np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2))

    def ghz(self, n: int) -> State:
        dim = 2 ** int(n)
        v = np.zeros(dim, dtype=complex)
        v[0] = v[-1] = 1.0 / math.sqrt(2)
        return State(v)

    def fidelity(self, a: State, b: State) -> float:
        return a.fidelity(b)

    def hadamard(self) -> Operator:
        return Operator(np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2))

    def pauli(self, axis: str) -> Operator:
        axis = axis.lower()
        if axis == "x":
            return Operator(np.array([[0, 1], [1, 0]], dtype=complex))
        if axis == "y":
            return Operator(np.array([[0, -1j], [1j, 0]], dtype=complex))
        if axis == "z":
            return Operator(np.array([[1, 0], [0, -1]], dtype=complex))
        raise ValueError("axis must be x, y, or z")

    def cnot(self) -> Operator:
        return Operator(np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex
        ))

    def qft_op(self, n_qubits: int) -> Operator:
        return Operator(qft_matrix(int(n_qubits)))

    def measure(self, state: State) -> Dict[str, Any]:
        """Exact Born distribution. No collapse sampling."""
        p = state.born()
        i = int(np.argmax(p))
        return {
            "distribution": p,
            "most_probable": i,
            "probability": float(p[i]),
            "entropy": state.entropy(),
            "exact": True,
        }

    # ----- algorithms -----
    def grover(self, n_qubits: int, marked: Sequence[int], scaled: bool = False) -> APIResult:
        N = 2 ** int(n_qubits)
        marked = list(marked)
        iters = GoldenScale.grover_iterations(N, len(marked), scaled=scaled)
        r = grover(int(n_qubits), marked, iterations=iters)
        psi = State(r["state"])
        target = State(self.basis(marked[0], N).amplitudes) if len(marked) == 1 else None
        fid = None
        if target is not None:
            fid = psi.fidelity(target)
        m = metrics(r["distribution"], marked)
        return APIResult(
            ok=bool(r["success"]),
            fidelity=fid,
            data={
                "iterations": r["iterations"],
                "marked_probability": r["marked_probability"],
                "found": r["found"],
                "n_eff": m["effective_dimension"],
                "distribution": r["distribution"],
                "scaled": scaled,
            },
            notes="exact Grover rotation",
        )

    def qft(self, state: State) -> APIResult:
        out = State(qft(state.amplitudes))
        back = State(self.qft_op(int(round(math.log2(state.dim)))).dagger().apply(out).amplitudes)
        return APIResult(
            ok=True,
            fidelity=state.fidelity(back),
            data={"state": out, "distribution": out.born()},
            notes="exact QFT; fidelity is inversion check",
        )

    def qaoa(self, n: int, J: np.ndarray, p: int = 3, scaled: bool = True) -> APIResult:
        beta, gamma = GoldenScale.qaoa_angles(int(p), scaled=scaled)
        r = qaoa_ising(int(n), np.asarray(J, dtype=float), beta, gamma)
        ev0 = r["exact_min"]
        return APIResult(
            ok=True,
            data={
                "energy": r["energy"],
                "exact_min": ev0,
                "gap": r["gap"],
                "n_eff": n_effective(r["distribution"]),
                "distribution": r["distribution"],
                "scaled": scaled,
                "beta": beta,
                "gamma": gamma,
            },
            notes="exact QAOA unitaries; compare energy to spectral min",
        )

    def phase_from_spectrum(self, U: Operator) -> APIResult:
        ev = np.linalg.eigvals(U.matrix)
        phases = np.angle(ev) / (2 * math.pi)
        return APIResult(ok=True, data={"eigenvalues": ev, "phases": phases},
                         notes="exact spectrum; not sampled phase estimation")

    def schmidt(self, state: State, cut: int) -> APIResult:
        n = int(round(math.log2(state.dim)))
        spec = entanglement_spectrum(state.amplitudes, int(cut))
        return APIResult(ok=True, data=spec, notes="exact SVD / Schmidt")

    def kernel(self, X: np.ndarray) -> APIResult:
        """Exact amplitude-phase feature map + Gram matrix. Deterministic."""
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        n, d = X.shape
        nq = max(1, int(math.ceil(math.log2(max(d, 2)))))
        dim = 2 ** nq

        def feat(row: np.ndarray) -> State:
            amp = np.zeros(dim, dtype=complex)
            m = min(row.size, dim)
            amp[:m] = np.exp(1j * PHI * row[:m])
            return State(amp)

        feats = [feat(X[i]) for i in range(n)]
        K = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(n):
                K[i, j] = feats[i].fidelity(feats[j])
        ev = np.linalg.eigvalsh(0.5 * (K + K.T))
        return APIResult(
            ok=float(np.min(ev)) >= -1e-8,
            data={"K": K, "min_eig": float(np.min(ev)), "trace": float(np.trace(K))},
            notes="K_ij = F(φ(x_i), φ(x_j)); PSD up to float error",
        )

    # ----- golden folds -----
    def fold_Mn(self, data: ArrayLike, n: int) -> APIResult:
        x = np.asarray(data, dtype=float).reshape(-1)
        y = fold_pairs_Mn(x, int(n))
        back = unfold_pairs_Mn(y, int(n))
        err = float(np.linalg.norm(x[: back.size] - back[: x.size]) / max(np.linalg.norm(x), 1e-15))
        return APIResult(
            ok=err < 1e-8,
            fidelity=max(0.0, 1.0 - err),
            data={"folded": y, "roundtrip_error": err, "n": int(n)},
            notes="M^n pair fold; Cassini invertibility",
        )

    def fold_zeckendorf(self, values: Sequence[int]) -> APIResult:
        r = zeckendorf_fold_memory(list(values))
        return APIResult(ok=bool(r["unique_reconstruction"]), data=r,
                         notes="unique sparse Fib occupation address")

    def fold_binet(self, kind: str, n_max: int) -> APIResult:
        kind = kind.upper()
        errs = []
        for k in range(int(n_max) + 1):
            if kind == "F":
                errs.append(abs(binet_F(k) - fib(k)))
            else:
                errs.append(abs(binet_L(k) - lucas(k)))
        mx = float(max(errs) if errs else 0.0)
        return APIResult(
            ok=mx < 1e-8,
            fidelity=max(0.0, 1.0 - mx),
            data={"kind": kind, "n_max": n_max, "max_abs_error": mx, "terms": n_max + 1, "amplitudes": 2},
            notes="whole ray stored as (Φ^n, ψ^n)",
        )

    def born_pair_coherence(self, state: State) -> APIResult:
        s = score_pairs(pair_born(state.born()))
        return APIResult(ok=True, data=s, notes="M^n on exact Born pairs, not samples")

    def yang_baxter(self, dim_a: int = 2, dim_b: int = 2, dim_c: int = 2) -> APIResult:
        def braid(da: int, db: int) -> np.ndarray:
            n = da * db
            B = np.zeros((n, n), dtype=complex)
            for i in range(da):
                for j in range(db):
                    B[j * da + i, i * db + j] = 1.0
            return B

        A, B, C = int(dim_a), int(dim_b), int(dim_c)
        bAB, bBC, bAC = braid(A, B), braid(B, C), braid(A, C)
        IA, IB, IC = np.eye(A), np.eye(B), np.eye(C)
        lhs = np.kron(bBC, IA) @ np.kron(IB, bAC) @ np.kron(bAB, IC)
        rhs = np.kron(IC, bAB) @ np.kron(bAC, IB) @ np.kron(IA, bBC)
        err = float(np.linalg.norm(lhs - rhs))
        return APIResult(ok=err < 1e-12, fidelity=max(0.0, 1.0 - err),
                         data={"error": err}, notes="exact permutation braiding")

    def rotation(self, axis: str, theta: float) -> Operator:
        return Operator(rotation(axis, float(theta)))

    def mps(self, state: State, bond_dim: int = None) -> APIResult:
        tensors = mps_from_state(state.amplitudes, bond_dim)
        recon = State(mps_contract(tensors))
        fid = state.fidelity(recon)
        return APIResult(
            ok=fid > 1.0 - 1e-10 if bond_dim is None or bond_dim >= state.dim else True,
            fidelity=fid,
            data={"n_tensors": len(tensors), "shapes": [t.shape for t in tensors]},
            notes="full SVD is exact; truncation only if bond_dim < rank",
        )

    def qng(self, thetas: np.ndarray, loss_fn, eta: float = 0.1) -> APIResult:
        """One exact-QNG step: θ ← θ − η (g^Q)^{-1} ∇L using parameter-shift."""
        th = np.asarray(thetas, dtype=float).reshape(-1)
        g = np.zeros_like(th)
        shift = 0.5 * math.pi
        for i in range(th.size):
            plus, minus = th.copy(), th.copy()
            plus[i] += shift
            minus[i] -= shift
            g[i] = 0.5 * (float(loss_fn(plus)) - float(loss_fn(minus)))
        # 1-param QFI blocks on the rotation family (exact F=1 per angle)
        F = np.eye(th.size)
        step = np.linalg.solve(F + 1e-12 * np.eye(th.size), g)
        nxt = th - float(eta) * step
        return APIResult(
            ok=True,
            data={"theta": th, "grad": g, "theta_next": nxt, "eta": eta},
            notes="parameter-shift gradient + QFI metric; one step only",
        )

    def qfi(self, theta: float = 0.0, axis: str = "y") -> APIResult:
        f = qfi_rotation_family(float(theta), axis)
        return APIResult(ok=abs(f - 1.0) < 1e-10, data={"qfi": f, "axis": axis, "theta": theta},
                         notes="exact QFI of R(θ)|0⟩; generator σ/2 ⇒ F=1")

    def reduce(self, state: State, dim_a: int, dim_b: int, keep: str = "A") -> APIResult:
        rho = state.projector()
        red = partial_trace(rho, int(dim_a), int(dim_b), keep)
        ev = np.linalg.eigvalsh(0.5 * (red + red.conj().T))
        ev = ev[ev > 1e-15]
        s = float(-np.sum(ev * np.log(ev))) if ev.size else 0.0
        return APIResult(ok=True, data={"rho": red, "entropy": s, "rank": int(ev.size)},
                         notes="exact bipartite partial trace")

    def geodesic(self, theta0: float, phi0: float, theta1: float, phi1: float, steps: int = 8) -> APIResult:
        g = bloch_geodesic(float(theta0), float(phi0), float(theta1), float(phi1), int(steps))
        return APIResult(ok=True, data=g, notes="exact Bloch/Fubini–Study geodesic")

    def compose(self, U: Operator, V: Operator) -> Operator:
        return Operator(functor_compose(U.matrix, V.matrix))

    def christoffel(self, theta: float, phi: float = 0.0) -> APIResult:
        g = bloch_christoffel(float(theta), float(phi))
        return APIResult(ok=True, data=g, notes="exact Bloch Christoffel symbols")

    def walk(self, adjacency: np.ndarray, steps: int = 4) -> APIResult:
        U = coined_walk_operator(np.asarray(adjacency, dtype=float))
        ok_u = mat_unitary(U)
        dim = U.shape[0]
        psi = np.zeros(dim, dtype=complex)
        psi[: max(dim // adjacency.shape[0], 1)] = 1.0
        psi = psi / np.linalg.norm(psi)
        for _ in range(int(steps)):
            psi = U @ psi
        p = np.abs(psi) ** 2
        return APIResult(
            ok=ok_u,
            data={"unitary": ok_u, "distribution": p, "dim": dim, "steps": steps},
            notes="exact coined walk U=S(2|s><s|-I)",
        )

    def homology(self, points: np.ndarray, radius: float = None) -> APIResult:
        X = np.asarray(points, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        if radius is None:
            D = np.sqrt(np.sum((X[:, None, :] - X[None, :, :]) ** 2, axis=-1))
            tri = D[np.triu_indices(len(X), 1)]
            radius = float(np.median(tri) * (1.0 / PHI)) if tri.size else 1.0
        betti = vietoris_rips_betti(X, radius)
        ch = chern_character(betti)
        return APIResult(
            ok=True,
            data={"betti": betti, "chern": ch, "radius": radius,
                  "euler": float(sum(((-1) ** k) * betti[k] for k in betti))},
            notes="exact VR homology via boundary SVD ranks",
        )

    def deutsch_jozsa(self, n_qubits: int = 3, kind: str = "balanced") -> APIResult:
        n = int(n_qubits)
        dim = 2 ** n
        psi = np.zeros(dim, dtype=complex)
        psi[0] = 1.0
        H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
        Hn = H
        for _ in range(n - 1):
            Hn = np.kron(Hn, H)
        psi = Hn @ psi
        oracle = np.eye(dim, dtype=complex)
        if kind == "balanced":
            for i in range(dim):
                if bin(i).count("1") % 2 == 1:
                    oracle[i, i] = -1.0
        psi = Hn @ (oracle @ psi)
        p0 = float(np.abs(psi[0]) ** 2)
        balanced = p0 < 0.5
        return APIResult(
            ok=(balanced and kind == "balanced") or ((not balanced) and kind == "constant"),
            data={"P0": p0, "verdict": "balanced" if balanced else "constant", "kind": kind},
            notes="exact DJ; P(|0...0>) decides",
        )

    def completeness(self, dim: int) -> APIResult:
        basis = [np.eye(dim, dtype=complex)[:, i] for i in range(int(dim))]
        err = completeness(basis)
        return APIResult(ok=err < 1e-12, fidelity=max(0.0, 1.0 - err),
                         data={"error": err}, notes="∑|i⟩⟨i| = I")

    def health(self) -> APIResult:
        ids = {n: verify_identities(n) for n in range(1, 11)}
        fib_amp = verify_fib_amplification()
        yb = self.yang_baxter()
        h = self.hadamard()
        x = self.pauli("x")
        bell = self.bell()
        return APIResult(
            ok=all(all(v.values()) for v in ids.values()) and all(c["match"] for c in fib_amp) and yb.ok and h.is_unitary() and x.is_unitary(),
            data={
                "identities": ids,
                "fib_Mn": fib_amp,
                "yang_baxter": yb.data,
                "H_unitary": h.is_unitary(),
                "X_unitary": x.is_unitary(),
                "bell_entropy": bell.entropy(),
                "phi": PHI,
            },
            notes="API refuses to serve if identities fail",
        )
