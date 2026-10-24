"""Mini training loop using φ-layer on MNIST-like digits (synthetic 8x8 digits).

No torchvision required. Pure NumPy SGD on features after φ-fold embedding.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

import numpy as np

from ..ai_layers import PhiFoldLayer
from ..embeddings import phi_embed, phi_unembed


@dataclass
class TrainResult:
    steps: int
    final_loss: float
    final_acc: float
    embed_roundtrip_err: float
    history: List[Dict[str, float]] = field(default_factory=list)
    claims: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _make_digits(n_per_class: int = 20, seed: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """8x8 synthetic digit-like blobs for 10 classes."""
    rng = np.random.default_rng(seed)
    xs, ys = [], []
    yy, xx = np.mgrid[0:8, 0:8]
    for c in range(10):
        for _ in range(n_per_class):
            img = np.zeros((8, 8), dtype=np.float64)
            # class-dependent strokes
            img += 0.3 * np.sin((xx + c) * 0.7) * np.cos((yy - c) * 0.5)
            cx, cy = 2 + (c % 4), 2 + (c // 3)
            img += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (1.2 + 0.1 * c)))
            img += 0.05 * rng.normal(size=img.shape)
            xs.append(img.ravel())
            ys.append(c)
    X = np.stack(xs, axis=0)
    y = np.asarray(ys, dtype=np.int64)
    # shuffle
    idx = rng.permutation(len(y))
    return X[idx], y[idx]


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / (e.sum(axis=1, keepdims=True) + 1e-12)


def train_phi_layer_classifier(
    steps: int = 60,
    lr: float = 0.3,
    seed: int = 0,
    embed_kind: str = "unitary",
) -> TrainResult:
    X, y = _make_digits(seed=seed)
    # embed each sample via φ-layer
    layer = PhiFoldLayer(kind=embed_kind if embed_kind != "pair" else "unitary")
    Z = []
    for i in range(X.shape[0]):
        z, _ = layer.forward(X[i])
        Z.append(np.asarray(z, dtype=np.float64).ravel())
    # pad to equal length
    m = max(z.size for z in Z)
    Zp = np.zeros((len(Z), m), dtype=np.float64)
    for i, z in enumerate(Z):
        Zp[i, : z.size] = z
    # standardize
    mu, sd = Zp.mean(0), Zp.std(0) + 1e-8
    Zp = (Zp - mu) / sd

    n_classes = 10
    rng = np.random.default_rng(seed)
    W = rng.normal(0, 0.05, size=(n_classes, m))
    b = np.zeros(n_classes)
    history = []
    for step in range(steps):
        logits = Zp @ W.T + b
        p = _softmax(logits)
        # loss
        n = y.size
        loss = float(-np.log(p[np.arange(n), y] + 1e-12).mean())
        acc = float(np.mean(np.argmax(p, axis=1) == y))
        # grad
        p[np.arange(n), y] -= 1.0
        p /= n
        gW = p.T @ Zp
        gb = p.sum(axis=0)
        W -= lr * gW
        b -= lr * gb
        history.append({"step": step, "loss": loss, "acc": acc})

    # embed invertibility check on first sample
    emb = phi_embed(X[0].reshape(8, 8), kind="unitary")
    rec = phi_unembed(emb)
    err = float(np.max(np.abs(X[0].reshape(8, 8) - rec)))

    return TrainResult(
        steps=steps,
        final_loss=history[-1]["loss"],
        final_acc=history[-1]["acc"],
        embed_roundtrip_err=err,
        history=history[:: max(1, steps // 10)],
        claims={
            "real_mnist_download": False,
            "synthetic_8x8_digits": True,
            "phi_layer_embedding": True,
            "torch_required": False,
        },
    )
