"""Self-defense — Part XII: code integrity, config integrity, self
attestation, witness mode (SD1–SD4)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .result import CODE_INTEGRITY_FAILURE, Ok, Result, error
from .types import Attestation, canonical_json

_MANIFEST_NAME = "manifest.json"
_PACKAGE_DIR = Path(__file__).resolve().parent


def _package_files() -> list[Path]:
    return sorted(
        p for p in _PACKAGE_DIR.glob("*.py") if p.is_file() and p.name != "__init__.py"
    ) + [_PACKAGE_DIR / "__init__.py"]


def build_manifest() -> dict[str, str]:
    """sha256 of every l_hras source file — written once, verified ever
    after. Returns {relative_path: digest}."""
    manifest: dict[str, str] = {}
    for path in _package_files():
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def write_manifest(path: Optional[str] = None) -> dict[str, str]:
    manifest = build_manifest()
    target = Path(path) if path else _PACKAGE_DIR / _MANIFEST_NAME
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def load_code_manifest() -> dict[str, str]:
    manifest_path = _PACKAGE_DIR / _MANIFEST_NAME
    if manifest_path.is_file():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return build_manifest()


def verify_code_integrity() -> Result[bool]:
    """Every source file's digest must equal its manifest digest."""
    manifest = load_code_manifest()
    for name, expected in manifest.items():
        path = _PACKAGE_DIR / name
        if not path.is_file():
            return error(CODE_INTEGRITY_FAILURE, file=name, reason="missing")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            return error(CODE_INTEGRITY_FAILURE, file=name)
    return Ok(True)


def config_integrity_payload(cfg: Any) -> dict[str, Any]:
    return {
        "mass_gap": cfg.mass_gap,
        "viscosity": cfg.viscosity,
        "pnp_ratio": str(cfg.pnp_ratio),
        "entropy_threshold": cfg.entropy_threshold,
        "purity_threshold": cfg.purity_threshold,
        "fidelity_threshold": cfg.fidelity_threshold,
        "critical_lines": dict(cfg.critical_lines),
        "rank_bounds": dict(cfg.rank_bounds),
    }


def verify_config_integrity(lhras: Any) -> Result[bool]:
    """The loaded config must match the signature bound at standing —
    post-hoc tampering of ``cfg`` fails closed."""
    cfg = lhras.cfg
    if cfg.trust_root is None or not cfg.trust_root.secret:
        return error(CODE_INTEGRITY_FAILURE, reason="trust_root_absent")
    bound = getattr(lhras, "_config_integrity_sig", None)
    current = cfg.trust_root.sign(
        {"config_integrity": canonical_json(config_integrity_payload(cfg))}
    )
    if bound is None:
        # Not yet bound (pre-standing): the config verifies against its
        # own trust root, nothing more is declared.
        return Ok(True)
    import hmac as _hmac

    if not _hmac.compare_digest(bound, current):
        return error(CODE_INTEGRITY_FAILURE, reason="config_drifted")
    return Ok(True)


def self_attest(lhras: Any) -> Attestation:
    return lhras.attester.self_attest(
        {
            "event": "self_state",
            "swarm": lhras.swarm.id,
            "uptime": time.time() - getattr(lhras, "start_time", time.time()),
            "events": getattr(lhras, "event_count", 0),
            "refusals": getattr(lhras, "refusal_count", 0),
        }
    )


@dataclass
class WitnessSession:
    """Read-only observation of a standing Guardian — no mutation path
    is exposed on the session object."""

    lhras: Any
    observer: str
    mode: str = "read_only"
    started_at: float = field(default_factory=time.time)

    def snapshot(self) -> dict[str, Any]:
        l = self.lhras
        return {
            "standing": l.standing,
            "swarm_id": l.swarm.id,
            "workers": len(l.swarm.workers),
            "topologies": (dict(l.standing_state.topologies) if l.standing_state else {}),
            "events": getattr(l, "event_count", 0),
            "refusals": getattr(l, "refusal_count", 0),
        }


def witness_mode(lhras: Any, observer_pubkey: str) -> WitnessSession:
    return WitnessSession(lhras=lhras, observer=observer_pubkey)
