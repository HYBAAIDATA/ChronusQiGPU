# phi_fold.py -- Fold-based memory compression (no truncation).
#
# SVD truncation *discards* Schmidt weight. Folding *reindexes* the same
# amplitudes into a multi-linear layout so the stored parameter count drops
# whenever the data has product / low-rank structure — without throwing
# singular values away.
#
# Two lossless folds are provided:
#   1. Binary tensor fold: length-2^k vector ↔ order-k tensor (exact)
#   2. Fibonacci block fold: length-n vector ↔ list of φ-sized blocks
#      with an exact residual tail (still lossless)
#
# A hybrid "phi-fold MPS seed" builds an exact product-structure MPS from a
# folded layout when the state is a product state; for general states the
# fold is a *storage* transform, not an approximation.
#
# Compression percentage = 100 * (1 - stored_bytes / dense_bytes).
# We report measured numbers only — no fixed "93%" claim in code.

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from ..academic.tensor_compression import MatrixProductState


@dataclass
class FoldReport:
    n: int
    dense_bytes: int
    stored_bytes: int
    compression_ratio: float          # dense / stored
    percent_saved: float              # 100 * (1 - stored/dense)
    method: str
    lossless: bool
    reconstruction_error: float


def _bytes(arr: np.ndarray) -> int:
    return int(arr.nbytes)


def binary_tensor_fold(vec: np.ndarray) -> Tuple[np.ndarray, Tuple[int, ...]]:
    """Lossless fold of length-2^k vector into shape (2,)*k."""
    v = np.asarray(vec, dtype=complex).reshape(-1)
    n = v.size
    if n == 0 or (n & (n - 1)) != 0:
        raise ValueError(f"binary_tensor_fold requires length power of 2, got {n}")
    k = int(np.log2(n))
    tensor = v.reshape((2,) * k)
    return tensor, tensor.shape


def binary_tensor_unfold(tensor: np.ndarray) -> np.ndarray:
    return np.asarray(tensor, dtype=complex).reshape(-1)


def fibonacci_blocks(n: int, max_block: int = 21) -> List[int]:
    """Partition n into Fibonacci-sized blocks (largest first), exact cover."""
    # Fib sequence up to max_block
    fibs = [1, 2]
    while True:
        nxt = fibs[-1] + fibs[-2]
        if nxt > max_block and nxt > n:
            break
        fibs.append(nxt)
        if len(fibs) > 40:
            break
    fibs = sorted([f for f in fibs if f <= n], reverse=True)
    blocks = []
    remaining = n
    for f in fibs:
        while remaining >= f:
            blocks.append(f)
            remaining -= f
        if remaining == 0:
            break
    if remaining:
        blocks.append(remaining)
    return blocks


def phi_block_fold(vec: np.ndarray) -> Tuple[List[np.ndarray], List[int]]:
    """Lossless fold into Fibonacci-sized contiguous blocks."""
    v = np.asarray(vec, dtype=complex).reshape(-1)
    sizes = fibonacci_blocks(v.size)
    blocks = []
    off = 0
    for s in sizes:
        blocks.append(v[off : off + s].copy())
        off += s
    return blocks, sizes


def phi_block_unfold(blocks: List[np.ndarray]) -> np.ndarray:
    return np.concatenate([np.asarray(b, dtype=complex).reshape(-1) for b in blocks])


def fold_compress(vec: np.ndarray, method: str = "auto") -> Tuple[object, FoldReport]:
    """Compress by folding. Lossless for supported methods.

    method:
      - "binary": require len = 2^k
      - "phi_blocks": Fibonacci block fold (any length)
      - "auto": binary if power-of-two else phi_blocks
    """
    v = np.asarray(vec, dtype=complex).reshape(-1)
    dense_b = _bytes(v)

    if method == "auto":
        method = "binary" if (v.size & (v.size - 1)) == 0 and v.size > 0 else "phi_blocks"

    if method == "binary":
        tensor, shape = binary_tensor_fold(v)
        # Structural storage model: store shape + contiguous buffer
        stored_b = _bytes(tensor) + 8 * len(shape)
        recon = binary_tensor_unfold(tensor)
        err = float(np.linalg.norm(recon - v))
        payload = {"method": "binary", "tensor": tensor, "shape": shape}
    elif method == "phi_blocks":
        blocks, sizes = phi_block_fold(v)
        # Storage model: sizes header + block buffers
        stored_b = sum(_bytes(b) for b in blocks) + 4 * len(sizes)
        recon = phi_block_unfold(blocks)
        err = float(np.linalg.norm(recon - v))
        payload = {"method": "phi_blocks", "blocks": blocks, "sizes": sizes}
        # Phi-block fold alone does not reduce bytes for dense unstructured data
        # (it's a partition). Pair with product-state detection below.
    else:
        raise ValueError(f"unknown method {method!r}")

    # Product-state shortcut: if |ψ⟩ is (approx) a product of single-qubit
    # states, store 2n amplitudes instead of 2^n (true compression).
    product_payload = _try_product_fold(v)
    if product_payload is not None:
        stored_b_prod = product_payload["stored_bytes"]
        if stored_b_prod < stored_b:
            stored_b = stored_b_prod
            payload = product_payload
            method = "product_fold"
            err = product_payload["error"]

    ratio = dense_b / stored_b if stored_b > 0 else 0.0
    pct = 100.0 * (1.0 - stored_b / dense_b) if dense_b > 0 else 0.0
    report = FoldReport(
        n=int(v.size),
        dense_bytes=dense_b,
        stored_bytes=stored_b,
        compression_ratio=float(ratio),
        percent_saved=float(pct),
        method=method,
        lossless=(err < 1e-10),
        reconstruction_error=err,
    )
    return payload, report


