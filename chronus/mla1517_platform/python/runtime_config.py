"""Runtime configuration store for PYTHIA solver arms and the control API.

Single source of truth: ``PYTHIA_RUNTIME_CONFIG`` (default
``<repo>/data/runtime_config.json``), written only through the control
API's /config endpoint. Solver-arm processes poll the file each window
so hashrate pacing and live-submit toggles apply without a restart;
pool and arm-count changes are applied by restarting arms.

Every field is bounded and validated here — the file is the contract,
and values outside the bounds are rejected at write time, never clamped
silently in the reading path.
"""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
import os
import threading
import time
from pathlib import Path
from typing import Any

from Intelligence.lucas_scales import ladder_capacity

SCHEMA = "pythia.runtime_config/1"

# --- bounds (the hard outer edges of the system) ---
ARMS_MIN = 1
ARMS_MAX = 600  # solver-arm processes supervised by the control API
WORKERS_MIN = 1
WORKERS_MAX = 600  # virtual solver workers inside a scaled execution arm
LANES_PER_ARM = 32  # M32 lane topology inside every arm (fixed)
HASHRATE_CEILING_HS = 1e19  # governed engineering target ceiling: 10 EH/s
WINDOW_MIN = 1
# LUCAS_SCALED (lemma_lucas_universal): Chronus-declared bounds are ladder
# stops. WINDOW_MAX floors to 4194300; ARMS_MAX/WORKERS_MAX (600) and the
# window default (200000) are already stops; LANES_PER_ARM stays raw —
# M32 lane topology, not an envelope.
WINDOW_MAX = ladder_capacity(1 << 22)
CAMPAIGN_PHASES_MAX = ladder_capacity(32)  # ordered phases in one pool campaign
CAMPAIGN_DURATION_MIN_S = 10
CAMPAIGN_DURATION_MAX_S = 86400  # one day per phase, hard stop

_LOCK = threading.Lock()


def config_path() -> Path:
    """Resolve the runtime config path.

    ``PYTHIA_RUNTIME_CONFIG`` wins; otherwise the repo's
    ``data/runtime_config.json`` (repo root derived from this file's
    location: chronus/mla1517_platform/python/../..).
    """
    override = os.environ.get("PYTHIA_RUNTIME_CONFIG", "").strip()
    if override:
        return Path(override)
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    return repo_root / "data" / "runtime_config.json"


def default_config() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "updated_at": None,
        "pools": [],
        "solvers": {"arms": 1, "workers": 32},
        "execution": {"mode": "independent"},
        "intelligence": {"seed": 1337, "max_workers": 4, "max_nonces_per_arm": None, "require_toe": False},
        "hashrate": {"target_hs": 0.0, "ceiling_hs": HASHRATE_CEILING_HS},
        "live_submit": {"enabled": False, "approval_id": ""},
        "mining_policy": None,
        "window": 200000,
        "campaign": {"phases": []},
        "bounds": {
            "arms": [ARMS_MIN, ARMS_MAX],
            "workers_per_arm": [WORKERS_MIN, WORKERS_MAX],
            "hashrate_ceiling_hs": HASHRATE_CEILING_HS,
            "window": [WINDOW_MIN, WINDOW_MAX],
            "campaign_phases": CAMPAIGN_PHASES_MAX,
            "campaign_duration_s": [CAMPAIGN_DURATION_MIN_S, CAMPAIGN_DURATION_MAX_S],
        },
    }


def _persisted_section_ok(key: str, value: Any) -> bool:
    """Shape check for a persisted section: consumers assume these container
    types, so a section that breaks them is untrusted input (manual edit,
    version skew) and must fall back to its default rather than crash
    public_view or downstream readers. Semantic rules (bounds, pool
    references) stay enforced at write time by validate()."""
    if key == "mining_policy":
        return value is None or isinstance(value, dict)
    if key == "pools":
        return isinstance(value, list) and all(isinstance(p, dict) for p in value)
    if key in ("solvers", "hashrate", "live_submit", "campaign", "execution", "intelligence"):
        if not isinstance(value, dict):
            return False
        if key == "campaign":
            return isinstance(value.get("phases", []), list)
        if key == "hashrate":
            target = value.get("target_hs", 0.0)
            return isinstance(target, (int, float)) and not isinstance(target, bool)
        if key == "solvers":
            return isinstance(value.get("arms", 1), int) and isinstance(
                value.get("workers", 32), int
            )
        return True
    if key == "window":
        return isinstance(value, int) and not isinstance(value, bool)
    return False


