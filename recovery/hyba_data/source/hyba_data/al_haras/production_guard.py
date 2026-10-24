"""Al-Haras launch safety and secret hygiene guards (migrated from HYBA_PROD_READY).

This module is intentionally small and dependency-light because it is used as a
pre-runtime launch guard. It must fail closed, emit JSON-safe evidence, and
supports both the original MIDAS variable names and the newer HYBA/NiceHash names
used by the advanced launch gate.

Migrated verbatim (unchanged logic) from HYBA_PROD_READY's
`src/al_haras/production_guard.py` on 2026-07-13 as part of Al Haras
consolidation into HYBA_INTELLIGENCE.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "AKIA",
    "NICEHASH_SECRET=",
    "WALLET_PRIVATE_KEY",
    "PRODUCTION_WALLET_SEED",
)
REQUIRED_ROLLBACK_SECTIONS = ("stop", "revoke", "restore", "audit")

API_KEY_ENV_NAMES = (
    "MIDAS_API_KEY",
    "HYBA_MINING_API_KEY",
    "MIDAS_MINING_API_KEY",
    "NICEHASH_API_KEY",
)
WALLET_ENV_NAMES = (
    "MIDAS_WALLET_ADDRESS",
    "HYBA_MINING_WALLET",
    "MIDAS_MINING_WALLET",
    "NICEHASH_WALLET_ADDRESS",
    "BTC_WALLET_ADDRESS",
)
SECRET_MANAGER_ENV_NAMES = (
    "HYBA_SECRET_MANAGER_URI",
    "GOOGLE_SECRET_MANAGER_PROJECT",
    "AWS_SECRETS_MANAGER_SECRET_ID",
    "VAULT_ADDR",
)
BYPASS_FLAGS = (
    "ALHARAS_BYPASS_GATES",
    "MIDAS_BYPASS_SECURITY",
    "HYBA_FORCE_LAUNCH",
)
UNSAFE_DEV_FLAGS = (
    "ALHARAS_ALLOW_DEV_DEFAULTS",
    "MIDAS_ALLOW_DEV_DEFAULTS",
)
PRIVATE_MATERIAL_ENV_NAMES = (
    "MIDAS_WALLET_PRIVATE_KEY",
    "MIDAS_WALLET_SEED",
    "HYBA_MINING_WALLET_PRIVATE_KEY",
    "HYBA_MINING_WALLET_SEED",
    "NICEHASH_SECRET",
    "NICEHASH_SECRET_KEY",
    "PRODUCTION_WALLET_SEED",
    "WALLET_PRIVATE_KEY",
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "force", "on"}


def _first_present(env: Mapping[str, str], names: Sequence[str]) -> tuple[str | None, str | None]:
    for name in names:
        value = env.get(name)
        if value:
            return name, value
    return None, None


def _envelope(
    status: str, reason: str, evidence: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "subsystem": "al_haras",
        "status": status,
        "reason": reason,
        "evidence": dict(evidence or {}),
        "audit": {"route": "launch_security_guard", "reason": reason, "status": status},
    }


def detect_secret_markers(blobs: Sequence[str]) -> dict[str, Any]:
    findings = [marker for blob in blobs for marker in SECRET_MARKERS if marker in blob]
    if findings:
        return _envelope(
            "BLOCKED", "committed secret marker detected", {"findings": sorted(set(findings))}
        )
    return _envelope("READY", "no committed secret markers detected", {"scanned_blobs": len(blobs)})


def validate_launch_security(
    env: Mapping[str, str] | None, *, bypass_requested: bool = False
) -> dict[str, Any]:
    """Validate launch-time Al-Haras controls and return a JSON-safe envelope.

    The guard accepts only secret references supplied through environment or a
    declared secret-manager contract. It never accepts private wallet material
    in process configuration and it blocks production launches unless they are
    explicitly guarded rehearsal/dry-run launches.
    """

    if not isinstance(env, Mapping):
        return _envelope("BLOCKED", "environment config is required")

    bypass_flags = [name for name in BYPASS_FLAGS if _truthy(env.get(name))]
    if bypass_requested or bypass_flags:
        return _envelope(
            "BLOCKED",
            "launch gate bypass attempt rejected",
            {"bypass_requested": bypass_requested, "flag_names": bypass_flags},
        )

    unsafe_flags = [name for name in UNSAFE_DEV_FLAGS if _truthy(env.get(name))]
    if unsafe_flags:
        return _envelope(
            "BLOCKED",
            "unsafe development defaults rejected for launch",
            {"flag_names": unsafe_flags},
        )

    api_key_name, _ = _first_present(env, API_KEY_ENV_NAMES)
    wallet_name, _ = _first_present(env, WALLET_ENV_NAMES)
    missing = []
    if not api_key_name:
        missing.append("MIDAS_API_KEY")
    if not wallet_name:
        missing.append("MIDAS_WALLET_ADDRESS")
    if missing:
        return _envelope(
            "BLOCKED", "required mining secret references missing", {"missing": missing}
        )

    private_material = [name for name in PRIVATE_MATERIAL_ENV_NAMES if env.get(name)]
    if private_material:
        return _envelope(
            "BLOCKED",
            "wallet private material must not be present in process config",
            {"private_material_env_names": private_material},
        )

    production_mode = env.get("HYBA_ENV", "").strip().lower() == "production"
    dry_run_enabled = _truthy(env.get("MIDAS_DRY_RUN"))
    live_mining_disabled = (env.get("MIDAS_LIVE_MINING", "").strip().lower() in {"0", "false", "no"})
    if production_mode and not (dry_run_enabled or live_mining_disabled):
        return _envelope("BLOCKED", "production launch requires guarded rehearsal before live mode")

    secret_manager_names = [name for name in SECRET_MANAGER_ENV_NAMES if env.get(name)]
    return _envelope(
        "READY",
        "security gates passed with externalized secret references",
        {
            "accepted_api_key_env_name": api_key_name,
            "accepted_wallet_env_name": wallet_name,
            "secret_manager_env_names": secret_manager_names,
            "production_mode": production_mode,
            "dry_run_enabled": dry_run_enabled,
            "live_mining_disabled": live_mining_disabled,
        },
    )


def validate_rollback_plan(text: str) -> dict[str, Any]:
    """Semantic rollback validation — not keyword bingo.

    Requires ordered operational intent: stop services/process, revoke credentials,
    restore last-known-good, write audit evidence. Rejects anagrams, synonym spam
    without verbs, and unordered word salad.
    """
    if not isinstance(text, str) or not text.strip():
        return _envelope("HALTED", "rollback plan empty", {"missing": list(REQUIRED_ROLLBACK_SECTIONS)})

    lowered = text.lower()
    # Normalize whitespace
    compact = " ".join(lowered.split())

    # Semantic markers (verb + object patterns)
    patterns = {
        "stop": (
            "stop service", "stop services", "stop process", "stop mining", "halt service",
            "shut down", "shutdown", "kill process", "terminate process", "disable live",
            "1. stop", "step 1: stop", "stop the",
        ),
        "revoke": (
            "revoke key", "revoke keys", "revoke credential", "revoke credentials",
            "revoke token", "revoke access", "rotate secret", "invalidate session",
            "2. revoke", "step 2: revoke",
        ),
        "restore": (
            "restore backup", "restore last", "restore known", "restore from",
            "rollback to", "revert to", "restore snapshot", "restore lkg",
            "3. restore", "step 3: restore",
        ),
        "audit": (
            "write audit", "append audit", "audit log", "audit entry", "seal audit",
            "record audit", "emit audit", "audit trail", "4. audit", "step 4: audit",
        ),
    }

    missing = []
    positions: dict[str, int] = {}
    for section, alts in patterns.items():
        pos = -1
        for alt in alts:
            i = compact.find(alt)
            if i >= 0 and (pos < 0 or i < pos):
                pos = i
        # bare keyword alone is insufficient unless accompanied by operational neighbor
        if pos < 0:
            # allow bare word only if adjacent operational context within 40 chars
            bare = compact.find(section)
            if bare >= 0:
                window = compact[max(0, bare - 24) : bare + 40]
                ops = ("service", "process", "key", "credential", "backup", "snapshot",
                       "log", "trail", "token", "access", "mining", "known", "lkg")
                if any(o in window for o in ops):
                    pos = bare
        if pos < 0:
            missing.append(section)
        else:
            positions[section] = pos

    if missing:
        return _envelope("HALTED", "rollback plan missing required steps", {"missing": missing})

    # Order must be stop -> revoke -> restore -> audit (monotonic positions)
    order = ["stop", "revoke", "restore", "audit"]
    idxs = [positions[s] for s in order]
    if idxs != sorted(idxs):
        return _envelope(
            "HALTED",
            "rollback plan steps out of operational order",
            {"positions": positions, "required_order": order},
        )

    # Reject pure keyword packing without structure (too short / no newlines or numbering)
    if len(compact) < 48 and not any(ch.isdigit() for ch in compact):
        return _envelope("HALTED", "rollback plan lacks operational detail", {"length": len(compact)})

    return _envelope(
        "READY",
        "rollback plan semantically valid: stop/revoke/restore/audit in order",
        {"positions": positions},
    )
