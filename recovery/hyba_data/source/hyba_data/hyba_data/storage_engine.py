"""PHI-1 Storage Engine spike — local .phi write / unfold read (S3-gateway shaped).

Not a full S3 service. Proves fold-at-write + unfold-at-read integrity for local elevation.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np

from hyba_data.external_metrics import SENSITIVITY_M
from hyba_data.phi1_runtime import Phi1Runtime
from hyba_data.savings_metering import compute_savings

ArrayLike = Union[np.ndarray, list, bytes]


class Phi1StorageEngine:
    def __init__(self, root: str | Path = "artifacts/hyba_data/phi1_storage", max_err: float = 1e-5):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.rt = Phi1Runtime(store_dir=self.root / "runtime_store", max_err_gate=max_err)
        self.meta_dir = self.root / "meta"
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def put_object(
        self,
        key: str,
        data: ArrayLike,
        *,
        mode: str = "cf_tower",
        depth: int = 2,
        content_type: str = "application/x-phi-array",
    ) -> Dict[str, Any]:
        """S3-like PutObject: fold and store as .phi metadata + runtime handle."""
        if isinstance(data, (bytes, bytearray)):
            arr = np.frombuffer(bytes(data), dtype=np.uint8).astype(np.float64)
        else:
            arr = np.asarray(data, dtype=np.float64)
        w = self.rt.phi_fold_write(arr, mode=mode, depth=depth)
        if not w["passed_gate"]:
            raise RuntimeError(f"fold gate failed: {w['cert']}")
        handle_id = w["handle"]["handle_id"]
        meta = {
            "key": key,
            "handle_id": handle_id,
            "content_type": content_type,
            "mode": mode,
            "depth": depth,
            "baseline_bytes": int(arr.nbytes),
            "cert": w["cert"],
            "created": time.time(),
            "phi_suffix": ".phi",
        }
        path = self.meta_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.phi.json"
        path.write_text(json.dumps(meta, indent=2))
        meta["meta_path"] = str(path)
        meta["etag"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return meta

    def get_object(self, key: str) -> Dict[str, Any]:
        """S3-like GetObject: load meta and unfold."""
        path = self.meta_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.phi.json"
        if not path.exists():
            raise FileNotFoundError(key)
        meta = json.loads(path.read_text())
        u = self.rt.phi_unfold_read(meta["handle_id"])
        data = np.asarray(u["data"], dtype=np.float64)
        return {
            "key": key,
            "data": data,
            "meta": meta,
            "verify": self.rt.phi_verify(meta["handle_id"]),
        }

    def measure_capacity(
        self,
        key: str,
        *,
        s_memory: float = 1.0,
        f: float = 1.0,
    ) -> Dict[str, Any]:
        path = self.meta_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.phi.json"
        meta = json.loads(path.read_text())
        # use sensitivity for external fee path
        rows = {}
        for m in SENSITIVITY_M:
            rows[str(m)] = compute_savings(
                s_memory=s_memory, f=f, m_eff=m, measured=True
            ).to_dict()
        return {
            "key": key,
            "baseline_bytes": meta["baseline_bytes"],
            "cert": meta["cert"],
            "sensitivity_fees": rows,
            "viability_external": {str(m): m >= 2.0 for m in SENSITIVITY_M},
            "note": "m≥2 preferred for list-price 2× commodity break-even sketch",
        }


def run_storage_spike(
    artifact_dir: str | Path = "artifacts/hyba_data/elevation",
) -> Dict[str, Any]:
    eng = Phi1StorageEngine()
    x = np.sin(np.linspace(0, 12 * np.pi, 1024))
    put = eng.put_object("demo/blob-001", x, depth=2)
    got = eng.get_object("demo/blob-001")
    err = float(np.max(np.abs(got["data"][: x.size] - x)))
    cap = eng.measure_capacity("demo/blob-001", s_memory=1_000_000.0, f=0.5)
    out = {
        "put": {k: put[k] for k in put if k != "cert"} | {"recon_error_cert": put["cert"]["recon_error"]},
        "get_verify": got["verify"],
        "recon_error": err,
        "passed": err < 1e-5 and got["verify"].get("ok"),
        "capacity": cap,
    }
    art = Path(artifact_dir)
    art.mkdir(parents=True, exist_ok=True)
    p = art / "STORAGE_ENGINE_SPIKE.json"
    p.write_text(json.dumps(out, indent=2, default=str))
    out["artifact"] = str(p)
    return out