def load() -> dict[str, Any]:
    """Read the runtime config; absent or structurally invalid sections fall
    back to defaults — a persisted file is untrusted input."""
    path = config_path()
    cfg = default_config()
    if not path.is_file():
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {**cfg, "_policy_error": "invalid_persisted_config"}
    if not isinstance(raw, dict):
        return {**cfg, "_policy_error": "invalid_persisted_config"}
    for key in (
        "pools",
        "solvers",
        "hashrate",
        "live_submit",
        "mining_policy",
        "window",
        "campaign",
        "execution",
        "intelligence",
    ):
        if key in raw:
            if not _persisted_section_ok(key, raw[key]):
                return {**default_config(), "_policy_error": "invalid_persisted_config"}
            cfg[key] = raw[key]
    # A correctly shaped but out-of-policy file is still untrusted. Validate
    # all merged sections together: a corrupt dependency cannot retain live intent.
    try:
        normalized = validate(cfg)
    except (TypeError, ValueError, OverflowError):
        return {**default_config(), "_policy_error": "invalid_persisted_config"}
    normalized["updated_at"] = raw.get("updated_at")
    return normalized


def _validate_endpoint(endpoint: Any) -> str:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("pool endpoint must be a non-empty host[:port] string")
    ep = endpoint.strip()
    for prefix in ("stratum+tcp://", "tcp://", "stratum://"):
        if ep.startswith(prefix):
            ep = ep[len(prefix) :]
    host, sep, port_s = ep.partition(":")
    if not host or any(ch.isspace() for ch in host):
        raise ValueError("pool endpoint host is invalid")
    if sep:
        try:
            port = int(port_s)
        except ValueError:
            raise ValueError("pool endpoint port is invalid")
        if not 1 <= port <= 65535:
            raise ValueError("pool endpoint port must be 1..65535")
    return ep


def _validate_worker(worker: Any) -> str:
    if not isinstance(worker, str) or not worker.strip():
        raise ValueError("pool worker must be a non-empty account.worker string")
    worker = worker.strip()
    if len(worker) > 128 or any(ch.isspace() for ch in worker):
        raise ValueError("pool worker is invalid")
    return worker