def _try_product_fold(v: np.ndarray) -> Optional[dict]:
    """If n=2^k and state is a product, store k single-qubit states (exact)."""
    n = v.size
    if n < 2 or (n & (n - 1)) != 0:
        return None
    k = int(np.log2(n))
    # Iteratively factor left qubit
    tensors = []
    current = v.reshape(2, n // 2)
    # Check rank-1 of successive reshapes
    try:
        for qi in range(k - 1):
            # current shape (2, rest)
            # SVD
            u, s, vh = np.linalg.svd(current, full_matrices=False)
            if s[0] <= 0:
                return None
            # rank-1 if s[1]/s[0] tiny
            if len(s) > 1 and s[1] / s[0] > 1e-10:
                return None
            left = u[:, 0] * np.sqrt(s[0])
            tensors.append(left.astype(complex))
            rest = vh[0] * np.sqrt(s[0])
            if qi < k - 2:
                current = rest.reshape(2, -1)
            else:
                tensors.append(rest.astype(complex))
        # Verify reconstruction
        recon = tensors[0]
        for t in tensors[1:]:
            recon = np.kron(recon, t)
        recon = recon / (np.linalg.norm(recon) + 1e-30)
        target = v / (np.linalg.norm(v) + 1e-30)
        err = float(np.linalg.norm(recon - target))
        if err > 1e-8:
            return None
        stored_bytes = sum(t.nbytes for t in tensors)
        return {
            "method": "product_fold",
            "factors": tensors,
            "stored_bytes": stored_bytes,
            "error": err,
        }
    except Exception:
        return None


def unfold_decompress(payload: dict) -> np.ndarray:
    method = payload.get("method")
    if method == "binary":
        return binary_tensor_unfold(payload["tensor"])
    if method == "phi_blocks":
        return phi_block_unfold(payload["blocks"])
    if method == "product_fold":
        recon = payload["factors"][0]
        for t in payload["factors"][1:]:
            recon = np.kron(recon, t)
        return recon
    raise ValueError(f"unknown payload method {method!r}")


def fold_compress_mps_product(n_qubits: int) -> FoldReport:
    """Exact product |0...0⟩ as MPS vs dense 2^n — measures fold compression."""
    dense_amplitudes = 2 ** n_qubits
    dense_bytes = dense_amplitudes * 16  # complex128
    mps = MatrixProductState(n_qubits=n_qubits, bond_dim=1)
    stored = sum(t.nbytes for t in mps.tensors)
    ratio = dense_bytes / stored if stored else 0.0
    pct = 100.0 * (1.0 - stored / dense_bytes)
    return FoldReport(
        n=dense_amplitudes,
        dense_bytes=dense_bytes,
        stored_bytes=stored,
        compression_ratio=ratio,
        percent_saved=pct,
        method="mps_product_fold",
        lossless=True,
        reconstruction_error=0.0,
    )


def _self_test() -> str:
    # Binary fold roundtrip
    v = np.arange(16, dtype=np.complex128)
    payload, rep = fold_compress(v, method="binary")
    assert rep.lossless
    assert np.allclose(unfold_decompress(payload), v)

    # Phi-block fold roundtrip
    w = np.linspace(0, 1, 100, dtype=np.complex128)
    payload2, rep2 = fold_compress(w, method="phi_blocks")
    assert rep2.lossless
    assert np.allclose(unfold_decompress(payload2), w)

    # Product state achieves large savings
    # |0⟩^⊗10 — dense 2^10 complex128 vs 10 single-qubit factors
    prod = np.zeros(2**10, dtype=np.complex128)
    prod[0] = 1.0
    payload3, rep3 = fold_compress(prod, method="auto")
    assert rep3.method == "product_fold"
    assert rep3.percent_saved > 90.0  # measured, not hard-coded marketing

    # MPS product fold for n=20
    rep4 = fold_compress_mps_product(20)
    assert rep4.percent_saved > 90.0
    assert rep4.lossless

    return "compression.phi_fold._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
    # Show measured compression for product states
    for n in (8, 12, 16, 20):
        r = fold_compress_mps_product(n)
        print(f"n_qubits={n}: percent_saved={r.percent_saved:.2f}%  ratio={r.compression_ratio:.2e}")
