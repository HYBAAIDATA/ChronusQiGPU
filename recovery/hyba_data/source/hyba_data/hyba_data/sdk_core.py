"""PHI-1 Core SDK — free-tier / PyPI surface (M1 demos only).

External-safe: fold/unfold/verify on structured demos; M1 + sensitivity language.
Does not expose M2/M3 as product guarantees.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

import numpy as np

from hyba_data.external_metrics import M1_RATIO, SENSITIVITY_M, external_metric_pack
from hyba_data.phi1_runtime import Phi1Runtime

ArrayLike = Union[np.ndarray, list]

__all__ = [
    "fold",
    "unfold",
    "verify",
    "demo_m1",
    "external_metrics",
    "Phi1Core",
    "VERSION",
]

VERSION = "0.1.0-core"


class Phi1Core:
    def __init__(self, max_err: float = 1e-5):
        self.rt = Phi1Runtime(max_err_gate=max_err)

    def fold(
        self,
        data: ArrayLike,
        *,
        mode: str = "cf_tower",
        depth: int = 1,
    ) -> Dict[str, Any]:
        """Fold data. Free tier default depth=1 (M1 class)."""
        if depth > 2:
            # free tier discourages advertising depth-4 M2 as product guarantee
            pass
        return self.rt.phi_fold_write(data, mode=mode, depth=depth)

    def unfold(self, handle_id: str) -> Dict[str, Any]:
        return self.rt.phi_unfold_read(handle_id)

    def verify(self, handle_id: str) -> Dict[str, Any]:
        return self.rt.phi_verify(handle_id)


_default: Optional[Phi1Core] = None


def _core() -> Phi1Core:
    global _default
    if _default is None:
        _default = Phi1Core()
    return _default


def fold(data: ArrayLike, **kwargs) -> Dict[str, Any]:
    return _core().fold(data, **kwargs)


def unfold(handle_id: str) -> Dict[str, Any]:
    return _core().unfold(handle_id)


def verify(handle_id: str) -> Dict[str, Any]:
    return _core().verify(handle_id)


def external_metrics() -> Dict[str, Any]:
    return external_metric_pack()


def demo_m1(n: int = 256, seed: int = 0) -> Dict[str, Any]:
    """M1-class demo: structured sine, depth-1 fold, recon gate."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 8 * np.pi, n)
    x = np.sin(t) + 0.01 * rng.normal(size=n)
    c = Phi1Core()
    w = c.fold(x, mode="cf_tower", depth=1)
    u = c.unfold(w["handle"]["handle_id"])
    y = np.asarray(u["data"], dtype=np.float64)
    err = float(np.max(np.abs(y[: x.size] - x)))
    return {
        "version": VERSION,
        "m1_ratio_doctrine": M1_RATIO,
        "sensitivity_m": list(SENSITIVITY_M),
        "passed_gate": w["passed_gate"],
        "recon_error": err,
        "cert": w["cert"],
        "tier": "free_core",
        "not_claimed": ["M2 6.85× fleet", "M3 7.155×", "universal compression"],
    }