def validate(cfg: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a candidate config. Raises ValueError on
    any out-of-bounds or malformed field — nothing is clamped silently."""
    pools = cfg.get("pools", [])
    if not isinstance(pools, list):
        raise ValueError("pools must be a list")
    seen: set[str] = set()
    out_pools = []
    enabled_seen = False
    for i, p in enumerate(pools):
        if not isinstance(p, dict):
            raise ValueError(f"pools[{i}] must be an object")
        endpoint = _validate_endpoint(p.get("endpoint"))
        worker = _validate_worker(p.get("worker"))
        password = p.get("password", "")
        if not isinstance(password, str) or not password:
            raise ValueError(f"pools[{i}].password must be a non-empty string")
        key = f"{endpoint}|{worker}"
        if key in seen:
            raise ValueError(f"pools[{i}] duplicates {endpoint} {worker}")
        seen.add(key)
        enabled = p.get("enabled", False)
        if type(enabled) is not bool:
            raise ValueError(f"pools[{i}].enabled must be boolean")
        if enabled and enabled_seen:
            raise ValueError("exactly one pool may be enabled")
        enabled_seen = enabled_seen or enabled
        out_pools.append(
            {
                "endpoint": endpoint,
                "worker": worker,
                "password": password,
                "enabled": enabled,
            }
        )

    solvers = cfg.get("solvers", {})
    if not isinstance(solvers, dict):
        raise ValueError("solvers must be an object")
    arms = solvers.get("arms", 1)
    workers = solvers.get("workers", 32)
    if type(arms) is not int or not ARMS_MIN <= arms <= ARMS_MAX:
        raise ValueError(f"solvers.arms must be an integer in [{ARMS_MIN},{ARMS_MAX}]")
    if type(workers) is not int or not WORKERS_MIN <= workers <= WORKERS_MAX:
        raise ValueError(f"solvers.workers must be an integer in [{WORKERS_MIN},{WORKERS_MAX}]")

    hashrate = cfg.get("hashrate", {})
    if not isinstance(hashrate, dict):
        raise ValueError("hashrate must be an object")
    target = hashrate.get("target_hs", 0.0)
    if not isinstance(target, (int, float)) or isinstance(target, bool):
        raise ValueError("hashrate.target_hs must be a number")
    try:
        target = float(target)
    except OverflowError as exc:
        raise ValueError("hashrate.target_hs must be in [0, 1e19]") from exc
    ceiling = hashrate.get("ceiling_hs", HASHRATE_CEILING_HS)
    if (
        isinstance(ceiling, bool)
        or not isinstance(ceiling, (int, float))
        or not 0 < ceiling <= HASHRATE_CEILING_HS
        or not math.isfinite(ceiling)
    ):
        raise ValueError("hashrate.ceiling_hs must be in (0, 1e19]")
    ceiling = float(ceiling)
    if not 0.0 <= target <= ceiling:
        raise ValueError("hashrate.target_hs must be in [0, 1e19] (10 EH/s ceiling)")

    live = cfg.get("live_submit", {})
    if not isinstance(live, dict):
        raise ValueError("live_submit must be an object")
    live_enabled = live.get("enabled", False)
    if type(live_enabled) is not bool:
        raise ValueError("live_submit.enabled must be boolean")
    approval_id = live.get("approval_id", "")
    if not isinstance(approval_id, str):
        raise ValueError("live_submit.approval_id must be a string")
    if live_enabled:
        if not out_pools or not any(p["enabled"] for p in out_pools):
            raise ValueError("live_submit requires an enabled pool")
        if len(approval_id) != 64 or any(c not in "0123456789abcdef" for c in approval_id):
            raise ValueError("live_submit requires an approval_id bound to the pool identity")

    window = cfg.get("window", 200000)
    if type(window) is not int or not WINDOW_MIN <= window <= WINDOW_MAX:
        raise ValueError(f"window must be an integer in [{WINDOW_MIN},{WINDOW_MAX}]")

    campaign = cfg.get("campaign", {})
    if not isinstance(campaign, dict):
        raise ValueError("campaign must be an object")
    phases = campaign.get("phases", [])
    if not isinstance(phases, list) or len(phases) > CAMPAIGN_PHASES_MAX:
        raise ValueError(f"campaign.phases must be a list of at most {CAMPAIGN_PHASES_MAX}")
    pool_keys = {p["worker"] for p in out_pools} | {p["endpoint"] for p in out_pools}
    out_phases = []
    for i, ph in enumerate(phases):
        if not isinstance(ph, dict):
            raise ValueError(f"campaign.phases[{i}] must be an object")
        pool_key = ph.get("pool")
        if not isinstance(pool_key, str) or pool_key not in pool_keys:
            raise ValueError(
                f"campaign.phases[{i}].pool must name a configured pool worker or endpoint"
            )
        duration = ph.get("duration_s")
        if (
            not isinstance(duration, int)
            or isinstance(duration, bool)
            or not CAMPAIGN_DURATION_MIN_S <= duration <= CAMPAIGN_DURATION_MAX_S
        ):
            raise ValueError(
                f"campaign.phases[{i}].duration_s must be an integer in "
                f"[{CAMPAIGN_DURATION_MIN_S},{CAMPAIGN_DURATION_MAX_S}]"
            )
        phase_target = ph.get("target_hs", ceiling)
        if not isinstance(phase_target, (int, float)) or isinstance(phase_target, bool):
            raise ValueError(f"campaign.phases[{i}].target_hs must be a number")
        phase_target = float(phase_target)
        if not 0.0 < phase_target <= HASHRATE_CEILING_HS:
            raise ValueError(
                f"campaign.phases[{i}].target_hs must be in (0, 1e19] (10 EH/s ceiling)"
            )
        phase_arms = ph.get("arms", ARMS_MIN)
        if type(phase_arms) is not int or not ARMS_MIN <= phase_arms <= ARMS_MAX:
            raise ValueError(
                f"campaign.phases[{i}].arms must be an integer in [{ARMS_MIN},{ARMS_MAX}]"
            )
        phase_live = ph.get("live_submit", False)
        if type(phase_live) is not bool:
            raise ValueError(f"campaign.phases[{i}].live_submit must be boolean")
        if phase_target > ceiling:
            raise ValueError(f"campaign.phases[{i}].target_hs exceeds configured ceiling")
        out_phases.append(
            {
                "pool": pool_key,
                "duration_s": duration,
                "target_hs": phase_target,
                "arms": phase_arms,
                "live_submit": phase_live,
            }
        )

    policy = cfg.get("mining_policy")
    if policy is not None:
        from pool_catalog import POOL_CATALOG
        if (not isinstance(policy, dict) or set(policy) != {"poolId", "shares_target"}
            or policy.get("poolId") not in POOL_CATALOG
            or type(policy.get("shares_target")) is not int
            or not 1 <= policy["shares_target"] <= 10000):
            raise ValueError("invalid mining_policy")
        policy = dict(policy)

    execution = cfg.get("execution", {})
    intelligence = cfg.get("intelligence", {})
    if not isinstance(execution, dict) or execution.get("mode", "independent") not in (
        "independent",
        "auto",
        "scale_stack",
    ):
        raise ValueError("execution.mode must be independent, auto, or scale_stack")
    if not isinstance(intelligence, dict):
        raise ValueError("intelligence must be an object")
    require_toe = intelligence.get("require_toe", False)
    if type(require_toe) is not bool:
        raise ValueError("intelligence.require_toe must be boolean")
    seed = intelligence.get("seed", 1337)
    workers_limit = intelligence.get("max_workers", 4)
    nonce_limit = intelligence.get("max_nonces_per_arm")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("intelligence.seed must be a u32 integer")
    if type(workers_limit) is not int or not 1 <= workers_limit <= 32:
        raise ValueError("intelligence.max_workers must be in [1,32]")
    if nonce_limit is not None and (type(nonce_limit) is not int or not 1 <= nonce_limit <= 2**20):
        raise ValueError("intelligence.max_nonces_per_arm must be null or in [1,2^20]")
    return {
        "schema": SCHEMA,
        "updated_at": time.time(),
        "pools": out_pools,
        "solvers": {"arms": arms, "workers": workers},
        "execution": {"mode": execution.get("mode", "independent")},
        "intelligence": {
            "seed": seed,
            "require_toe": require_toe,
            "max_workers": workers_limit,
            "max_nonces_per_arm": nonce_limit,
        },
        "hashrate": {
            "target_hs": target,
            "ceiling_hs": ceiling,
        },
        "live_submit": {"enabled": live_enabled, "approval_id": approval_id},
        "mining_policy": policy,
        "window": window,
        "campaign": {"phases": out_phases},
        "bounds": {
            "arms": [ARMS_MIN, ARMS_MAX],
            "workers_per_arm": [WORKERS_MIN, WORKERS_MAX],
            "hashrate_ceiling_hs": HASHRATE_CEILING_HS,
            "window": [WINDOW_MIN, WINDOW_MAX],
            "campaign_phases": CAMPAIGN_PHASES_MAX,
            "campaign_duration_s": [CAMPAIGN_DURATION_MIN_S, CAMPAIGN_DURATION_MAX_S],
        },
    }


def save(cfg: dict[str, Any]) -> dict[str, Any]:
    """Validate, atomically persist, and return the normalized config."""
    normalized = validate(cfg)
    path = config_path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Config contains pool secrets. Unique same-directory temporary files
        # avoid cross-process collisions and never expose group/world permissions.
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        tmp = Path(temporary)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(normalized, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    return normalized


def active_pool(cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The single enabled pool, or None."""
    cfg = cfg if cfg is not None else load()
    for p in cfg.get("pools", []):
        if p.get("enabled"):
            return p
    return None


def identity_commit(endpoint: str, worker: str) -> str:
    """SHA-256 binding of a live-submit approval to one pool identity.
    The approval is only meaningful for the exact endpoint+worker it was
    issued against; a pool change without a fresh enable mismatches and
    the gate stays closed."""
    return hashlib.sha256(f"{endpoint}|{worker}".encode("utf-8")).hexdigest()


def live_submit_permitted(
    cfg: dict[str, Any] | None = None, *, endpoint: str = "", worker: str = ""
) -> bool:
    """Config-side live-submit gate, polled by solver arms each window.

    Permitted only when the operator enabled it through the API AND the
    approval binds to the arm's actual endpoint+worker."""
    cfg = cfg if cfg is not None else load()
    live = cfg.get("live_submit", {})
    if not live.get("enabled") or not live.get("approval_id"):
        return False
    pool = active_pool(cfg)
    if pool is None:
        return False
    actual_ep = endpoint or pool["endpoint"]
    actual_worker = worker or pool["worker"]
    return identity_commit(actual_ep, actual_worker) == live["approval_id"]


def public_view(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Redacted view for /status and /config GET — never leaks passwords."""
    cfg = cfg if cfg is not None else load()
    return {
        "schema": SCHEMA,
        "policy_valid": not bool(cfg.get("_policy_error")),
        "updated_at": cfg.get("updated_at"),
        "pools": [
            {
                "endpoint": p["endpoint"],
                "worker": p["worker"],
                "password_committed": bool(p.get("password")),
                "enabled": p.get("enabled", False),
            }
            for p in cfg.get("pools", [])
        ],
        "solvers": dict(cfg.get("solvers", {})),
        "execution": dict(cfg.get("execution", {})),
        "intelligence": dict(cfg.get("intelligence", {})),
        "hashrate": dict(cfg.get("hashrate", {})),
        "live_submit": {
            "enabled": cfg.get("live_submit", {}).get("enabled", False),
            "approval_bound": bool(cfg.get("live_submit", {}).get("approval_id")),
        },
        "mining_policy": cfg.get("mining_policy"),
        "window": cfg.get("window", 200000),
        "campaign": {
            "phases": [
                {
                    "pool": ph["pool"],
                    "duration_s": ph["duration_s"],
                    "target_hs": ph["target_hs"],
                    "arms": ph["arms"],
                    "live_submit": bool(ph.get("live_submit", False)),
                }
                for ph in cfg.get("campaign", {}).get("phases", [])
            ]
        },
        "bounds": dict(cfg.get("bounds", {})),
        "path": str(config_path()),
    }
