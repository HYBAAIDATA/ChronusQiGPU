"""Run one bounded, live Stratum share-acceptance smoke test.

The script delegates hashing, submission, and pool verdict handling to
``mining/stratum_bridge.py``. Credentials remain in the parent environment or
secure prompt, never in argv, ``.env``, logs, or a retained runtime config.
"""

from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_PYTHON = ROOT / "chronus/mla1517_platform" / "python"
if str(PLATFORM_PYTHON) not in sys.path:
    sys.path.insert(0, str(PLATFORM_PYTHON))

import runtime_config
from startup_contract import validate_worker_identity

POOLS = {
    "viabtc": "btc.viabtc.top:3333",
    "braiins": "stratum.braiins.com:3333",
}


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
        help=argparse.SUPPRESS,
    )
    return parser


def _validate(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not args.confirm_live_submit:
        parser.error("--confirm-live-submit is required for a real pool submission")
    if not 1 <= args.window <= runtime_config.WINDOW_MAX:
        parser.error(f"--window must be in [1,{runtime_config.WINDOW_MAX}]")
    if not 1 <= args.max_runtime <= 600:
        parser.error("--max-runtime must be in [1,600]")
    try:
        validate_worker_identity(args.worker)
    except ValueError as exc:
        parser.error(str(exc))


def _bridge_command(args: argparse.Namespace, endpoint: str) -> list[str]:
    """Build a command line that contains no credentials."""
    return [
        sys.executable,
        str(ROOT / "mining" / "stratum_bridge.py"),
        "--pool",
        endpoint,
        "--worker",
        args.worker,
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


def _save_ephemeral_config(path: Path, config: dict[str, object]) -> None:
    """Persist live-smoke configuration with owner-only permissions."""
    previous_path = os.environ.get("PYTHIA_RUNTIME_CONFIG")
    previous_umask = os.umask(0o077)
    os.environ["PYTHIA_RUNTIME_CONFIG"] = str(path)
    try:
        runtime_config.save(config)
        path.chmod(0o600)
    finally:
        os.umask(previous_umask)
        if previous_path is None:
            os.environ.pop("PYTHIA_RUNTIME_CONFIG", None)
        else:
            os.environ["PYTHIA_RUNTIME_CONFIG"] = previous_path


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    _validate(args, parser)

    endpoint = args.endpoint or POOLS[args.pool]
    password = _password(args)
    if not password:
        parser.error("a non-empty pool password is required")

    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="live-pool-smoke-", suffix=".json", dir=data_dir
    )
    os.close(descriptor)
    smoke_config = Path(temporary_name)
    smoke_config.chmod(0o600)
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

    _save_ephemeral_config(smoke_config, config)

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
            "PYTHIA_STRATUM_PASSWORD": password,
            "STRATUM_PASSWORD": password,
        }
    )
    command = _bridge_command(args, endpoint)
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
        smoke_config.unlink(missing_ok=True)
        smoke_config.with_suffix(".json.tmp").unlink(missing_ok=True)
        print("Ephemeral live-submit config removed.")


if __name__ == "__main__":
    raise SystemExit(main())
