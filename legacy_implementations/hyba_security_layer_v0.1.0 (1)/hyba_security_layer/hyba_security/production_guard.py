"""HYBA / AL HARAS security layer - fail-closed launch guard.

CLAIM LANE: IMPLEMENTED. Deny-by-default production readiness gate.

Provenance: `production_guard.py` was assessed KEEP - real (secret markers,
bypass reject, wallet-key env block, property tests) in the AL HARAS package
audit, 20 Jul 2026. Bypass is treated as hostile, not as an escape hatch.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

CLAIM_LANE: Final[str] = "IMPLEMENTED"

STATUS_READY: Final[str] = "READY"
STATUS_BLOCKED: Final[str] = "BLOCKED"

# Any env key containing these fragments is a bypass attempt when truthy.
BYPASS_FRAGMENTS: Final[tuple[str, ...]] = (
    "BYPASS",
    "SKIP_CHECK",
    "SKIP_SECURITY",
    "DISABLE_SECURITY",
    "DISABLE_GUARD",
    "FORCE_DEPLOY",
    "IGNORE_GATE",
    "NO_VERIFY",
)

# Any env key containing these fragments must never be present in production.
PRIVATE_MATERIAL_FRAGMENTS: Final[tuple[str, ...]] = (
    "PRIVATE_KEY",
    "SECRET_KEY",
    "WALLET_KEY",
    "WALLET_SEED",
    "MNEMONIC",
    "SEED_PHRASE",
    "SIGNING_KEY",
)

# Any env VALUE containing these markers is leaked secret material.
SECRET_VALUE_MARKERS: Final[tuple[str, ...]] = (
    "-----BEGIN",
    "AKIA",
    "ASIA",
    "ghp_",
    "xoxb-",
    "sk_live_",
)

# Values that count as "true" regardless of casing.
TRUTHY: Final[frozenset[str]] = frozenset(
    {"1", "true", "yes", "on", "y", "enabled", "enable"}
)

REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "HYBA_ENV",
    "HYBA_API_KEY",
    "HYBA_RELEASE_SHA",
)

DEV_DEFAULTS: Final[frozenset[str]] = frozenset(
    {"changeme", "password", "test", "dev", "localhost", "admin", "secret", ""}
)


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUTHY


def evaluate(env: Any, *, rehearsal_completed: bool = False) -> dict[str, Any]:
    """Return a launch decision. Deny-by-default: anything unclear is BLOCKED."""
    reasons: list[str] = []

    if not isinstance(env, Mapping):
        return {
            "status": STATUS_BLOCKED,
            "reasons": ["environment is not a mapping"],
            "claim_lane": CLAIM_LANE,
            "fail_closed": True,
        }
    if len(env) == 0:
        return {
            "status": STATUS_BLOCKED,
            "reasons": ["empty environment"],
            "claim_lane": CLAIM_LANE,
            "fail_closed": True,
        }

    for raw_key, raw_value in env.items():
        key = str(raw_key).upper()
        value = raw_value

        for fragment in BYPASS_FRAGMENTS:
            if fragment in key and _is_truthy(value):
                reasons.append(f"bypass flag set: {raw_key}")

        for fragment in PRIVATE_MATERIAL_FRAGMENTS:
            if fragment in key:
                reasons.append(f"private material in environment: {raw_key}")

        text_value = value if isinstance(value, str) else str(value)
        for marker in SECRET_VALUE_MARKERS:
            if marker in text_value:
                reasons.append(f"secret marker '{marker}' in value of {raw_key}")

    for required in REQUIRED_KEYS:
        if required not in env:
            reasons.append(f"missing required key: {required}")
        elif str(env[required]).strip().lower() in DEV_DEFAULTS:
            reasons.append(f"development default value for {required}")

    if str(env.get("HYBA_ENV", "")).strip().lower() == "production" and not rehearsal_completed:
        reasons.append("production launch without completed rehearsal")

    if not str(env.get("HYBA_ROLLBACK_PLAN", "")).strip():
        reasons.append("no rollback plan declared")

    status = STATUS_BLOCKED if reasons else STATUS_READY
    return {
        "status": status,
        "reasons": sorted(set(reasons)),
        "claim_lane": CLAIM_LANE,
        "fail_closed": True,
        "rehearsal_completed": bool(rehearsal_completed),
    }


def is_ready(env: Any, *, rehearsal_completed: bool = False) -> bool:
    return evaluate(env, rehearsal_completed=rehearsal_completed)["status"] == STATUS_READY
