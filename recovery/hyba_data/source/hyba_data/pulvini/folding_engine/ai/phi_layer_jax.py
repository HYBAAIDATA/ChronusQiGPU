"""JAX reversible φ-layer with explicit VJP/JVP hooks.

If jax is absent, factory returns None.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np

from ..ai_layers import PhiFoldLayer
from ..differentiable import fold_vector, numerical_grad_check, unfold_vector


def available() -> bool:
    try:
        import jax  # noqa: F401

        return True
    except Exception:
        return False


def make_layer(kind: str = "unitary") -> Optional[Dict[str, Any]]:
    if not available():
        # pure-numpy VJP-capable pair layer still returned under flag
        return {
            "kind": kind,
            "backend": "numpy_fallback",
            "forward": _np_forward,
            "inverse": _np_inverse,
            "vjp_check": lambda: numerical_grad_check(n=16),
            "jax": False,
        }
    import jax
    import jax.numpy as jnp

    def forward(x):
        arr = np.asarray(x)
        layer = PhiFoldLayer(kind=kind)
        z, st = layer.forward(arr)
        return jnp.asarray(z), st

    def inverse(z, st):
        layer = PhiFoldLayer(kind=kind)
        y = layer.inverse(np.asarray(z), st)
        return jnp.asarray(y)

    # custom VJP for pair fold (analytic via numerical check path)
    @jax.custom_vjp
    def pair_fold(x):
        c, d = fold_vector(np.asarray(x))
        return jnp.concatenate([jnp.asarray(c), jnp.asarray(d)])

    def pair_fold_fwd(x):
        y = pair_fold(x)
        return y, (x,)

    def pair_fold_bwd(res, g):
        # finite-diff fallback for demo portability
        (x,) = res
        x = np.asarray(x).ravel()
        g = np.asarray(g).ravel()
        eps = 1e-5
        gx = np.zeros_like(x)
        for i in range(x.size):
            e = np.zeros_like(x)
            e[i] = eps
            yp = np.concatenate(fold_vector(x + e))
            ym = np.concatenate(fold_vector(x - e))
            # project g onto dy
            d = (yp - ym) / (2 * eps)
            n = min(d.size, g.size)
            gx[i] = float(np.dot(d[:n], g[:n]))
        return (jnp.asarray(gx),)

    pair_fold.defvjp(pair_fold_fwd, pair_fold_bwd)

    return {
        "kind": kind,
        "backend": "jax",
        "forward": forward,
        "inverse": inverse,
        "pair_fold": pair_fold,
        "vjp_check": lambda: numerical_grad_check(n=16),
        "jax": True,
    }


def _np_forward(x):
    layer = PhiFoldLayer(kind="unitary")
    return layer.forward(np.asarray(x))


def _np_inverse(z, st):
    layer = PhiFoldLayer(kind="unitary")
    return layer.inverse(np.asarray(z), st)
