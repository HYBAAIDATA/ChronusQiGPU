"""HYBA Data system runtime — start, online gate, debug & fix.

Doctrine:
  Self-healing and self-optimising (Salamander) may ONLY run when the system
  is ONLINE. Offline = observe/debug only; no heal/optimize actuation.

  PYTHONPATH=python_backend python3 -m hyba_data.system_runtime start
  PYTHONPATH=python_backend python3 -m hyba_data.system_runtime debug
  PYTHONPATH=python_backend python3 -m hyba_data.system_runtime fix
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_PATH = Path("artifacts/hyba_data/SYSTEM_RUNTIME_STATE.json")
DEBUG_PATH = Path("artifacts/hyba_data/elevation/SYSTEM_DEBUG_FIX.json")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class SystemState:
    online: bool = False
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    last_health: Dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
    version: str = "1.0.0"
    doctrine: str = (
        "Self-heal and self-optimize only when online. "
        "Emergence enhanced once present; not engineered as a checkbox."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_state() -> SystemState:
    if STATE_PATH.exists():
        try:
            d = json.loads(STATE_PATH.read_text())
            return SystemState(
                online=bool(d.get("online")),
                started_at=d.get("started_at"),
                stopped_at=d.get("stopped_at"),
                last_health=d.get("last_health") or {},
                last_error=d.get("last_error"),
                version=d.get("version") or "1.0.0",
            )
        except Exception:
            pass
    return SystemState()


def save_state(state: SystemState) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state.to_dict(), indent=2))


def is_online() -> bool:
    return load_state().online


def require_online(action: str = "autonomic") -> None:
    if not is_online():
        raise RuntimeError(
            f"System is OFFLINE — {action} blocked. "
            "Self-healing/self-optimising only when online. "
            "Run: python3 -m hyba_data.system_runtime start"
        )


def health_probe() -> Dict[str, Any]:
    """Probe core product surfaces without requiring full online actuation."""
    checks: Dict[str, Any] = {}
    errors: List[str] = []

    def _check(name: str, fn) -> None:
        try:
            checks[name] = {"ok": True, "detail": fn()}
        except Exception as e:
            checks[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            errors.append(name)

    _check(
        "platform",
        lambda: __import__(
            "hyba_substrate.platform", fromlist=["describe_platform"]
        ).describe_platform(),
    )
    _check(
        "phi1_sdk",
        lambda: {
            "passed_gate": __import__(
                "hyba_data.sdk_core", fromlist=["demo_m1"]
            ).demo_m1()["passed_gate"]
        },
    )
    _check(
        "fold_doctrine",
        lambda: __import__(
            "hyba_data.fold_doctrine", fromlist=["describe_fold_doctrine"]
        ).describe_fold_doctrine(),
    )
    _check(
        "external_metrics",
        lambda: __import__(
            "hyba_data.external_metrics", fromlist=["external_metric_pack"]
        ).external_metric_pack()["external_only"],
    )
    _check(
        "emergence_doctrine",
        lambda: __import__(
            "hyba_data.emergence", fromlist=["describe_emergence_doctrine"]
        ).describe_emergence_doctrine()["law"],
    )

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "checks": checks,
        "online": is_online(),
        "timestamp": _utc(),
    }


def start_system() -> Dict[str, Any]:
    """Bring system ONLINE after health probe passes."""
    health = health_probe()
    state = load_state()
    if not health["ok"]:
        state.online = False
        state.last_error = f"health_failed:{health['errors']}"
        state.last_health = health
        save_state(state)
        return {
            "status": "START_FAILED",
            "online": False,
            "health": health,
            "message": "Fix health failures before online. See debug/fix.",
        }

    state.online = True
    state.started_at = _utc()
    state.stopped_at = None
    state.last_error = None
    state.last_health = health
    save_state(state)

    # Autonomic cycle ONLY after online
    autonomic = None
    try:
        from hyba_substrate.salamander_support import run_autonomic_cycle

        autonomic = run_autonomic_cycle(require_online=True)
    except TypeError:
        # older signature — call then annotate
        from hyba_substrate.salamander_support import run_autonomic_cycle

        autonomic = run_autonomic_cycle()
        if isinstance(autonomic, dict):
            autonomic["online_gate"] = True
    except Exception as e:
        autonomic = {"error": f"{type(e).__name__}: {e}"}

    return {
        "status": "ONLINE",
        "online": True,
        "started_at": state.started_at,
        "health": health,
        "salamander": autonomic,
        "state_path": str(STATE_PATH),
    }


def stop_system() -> Dict[str, Any]:
    state = load_state()
    state.online = False
    state.stopped_at = _utc()
    save_state(state)
    return {"status": "OFFLINE", "online": False, "stopped_at": state.stopped_at}


def debug_system() -> Dict[str, Any]:
    """Collect diagnostics for offline or online systems (no heal actuation if offline)."""
    state = load_state()
    health = health_probe()
    issues: List[Dict[str, Any]] = []

    for name, c in (health.get("checks") or {}).items():
        if not c.get("ok"):
            issues.append(
                {
                    "component": name,
                    "severity": "high",
                    "error": c.get("error"),
                    "fix_hint": f"Inspect import/runtime for {name}; re-run health_probe",
                }
            )

    if not state.online:
        issues.append(
            {
                "component": "runtime",
                "severity": "info",
                "error": "system_offline",
                "fix_hint": "Self-heal/optimize blocked until start_system() succeeds",
            }
        )

    # Portfolio smoke (safe offline)
    portfolio: Dict[str, Any] = {}
    try:
        import numpy as np

        from hyba_data.phi1_runtime import Phi1Runtime

        rt = Phi1Runtime()
        x = np.sin(np.linspace(0, 6, 128))
        w = rt.phi_fold_write(x, mode="cf_tower", depth=2)
        portfolio["phi1_fold"] = {
            "passed_gate": w.get("passed_gate"),
            "recon_error": (w.get("cert") or {}).get("recon_error"),
        }
    except Exception as e:
        portfolio["phi1_fold"] = {"error": f"{type(e).__name__}: {e}"}
        issues.append(
            {
                "component": "phi1_fold",
                "severity": "high",
                "error": str(e),
                "fix_hint": "Check phi_folding_engine shims and PYTHONPATH",
            }
        )

    report = {
        "timestamp": _utc(),
        "state": state.to_dict(),
        "health": health,
        "portfolio": portfolio,
        "issues": issues,
        "online": state.online,
        "autonomic_allowed": state.online,
        "doctrine": state.doctrine,
    }
    DEBUG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEBUG_PATH.write_text(json.dumps(report, indent=2, default=str))
    report["artifact"] = str(DEBUG_PATH)
    return report


def fix_system() -> Dict[str, Any]:
    """Apply safe fixes then re-probe; bring online if healthy.

    Does NOT run Salamander heal/optimize while offline — only prep + start.
    """
    actions: List[str] = []
    dbg = debug_system()

    # Ensure artifact dirs
    for d in [
        Path("artifacts/hyba_data"),
        Path("artifacts/hyba_data/elevation"),
        Path("artifacts/hyba_data/phi1_store"),
    ]:
        d.mkdir(parents=True, exist_ok=True)
        actions.append(f"ensure_dir:{d}")

    # Clear stale last_error if health ok
    health = health_probe()
    state = load_state()
    if health["ok"]:
        state.last_error = None
        state.last_health = health
        save_state(state)
        actions.append("cleared_last_error")

    start = None
    if health["ok"]:
        start = start_system()
        actions.append("start_system")
    else:
        actions.append("start_blocked_unhealthy")

    out = {
        "timestamp": _utc(),
        "actions": actions,
        "debug": dbg,
        "start": start,
        "online": is_online(),
        "status": "FIXED_ONLINE" if is_online() else "NEEDS_MANUAL_FIX",
    }
    fix_path = Path("artifacts/hyba_data/elevation/SYSTEM_FIX_REPORT.json")
    fix_path.write_text(json.dumps(out, indent=2, default=str))
    out["artifact"] = str(fix_path)
    return out


def run_autonomic_if_online() -> Dict[str, Any]:
    """Public gate for heal/optimize."""
    require_online("salamander_autonomic_cycle")
    from hyba_substrate.salamander_support import run_autonomic_cycle

    try:
        return run_autonomic_cycle(require_online=True)
    except TypeError:
        r = run_autonomic_cycle()
        if isinstance(r, dict):
            r["online_gate"] = True
        return r


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv or sys.argv[1:])
    cmd = (argv[0] if argv else "status").lower()
    if cmd in ("start", "up", "online"):
        r = start_system()
    elif cmd in ("stop", "down", "offline"):
        r = stop_system()
    elif cmd in ("debug", "diag"):
        r = debug_system()
    elif cmd in ("fix", "repair"):
        r = fix_system()
    elif cmd in ("health", "probe"):
        r = health_probe()
    elif cmd in ("autonomic", "heal"):
        try:
            r = run_autonomic_if_online()
        except Exception as e:
            r = {"status": "BLOCKED", "error": str(e), "online": is_online()}
    else:
        st = load_state()
        r = {"status": "STATE", **st.to_dict(), "health": health_probe()}

    print(json.dumps(r, indent=2, default=str))
    if isinstance(r, dict):
        if r.get("status") in ("START_FAILED", "NEEDS_MANUAL_FIX", "BLOCKED"):
            return 1
        if r.get("ok") is False:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
