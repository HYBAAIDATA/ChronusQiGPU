"""PHI-1 Runtime (Lane A → B) — elevate code to meet Architecture + OS design docs.

Doctrine (absolute):
  We elevate code to meet documentation, always.
  Fold, never truncate. Quantum serves data. Quantum from maths.

Maps PHI-1 OS Design Document APIs onto Φ-UFE:
  phi_open, phi_fold_write, phi_unfold_read, phi_stat, phi_verify

Repo: python_backend/hyba_data/phi1_runtime.py
Docs: PHI-Space Architecture Spec v1.0 · PHI-1 OS Design Document v1.0
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from hyba_data.fold_doctrine import assert_fold_not_truncate, describe_fold_doctrine

ArrayLike = Union[np.ndarray, list, tuple]

# Ensure fold engine loads without mining package
try:
    from pulvini.folding_engine.compat_mining_shim import install as _install_shim

    _install_shim()
except Exception:
    pass

from pulvini.folding_engine import PhiFoldingEngine


@dataclass
class PhiHandle:
    """Open handle to a φ-state (PHI-1 process memory model)."""

    handle_id: str
    mode: str
    n: int
    created_at_utc: str
    path: Optional[str] = None
    claim_lane: str = "A"  # implemented runtime

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PhiCert:
    """Integrity / recon certificate — fold never truncate."""

    mode: str
    n: int
    recon_error: float
    compression_ratio: Optional[float]
    content_hash: str
    fold_hash: str
    passed_gate: bool
    max_err_gate: float
    doctrine: str = "fold_never_truncate"
    quantum_serves_data: bool = True
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Phi1Runtime:
    """Software PHI-1 runtime on classical host (Linux/containers)."""

    def __init__(
        self,
        store_dir: str | Path = "artifacts/hyba_data/phi1_store",
        default_mode: str = "cf_tower",
        max_err_gate: float = 1e-5,
    ):
        self.engine = PhiFoldingEngine()
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.default_mode = default_mode
        self.max_err_gate = max_err_gate
        self._handles: Dict[str, Dict[str, Any]] = {}

    # --- PHI-1 OS APIs ---

    def phi_open(self, object_id: Optional[str] = None) -> PhiHandle:
        """Open a new or existing φ-state handle."""
        hid = object_id or str(uuid.uuid4())
        path = self.store_dir / f"{hid}.phistate.json"
        h = PhiHandle(
            handle_id=hid,
            mode=self.default_mode,
            n=0,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            path=str(path) if path.exists() else None,
        )
        if path.exists():
            blob = json.loads(path.read_text())
            h.mode = blob.get("mode", self.default_mode)
            h.n = int(blob.get("n", 0))
            h.path = str(path)
            self._handles[hid] = blob
        else:
            self._handles[hid] = {"handle_id": hid, "empty": True}
        return h

    def phi_fold_write(
        self,
        data: ArrayLike,
        *,
        mode: Optional[str] = None,
        handle_id: Optional[str] = None,
        depth: int = 4,
    ) -> Dict[str, Any]:
        """φ-FOLD + persist — compress by folding, not truncating."""
        mode = mode or self.default_mode
        x = np.asarray(data)
        # zphi path prefers integer-like
        src = x
        if mode == "zphi_exact" and not np.issubdtype(x.dtype, np.integer):
            src = np.round(x).astype(np.int64)

        t0 = time.perf_counter()
        folded = self.engine.fold(src, mode=mode, depth=depth)
        unfolded = np.asarray(self.engine.unfold(folded)).ravel()
        src_flat = np.asarray(src, dtype=np.float64).ravel()
        unfolded = unfolded[: src_flat.size].astype(np.float64)
        recon_error = float(np.max(np.abs(unfolded - src_flat[: unfolded.size])))
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Gate: fold never truncate
        gate = 1.0 if mode == "zphi_exact" else self.max_err_gate
        try:
            assert_fold_not_truncate(recon_error, max_err=gate)
            passed = True
        except Exception:
            passed = False

        ratio = None
        if isinstance(folded, dict):
            ratio = folded.get("compression_ratio") or folded.get("ratio")
            if ratio is None and folded.get("kind") == "progressive_pair_fold":
                ratio = folded.get("compression_ratio")

        content_hash = hashlib.sha256(
            np.ascontiguousarray(src_flat).tobytes()
        ).hexdigest()
        fold_bytes = json.dumps(folded, sort_keys=True, default=str).encode("utf-8")
        fold_hash = hashlib.sha256(fold_bytes).hexdigest()

        cert = PhiCert(
            mode=mode,
            n=int(src_flat.size),
            recon_error=recon_error,
            compression_ratio=float(ratio) if ratio is not None else None,
            content_hash=content_hash,
            fold_hash=fold_hash,
            passed_gate=passed,
            max_err_gate=gate,
        )

        hid = handle_id or str(uuid.uuid4())
        record = {
            "handle_id": hid,
            "mode": mode,
            "n": int(src_flat.size),
            "folded": folded,
            "cert": cert.to_dict(),
            "doctrine": describe_fold_doctrine(),
            "elapsed_ms": elapsed_ms,
            "shape": list(np.asarray(src).shape),
            "dtype": str(np.asarray(src).dtype),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "isa": ["phi_FOLD", "phi_UNFOLD", "phi_VERIFY"],
            "lane": "A",
            "quantum_serves_data": True,
        }
        path = self.store_dir / f"{hid}.phistate.json"
        cert_path = self.store_dir / f"{hid}.cert.json"
        path.write_text(json.dumps(record, indent=2, default=str))
        cert_path.write_text(json.dumps(cert.to_dict(), indent=2))
        self._handles[hid] = record

        return {
            "handle": PhiHandle(
                handle_id=hid,
                mode=mode,
                n=int(src_flat.size),
                created_at_utc=record["created_at_utc"],
                path=str(path),
            ).to_dict(),
            "cert": cert.to_dict(),
            "passed_gate": passed,
            "store": str(path),
            "elevation_rule": "We elevate code to meet documentation, always.",
        }

    def phi_unfold_read(self, handle_id: str) -> Dict[str, Any]:
        """φ-UNFOLD — reconstruct from stored φ-state."""
        rec = self._load(handle_id)
        folded = rec["folded"]
        y = np.asarray(self.engine.unfold(folded)).ravel()
        cert = rec.get("cert") or {}
        return {
            "handle_id": handle_id,
            "data": y.tolist(),
            "n": int(y.size),
            "mode": rec.get("mode"),
            "cert": cert,
            "passed_gate": bool(cert.get("passed_gate")),
        }

    def phi_stat(self, handle_id: str) -> Dict[str, Any]:
        rec = self._load(handle_id)
        return {
            "handle_id": handle_id,
            "mode": rec.get("mode"),
            "n": rec.get("n"),
            "cert": rec.get("cert"),
            "shape": rec.get("shape"),
            "dtype": rec.get("dtype"),
            "created_at_utc": rec.get("created_at_utc"),
            "path": str(self.store_dir / f"{handle_id}.phistate.json"),
        }

    def phi_verify(self, handle_id: str) -> Dict[str, Any]:
        """φ-VERIFY — integrity / recon gate re-check."""
        rec = self._load(handle_id)
        cert = rec.get("cert") or {}
        # re-unfold and compare hash of fold payload
        fold_bytes = json.dumps(rec["folded"], sort_keys=True, default=str).encode(
            "utf-8"
        )
        fold_hash = hashlib.sha256(fold_bytes).hexdigest()
        hash_ok = fold_hash == cert.get("fold_hash")
        y = np.asarray(self.engine.unfold(rec["folded"])).ravel()
        ok = bool(cert.get("passed_gate")) and hash_ok and y.size == int(rec.get("n", y.size))
        return {
            "handle_id": handle_id,
            "ok": ok,
            "hash_ok": hash_ok,
            "passed_gate": bool(cert.get("passed_gate")),
            "recon_error": cert.get("recon_error"),
            "mode": rec.get("mode"),
            "opcode": "phi_VERIFY",
        }

    def phi_dist(self, handle_a: str, handle_b: str) -> Dict[str, Any]:
        """φ-DIST proxy — L2 on unfolded states (Lane A); geodesic target is Lane C."""
        a = np.asarray(self.phi_unfold_read(handle_a)["data"], dtype=np.float64)
        b = np.asarray(self.phi_unfold_read(handle_b)["data"], dtype=np.float64)
        n = min(a.size, b.size)
        dist = float(np.linalg.norm(a[:n] - b[:n])) if n else 0.0
        return {
            "handle_a": handle_a,
            "handle_b": handle_b,
            "distance_l2": dist,
            "n": n,
            "lane": "A",
            "note": "Geodesic O(log N) search remains Lane C until sealed",
            "opcode": "phi_DIST",
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "runtime": "PHI-1",
            "version": "1.0.0-laneA",
            "elevation_rule": "We elevate code to meet documentation, always.",
            "doctrine": describe_fold_doctrine(),
            "store_dir": str(self.store_dir),
            "default_mode": self.default_mode,
            "max_err_gate": self.max_err_gate,
            "isa_implemented": [
                "phi_FOLD",
                "phi_UNFOLD",
                "phi_LOAD",
                "phi_VERIFY",
                "phi_DIST",
            ],
            "isa_target": ["phi_UNITARY", "phi_SEARCH", "phi_VERIFY_topo"],
            "docs": [
                "PHI-Space Architecture Specification (v1.0)",
                "PHI-1 OS Design Document (v1.0)",
            ],
            "quantum_serves_data": True,
            "not_saas": True,
            "mining_product_surface": False,
        }

    def _load(self, handle_id: str) -> Dict[str, Any]:
        if handle_id in self._handles and not self._handles[handle_id].get("empty"):
            return self._handles[handle_id]
        path = self.store_dir / f"{handle_id}.phistate.json"
        if not path.exists():
            raise FileNotFoundError(f"φ-state not found: {handle_id}")
        rec = json.loads(path.read_text())
        self._handles[handle_id] = rec
        return rec


def build_runtime_report() -> Dict[str, Any]:
    """Self-test: elevate code to meet PHI-1 OS documentation."""
    rt = Phi1Runtime()
    x = np.sin(np.linspace(0, 6 * np.pi, 128))
    w = rt.phi_fold_write(x, mode="cf_tower", depth=3)
    hid = w["handle"]["handle_id"]
    u = rt.phi_unfold_read(hid)
    v = rt.phi_verify(hid)
    s = rt.phi_stat(hid)
    # second state for dist
    w2 = rt.phi_fold_write(x * 0.5, mode="cf_tower", depth=3)
    d = rt.phi_dist(hid, w2["handle"]["handle_id"])
    report = {
        "title": "PHI-1 Runtime Elevation Report",
        "elevation_rule": "We elevate code to meet documentation, always.",
        "describe": rt.describe(),
        "fold_write": {"passed_gate": w["passed_gate"], "cert": w["cert"]},
        "unfold_n": u["n"],
        "verify": v,
        "stat_mode": s.get("mode"),
        "dist": d,
        "self_test_passed": bool(
            w["passed_gate"] and v["ok"] and u["n"] == 128 and d["distance_l2"] >= 0
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_path": "python_backend/hyba_data/phi1_runtime.py",
    }
    return report


def main() -> int:
    report = build_runtime_report()
    art = Path("artifacts/hyba_data")
    art.mkdir(parents=True, exist_ok=True)
    out = art / "PHI1_RUNTIME_ELEVATION.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(
        json.dumps(
            {
                "wrote": str(out),
                "self_test_passed": report["self_test_passed"],
                "elevation_rule": report["elevation_rule"],
            },
            indent=2,
        )
    )
    return 0 if report["self_test_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
