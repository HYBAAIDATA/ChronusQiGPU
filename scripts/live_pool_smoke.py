"""Run one bounded, live Stratum share-acceptance smoke test.

The script is intentionally the only convenience layer: it delegates hashing,
submission, and pool verdict handling to ``mining/stratum_bridge.py``. It
writes local setup to the ignored ``.env`` and uses a separate ignored runtime
config for the smoke process.
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_PYTHON = ROOT / "mla1517_platform_v3.4" / "python"
if str(PLATFORM_PYTHON) not in sys.path:
    sys.path.insert(0, str(PLATFORM_PYTHON))

import runtime_config

POOLS = {
    "viabtc": "btc.viabtc.top:3333",
    "braiins": "stratum.braiins.com:3333",
}


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _write_env(path: Path, updates: dict[str, str]) -> None:
    existing = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    remaining = dict(updates)
    rendered: list[str] = []
    for line in existing:
        key, separator, _ = line.partition("=")
        if separator and key.strip() in remaining:
            rendered.append(f"{key.strip()}={remaining.pop(key.strip())}")
        else:
            rendered.append(line)
    if remaining:
        if rendered and rendered[-1]:
            rendered.append("")
        rendered.extend(f"{key}={value}" for key, value in sorted(remaining.items()))
    path.write_text("\n".join(rendered) + "\n", encoding="utf-8")


def _password(args: argparse.Namespace) -> str:
    password = os.environ.get(args.password_env, "")
    if password:
        return password
    return getpass.getpass(f"{args.pool} password for {args.worker}: ")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=sorted(POOLS), required=True)
    parser.add_argument("--worker", required=True, help="Pool account.worker identity")
    parser.add_argument(
        "--password-env",
        default="PYTHIA_SMOKE_POOL_PASSWORD",
        help="Environment variable holding the password; otherwise prompts securely",
    )
    parser.add_argument("--endpoint", help="Override the catalog endpoint for the selected pool")
    parser.add_argument("--backend", choices=("auto", "cpu", "gpu", "opencl"), default="cpu")
    parser.add_argument("--window", type=int, default=200000)
    parser.add_argument("--max-runtime", type=float, default=600.0)
    parser.add_argument(
        "--confirm-live-submit",
        action="store_true",
        help="Required acknowledgement that this sends at most one real share",
    )
    parser.add_argument(
        "--disarm-after",
        action="store_true",
        help="Disable live submission in the smoke runtime config when the test exits",
    )
    return parser


def _validate(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not args.confirm_live_submit:
        parser.error("--confirm-live-submit is required for a real pool submission")
    if not 1 <= args.window <= runtime_config.WINDOW_MAX:
        parser.error(f"--window must be in [1,{runtime_config.WINDOW_MAX}]")
    if not 1 <= args.max_runtime <= 600:
        parser.error("--max-runtime must be in [1,600]")
    if any(character.isspace() for character in args.worker) or len(args.worker) > 128:
        parser.error("--worker must be a non-empty account.worker identity without whitespace")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    _validate(args, parser)

    endpoint = args.endpoint or POOLS[args.pool]
    password = _password(args)
    if not password:
        parser.error("a non-empty pool password is required")

    env_path = ROOT / ".env"
    existing_env = _load_env(env_path)
    admin_key = existing_env.get("EUCLID_ADMIN_API_KEY") or secrets.token_hex(32)
    identity_secret = existing_env.get("PYTHIA_IDENTITY_HMAC_SECRET") or secrets.token_hex(32)
    _write_env(
        env_path,
        {
            "EUCLID_ADMIN_API_KEY": admin_key,
            "MLA1517_STRATUM_ENDPOINT": endpoint,
            "MLA1517_STRATUM_PASSWORD": password,
            "MLA1517_STRATUM_USER": args.worker,
            "PYTHIA_IDENTITY_HMAC_SECRET": identity_secret,
            "PYTHIA_POOL_PROFILE": args.pool,
        },
    )

    smoke_config = ROOT / "data" / "live_pool_smoke_config.json"
    config = runtime_config.default_config()
    config["pools"] = [
        {
            "endpoint": endpoint,
            "worker": args.worker,
            "password": password,
            "enabled": True,
        }
    ]
    config["window"] = args.window
    config["live_submit"] = {
        "enabled": True,
        "approval_id": runtime_config.identity_commit(endpoint, args.worker),
    }

    previous_config_path = os.environ.get("PYTHIA_RUNTIME_CONFIG")
    os.environ["PYTHIA_RUNTIME_CONFIG"] = str(smoke_config)
    try:
        runtime_config.save(config)
    finally:
        if previous_config_path is None:
            os.environ.pop("PYTHIA_RUNTIME_CONFIG", None)
        else:
            os.environ["PYTHIA_RUNTIME_CONFIG"] = previous_config_path

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_dir = ROOT / "smoke-artifacts"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"live-pool-{args.pool}-{timestamp}.log"
    bridge_env = os.environ.copy()
    bridge_env.update(
        {
            "HYBA_AUTONOMOUS_EXTERNAL_ACTIONS": "true",
            "HYBA_ENABLE_LIVE_SHARE_SUBMIT": "true",
            "HYBA_LIVE_SHARE_APPROVAL_ID": config["live_submit"]["approval_id"],
            "PYTHIA_RUNTIME_CONFIG": str(smoke_config),
        }
    )
    command = [
        sys.executable,
        str(ROOT / "mining" / "stratum_bridge.py"),
        "--pool",
        endpoint,
        "--worker",
        args.worker,
        "--password",
        password,
        "--submit-test",
        "--continuous",
        "--backend",
        args.backend,
        "--window",
        str(args.window),
        "--max-shares",
        "1",
        "--max-runtime",
        str(args.max_runtime),
    ]
    print(f"Starting one-share live smoke against {endpoint} as {args.worker}.")
    print(f"Bridge log: {log_path}")
    try:
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(
                command, cwd=ROOT, env=bridge_env, stdout=log, stderr=subprocess.STDOUT
            )
        output = log_path.read_text(encoding="utf-8", errors="replace")
        if "Pool submission verdict: *** ACCEPTED ***" in output:
            print("PASS: pool accepted one submitted share.")
            return 0
        print("FAIL: no accepted share before the bounded smoke run ended.", file=sys.stderr)
        return result.returncode or 1
    finally:
        if args.disarm_after:
            previous_config_path = os.environ.get("PYTHIA_RUNTIME_CONFIG")
            os.environ["PYTHIA_RUNTIME_CONFIG"] = str(smoke_config)
            try:
                current = runtime_config.load()
                current["live_submit"] = {"enabled": False, "approval_id": ""}
                runtime_config.save(current)
                print("Live-submit smoke config disarmed.")
            finally:
                if previous_config_path is None:
                    os.environ.pop("PYTHIA_RUNTIME_CONFIG", None)
                else:
                    os.environ["PYTHIA_RUNTIME_CONFIG"] = previous_config_path


if __name__ == "__main__":
    raise SystemExit(main())
