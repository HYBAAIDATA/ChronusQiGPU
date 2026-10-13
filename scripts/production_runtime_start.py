#!/usr/bin/env python3
"""Production runtime startup and pre-flight validation harness.

Translates production environment secrets (ViaBTC, Braiins, Phylotaxis state/storage)
into canonical runtime configuration and executes fail-closed checks prior to worker ignition.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PY_DIR = REPO_ROOT / "chronus" / "mla1517_platform" / "python"
for p in (str(REPO_ROOT), str(PY_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def configure_environment() -> dict[str, str]:
    """Map external / GitHub environment variables to internal canonical names."""
    env_updates: dict[str, str] = {}

    # Map ViaBTC pool credentials
    viabtc_user = os.getenv("VIABTC_USER") or os.getenv("MLA1517_VIABTC_USER", "")
    viabtc_pass = os.getenv("VIABTC_PASSWORD") or os.getenv("MLA1517_VIABTC_PASSWORD", "")
    if viabtc_user:
        env_updates["MLA1517_VIABTC_USER"] = viabtc_user
        env_updates["MLA1517_STRATUM_USER"] = viabtc_user
    if viabtc_pass:
        env_updates["MLA1517_VIABTC_PASSWORD"] = viabtc_pass
        env_updates["MLA1517_STRATUM_PASSWORD"] = viabtc_pass

    # Map Braiins pool credentials
    braiins_user = os.getenv("BRAIINS_USER") or os.getenv("MLA1517_BRAIINS_USER", "")
    braiins_pass = os.getenv("BRAIINS_PASSWORD") or os.getenv("MLA1517_BRAIINS_PASSWORD", "")
    if braiins_user:
        env_updates["MLA1517_BRAIINS_USER"] = braiins_user
    if braiins_pass:
        env_updates["MLA1517_BRAIINS_PASSWORD"] = braiins_pass

    # Default pool configuration
    env_updates.setdefault("PYTHIA_POOLS", "viabtc,braiins")
    env_updates.setdefault("PYTHIA_POOL_PROFILE", "viabtc")

    # Map Phylaxis runtime configuration
    phylaxis_env = os.getenv("PHYLAXIS_ENVIRONMENT", "production")
    env_updates["PHYLAXIS_ENVIRONMENT"] = phylaxis_env

    for k, v in env_updates.items():
        os.environ[k] = v

    return env_updates


def validate_preflight(dry_run: bool = True) -> dict[str, Any]:
    """Run non-destructive validation checks before worker startup."""
    configure_environment()

    checks: list[dict[str, Any]] = []

    # 1. Check pool credentials
    viabtc_u = os.getenv("MLA1517_VIABTC_USER", "")
    viabtc_p = os.getenv("MLA1517_VIABTC_PASSWORD", "")
    braiins_u = os.getenv("MLA1517_BRAIINS_USER", "")
    braiins_p = os.getenv("MLA1517_BRAIINS_PASSWORD", "")

    checks.append({
        "check": "viabtc_credentials",
        "passed": bool(viabtc_u and viabtc_p),
        "user": viabtc_u if viabtc_u else None,
    })
    checks.append({
        "check": "braiins_credentials",
        "passed": bool(braiins_u and braiins_p),
        "user": braiins_u if braiins_u else None,
    })

    # 2. Check Phylaxis environment
    db_host = os.getenv("PHYLAXIS_DB_HOST", "")
    storage_ep = os.getenv("PHYLAXIS_STORAGE_ENDPOINT", "")
    checks.append({
        "check": "phylaxis_persistence",
        "configured": bool(db_host or storage_ep),
        "db_host": db_host or "local_embedded",
        "storage_endpoint": storage_ep or "local_cas",
    })

    # 3. Check Python import path resolution
    try:
        import control_api  # noqa: F401
        import system_fabric  # noqa: F401
        import pool_catalog  # noqa: F401
        imports_ok = True
        import_error = None
    except Exception as exc:
        imports_ok = False
        import_error = str(exc)

    checks.append({
        "check": "canonical_imports",
        "passed": imports_ok,
        "error": import_error,
    })

    all_passed = all(c.get("passed", True) for c in checks)
    return {
        "status": "READY" if all_passed else "FAILED_PREFLIGHT",
        "dry_run": dry_run,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Production runtime startup and pre-flight harness.")
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration without starting processes.")
    parser.add_argument("--host", default="0.0.0.0", help="Control API bind host.")
    parser.add_argument("--port", type=int, default=3000, help="Control API bind port.")
    parser.add_argument("--web-root", default=str(REPO_ROOT / "dist" / "public"), help="Static web root.")
    args = parser.parse_args()

    result = validate_preflight(dry_run=args.dry_run)
    print(json.dumps(result, indent=2))

    if result["status"] != "READY":
        print("[FAIL-CLOSED] Pre-flight validation checks failed. Aborting startup.", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[PRE-FLIGHT] Validation succeeded in dry-run mode.")
        return 0

    print("[STARTUP] Launching canonical control plane entrypoint...")
    import control_api
    control_api.main(["--host", args.host, "--port", str(args.port), "--web-root", args.web_root])
    return 0


if __name__ == "__main__":
    sys.exit(main())
