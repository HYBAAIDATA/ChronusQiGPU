"""Validate canonical runtime configuration without network or mining startup."""

import argparse
import json
import os
import sys
from pathlib import Path, PurePosixPath

_PLATFORM_DIR = Path(__file__).resolve().parent.parent / "chronus" / "mla1517_platform" / "python"
if str(_PLATFORM_DIR) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_DIR))

from startup_contract import StartupConfigError, validate_worker_identity


REQUIRED = (
    "MLA1517_STRATUM_USER",
    "MLA1517_STRATUM_PASSWORD",
    "MLA1517_VIABTC_USER",
    "MLA1517_VIABTC_PASSWORD",
    "MLA1517_BRAIINS_USER",
    "MLA1517_BRAIINS_PASSWORD",
    "EUCLID_ADMIN_API_KEY",
    "PYTHIA_STORAGE_DB",
    "PYTHIA_STORAGE_ROOT",
    "PYTHIA_STORAGE_CUSTODY_ROOT",
    "PYTHIA_STORAGE_TENANT",
    "PYTHIA_STORAGE_INTEGRITY_KEY_HEX",
    "PYTHIA_STORAGE_CUSTODY_KEY_HEX",
    "PYTHIA_M3_ACTOR",
    "PYTHIA_M3_AL_HARAS_TOKEN",
)
PATHS = ("PYTHIA_STORAGE_DB", "PYTHIA_STORAGE_ROOT", "PYTHIA_STORAGE_CUSTODY_ROOT")
KEYS = ("PYTHIA_STORAGE_INTEGRITY_KEY_HEX", "PYTHIA_STORAGE_CUSTODY_KEY_HEX")


def evaluate(env):
    checks = []

    def check(name, valid):
        checks.append({"name": name, "state": "CONFIGURED" if valid else "BLOCKED"})

    for name in REQUIRED:
        value = env.get(name, "")
        valid = bool(value.strip())
        if name.endswith("_USER") and valid:
            try:
                validate_worker_identity(value)
            except StartupConfigError:
                valid = False
        if name in KEYS and valid:
            try:
                valid = len(bytes.fromhex(value)) >= 32
            except ValueError:
                valid = False
        if name in PATHS and valid:
            valid = Path(value).is_absolute() or PurePosixPath(value).is_absolute()
        check(name, valid)
    check("PYTHIA_POOLS", env.get("PYTHIA_POOLS") == "viabtc,braiins")
    check("PYTHIA_POOL_PROFILE", env.get("PYTHIA_POOL_PROFILE") == "viabtc")
    check(
        "primary_identity_matches_viabtc",
        bool(env.get("MLA1517_STRATUM_USER"))
        and env.get("MLA1517_STRATUM_USER") == env.get("MLA1517_VIABTC_USER"),
    )
    check(
        "primary_password_matches_viabtc",
        bool(env.get("MLA1517_STRATUM_PASSWORD"))
        and env.get("MLA1517_STRATUM_PASSWORD") == env.get("MLA1517_VIABTC_PASSWORD"),
    )
    check("PYTHIA_M3_REQUIRED", env.get("PYTHIA_M3_REQUIRED") == "1")
    check("PYTHIA_AUTOSTART_WORKERS", env.get("PYTHIA_AUTOSTART_WORKERS") == "0")
    check(
        "external_phylaxis_variables_not_silently_ignored",
        not any(name.startswith("PHYLAXIS_") and value for name, value in env.items()),
    )
    return {
        "schema": "pythia.runtime_environment_preflight/1",
        "state": "BLOCKED" if any(c["state"] == "BLOCKED" for c in checks) else "CONFIGURED",
        "scope": "canonical environment configuration only; not connectivity or deployment proof",
        "network_attempted": False,
        "mining_started": False,
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(dict(os.environ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Runtime configuration: {report['state']}")
    for check in report["checks"]:
        if check["state"] == "BLOCKED":
            print(f"BLOCKED: {check['name']}")
    return 2 if report["state"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
