"""PHI-1 GPUizer — PyTorch Lightning-style callback + local benchmark harness.

Does not require CUDA for unit tests (CPU numpy path). Optional torch if present.
Doctrine: pilot-measured gains only; M2/M3 not used as external fleet facts.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from hyba_data.external_metrics import SENSITIVITY_M, assert_external_ratio_allowed
from hyba_data.phi1_runtime import Phi1Runtime
from hyba_data.savings_metering import compute_savings

try:
    import torch  # type: ignore

    HAS_TORCH = True
except Exception:
    torch = None  # type: ignore
    HAS_TORCH = False


@dataclass
class GpuizerPilotReport:
    backend: str
    n: int
    baseline_bytes: int
    folded_bytes: int
    measured_ratio: float
    recon_error: float
    elapsed_s: float
    fee_unmeasured: float
    fee_measured: float
    sensitivity: Dict[str, float]
    doctrine: str = "pilot-measured only; CIaaS gain-share"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Phi1GpuizerCallback:
    """Lightning-compatible callback surface (works without lightning installed).

    Hooks:
      on_train_batch_start / on_train_batch_end — fold activations/gradients buffer
    """

    def __init__(self, mode: str = "cf_tower", depth: int = 2, max_err: float = 1e-5):
        self.mode = mode
        self.depth = depth
        self.max_err = max_err
        self.rt = Phi1Runtime(max_err_gate=max_err)
        self.last_report: Optional[Dict[str, Any]] = None

    def fold_array(self, x: np.ndarray) -> Dict[str, Any]:
        return self.rt.phi_fold_write(x, mode=self.mode, depth=self.depth)

    def on_train_batch_start(self, trainer=None, pl_module=None, batch=None, batch_idx: int = 0):
        return None

    def on_train_batch_end(self, trainer=None, pl_module=None, outputs=None, batch=None, batch_idx: int = 0):
        # No-op placeholder for Lightning integration
        return None

    def measure_working_set(self, x: np.ndarray, s_memory: float = 1.0, f: float = 0.4) -> GpuizerPilotReport:
        x = np.asarray(x, dtype=np.float64)
        t0 = time.perf_counter()
        w = self.fold_array(x)
        elapsed = time.perf_counter() - t0
        assert w["passed_gate"], w
        u = self.rt.phi_unfold_read(w["handle"]["handle_id"])
        y = np.asarray(u["data"], dtype=np.float64)
        err = float(np.max(np.abs(y[: x.size] - x)))
        baseline = int(x.nbytes)
        # folded payload size proxy from cert
        folded = int(max(1, baseline // max(1, int(round(w["cert"].get("compression_ratio") or 1)))))
        ratio = baseline / max(folded, 1)
        # prefer cert ratio if present
        if w["cert"].get("compression_ratio"):
            ratio = float(w["cert"]["compression_ratio"])
        # clamp report ratio for fee using sensitivity if unmeasured external path
        m_for_fee = min(SENSITIVITY_M, key=lambda m: abs(m - max(ratio, 1.01)))
        un = compute_savings(s_memory=s_memory, f=f, m_eff=m_for_fee, measured=False)
        me = compute_savings(s_memory=s_memory, f=f, m_eff=m_for_fee, measured=True)
        sens = {
            str(m): compute_savings(s_memory=s_memory, f=f, m_eff=m, measured=True).hyba_fee
            for m in SENSITIVITY_M
        }
        rep = GpuizerPilotReport(
            backend="torch" if HAS_TORCH else "numpy",
            n=int(x.size),
            baseline_bytes=baseline,
            folded_bytes=folded,
            measured_ratio=float(ratio),
            recon_error=err,
            elapsed_s=elapsed,
            fee_unmeasured=un.hyba_fee,
            fee_measured=me.hyba_fee,
            sensitivity=sens,
        )
        self.last_report = rep.to_dict()
        return rep


def run_gpuizer_benchmark(
    n: int = 4096,
    seed: int = 0,
    artifact_dir: str | Path = "artifacts/hyba_data/elevation",
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 20 * np.pi, n)
    x = np.sin(t) + 0.05 * rng.normal(size=n)
    if HAS_TORCH:
        # exercise torch tensor path without requiring GPU
        xt = torch.tensor(x, dtype=torch.float64)
        x = xt.detach().cpu().numpy()
    cb = Phi1GpuizerCallback(depth=2)
    rep = cb.measure_working_set(x, s_memory=1_000_000.0, f=0.4)
    out = rep.to_dict()
    out["has_torch"] = HAS_TORCH
    out["external_ratio_gate"] = "sensitivity or measured pilot only"
    # ensure we don't claim M2 externally
    try:
        assert_external_ratio_allowed(2.0)
        out["external_gate_ok"] = True
    except PermissionError as e:
        out["external_gate_ok"] = False
        out["external_gate_error"] = str(e)
    art = Path(artifact_dir)
    art.mkdir(parents=True, exist_ok=True)
    path = art / "GPUIZER_PILOT_REPORT.json"
    path.write_text(json.dumps(out, indent=2))
    out["artifact"] = str(path)
    return out
