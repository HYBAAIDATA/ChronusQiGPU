# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""``hyba-mine``: the HYBA Mine command line.

Typical first run on a Mac (``scripts/mine/setup_mac.sh`` does this for you)::

    hyba-mine login viabtc          # username and password typed locally
    hyba-mine approve               # operator approval for this machine
    hyba-mine preflight             # BIST, credentials, Stratum handshake
    hyba-mine start                 # pre-flight again, then mine
    hyba-mine status                # every value from the ledger
    hyba-mine pool use braiins      # switch pool while mining
    hyba-mine stop
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import getpass
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from hyba_mine import PRODUCT_BOUNDARY, __version__
from hyba_mine.bist import run_preflight
from hyba_mine.control import (
    BACKENDS,
    PREFERENCES,
    ROUTES,
    clear_block,
    grant_approval,
    load_state,
    request_pool_switch,
    revoke_approval,
    update_state,
)
from hyba_mine.credentials import CredentialMissing, CredentialStoreError, make_login, open_store, require_login
from hyba_mine.dispatch import DispatchError, FleetDispatcher, LocalIGPUDispatcher, load_fleet_executor
from hyba_mine.ledger import Ledger
from hyba_mine.logsafe import configure_logging
from hyba_mine.paths import Layout
from hyba_mine.pools import POOL_CATALOG, POOL_IDS, TLS_POLICIES, get_pool
from hyba_mine.runtime import EXIT_CONFIG, EXIT_PREFLIGHT, MinerRuntime, RuntimeOptions
from hyba_mine.status import render_text, summarize

log = logging.getLogger("hyba_mine.cli")
REPO_RUN_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "mine" / "run.sh"


def _layout() -> Layout:
    return Layout().prepare()


def _ledger(layout: Layout) -> Ledger:
    return Ledger(layout.ledger, layout.ledger_lock)


def _print(text: str = "") -> None:
    print(text, flush=True)


# ------------------------------------------------------------------ commands
def cmd_pools(args) -> int:
    for profile in POOL_CATALOG.values():
        _print(f"{profile.pool_id:9} {profile.name}")
        for endpoint in profile.endpoints:
            _print(f"          {endpoint.url}")
        _print(f"          username: {profile.username_format}  (e.g. {profile.username_example})")
        _print(f"          password: {profile.password_hint}")
        _print(f"          {profile.notes}")
    return 0


def cmd_login(args) -> int:
    layout = _layout()
    profile = get_pool(args.pool)
    state = load_state(layout)
    _print(f"{profile.name} login. Username format: {profile.username_format} (e.g. {profile.username_example}).")
    username = args.username if args.username else input("Username: ").strip()
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass(f"Password ({profile.password_hint}): ")
    login = make_login(profile.pool_id, username, password)
    store = open_store(args.store or state.get("credential_store"), layout)
    store.put(profile.pool_id, login)
    update_state(layout, credential_store=store.backend, active_pool=state.get("active_pool") or profile.pool_id)
    clear_block(layout, profile.pool_id)
    _ledger(layout).append("login_stored", {"pool": profile.pool_id, "store": store.backend, **login.public()})
    _print(f"Stored the {profile.name} login in the {store.backend} store (login {login.fingerprint}, worker {login.worker}).")
    return 0


def cmd_logout(args) -> int:
    layout = _layout()
    profile = get_pool(args.pool)
    store = open_store(load_state(layout).get("credential_store"), layout)
    removed = store.delete(profile.pool_id)
    _ledger(layout).append("login_removed", {"pool": profile.pool_id, "removed": removed})
    _print(f"{profile.name} login {'removed' if removed else 'was not stored'}.")
    return 0


def cmd_approve(args) -> int:
    layout = _layout()
    _print(PRODUCT_BOUNDARY)
    if not args.yes:
        answer = input("Type APPROVE to let HYBA Mine mine on this machine: ").strip()
        if answer != "APPROVE":
            _print("Not approved. Nothing will mine on this machine.")
            return 1
    record = grant_approval(layout)
    _ledger(layout).append("approval_granted", {"host": record["host"], "approved_at": record["approved_at"]})
    _print(f"Approved on {record['host']} at {record['approved_at']}.")
    return 0


def cmd_revoke(args) -> int:
    layout = _layout()
    revoked = revoke_approval(layout)
    _ledger(layout).append("approval_revoked", {"revoked": revoked})
    _print("Approval revoked; HYBA Mine will not start on this machine." if revoked else "There was no approval.")
    return 0


def _miner_pid(layout: Layout) -> Optional[int]:
    try:
        pid = int(layout.pid.read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return None
    done = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=False)
    return pid if "hyba" in done.stdout.lower() else None


def cmd_pool(args) -> int:
    layout = _layout()
    state = load_state(layout)
    if args.action == "show":
        _print(json.dumps({"active_pool": state.get("active_pool"), "tls_policy": state.get("tls_policy"),
                           "route": state.get("route"), "blocked": state.get("blocked")}, indent=2))
        return 0
    profile = get_pool(args.pool)
    store = open_store(state.get("credential_store"), layout)
    try:
        require_login(store, profile.pool_id)
    except CredentialMissing as exc:
        _print(str(exc))
        return EXIT_CONFIG
    update_state(layout, active_pool=profile.pool_id)
    pid = _miner_pid(layout)
    if pid is None:
        _print(f"Active pool set to {profile.name}; it is used the next time HYBA Mine starts.")
        return 0
    request = request_pool_switch(layout, profile.pool_id)
    _print(f"Asked the running miner (pid {pid}) to switch to {profile.name}...")
    deadline = time.monotonic() + args.wait
    ledger = _ledger(layout)
    while time.monotonic() < deadline:
        for record in ledger.records():
            data = record.get("data") or {}
            if data.get("request_id") == request["request_id"] and record["kind"] in ("pool_switch_applied", "pool_switch_refused"):
                verdict = "switched" if record["kind"] == "pool_switch_applied" else f"refused: {data.get('reason')}"
                _print(f"Miner {verdict}.")
                return 0 if record["kind"] == "pool_switch_applied" else EXIT_CONFIG
        time.sleep(0.5)
    _print("The miner has not confirmed the switch yet; check: hyba-mine status")
    return 0


def _print_report(report) -> None:
    for check in report.checks:
        mark = "PASS" if check.passed else "FAIL"
        detail = f" - {check.detail}" if check.detail else ""
        _print(f"  [{mark}] {check.name}{detail}")
    if report.route is not None:
        route = report.route.to_dict()
        _print(f"  Backend: requested {route.get('requested_backend', route['requested'])}, prefer "
               f"{route.get('preference', 'ours')}, detected {', '.join(route.get('detected_backends') or [])}"
               f" -> executed {route.get('executed_backend') or route['executed']} ({route['executed']})"
               f" (fallback_reason: {route['fallback_reason'] or 'none'})")
    _print("Pre-flight PASSED." if report.passed else "Pre-flight FAILED: mining is blocked.")
    metal_failed = [c for c in report.checks if not c.passed and "metal" in c.name.lower()]
    if not report.passed and metal_failed:
        _print("  The Metal lane failed its self-test. To mine on the Chronus iGPU (our software-defined GPU):")
        _print("    hyba-mine start --backend igpu      (or: scripts/mine/run.sh --backend igpu)")


def _preflight(args, layout: Layout, pool_id: str, network: bool, close_lane: bool):
    state = load_state(layout)
    store = None
    try:
        store = open_store(state.get("credential_store"), layout)
    except (CredentialStoreError, ValueError) as exc:
        _print(f"Credential store unavailable: {exc}")
    report = run_preflight(
        layout, _ledger(layout), store, pool_id,
        requested_route=_backend(args, state),
        prefer=getattr(args, "prefer", None) or state.get("prefer") or "ours",
        tls_policy=args.tls or state.get("tls_policy") or "prefer",
        network=network,
        mode_a_workers=args.workers,
    )
    _print_report(report)
    if close_lane and report.lane is not None:
        report.lane.close()
    return report, store


def _backend(args, state: dict) -> str:
    chosen = getattr(args, "backend", None) or getattr(args, "route", None) or state.get("route") or "auto"
    return "igpu" if chosen == "mode_a" else chosen


def _active_pool(args, layout: Layout) -> Optional[str]:
    pool = args.pool or load_state(layout).get("active_pool")
    if not pool:
        _print("No pool selected. Run: hyba-mine login <viabtc|braiins|nicehash|ckpool>")
    return pool


def cmd_preflight(args) -> int:
    layout = _layout()
    configure_logging(logging.WARNING, layout.log_file)
    pool = _active_pool(args, layout)
    if pool is None:
        return EXIT_CONFIG
    report, _ = _preflight(args, layout, pool, network=not args.offline, close_lane=True)
    if args.json:
        _print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.passed else EXIT_PREFLIGHT


def cmd_start(args) -> int:
    layout = _layout()
    configure_logging(logging.INFO, layout.log_file)
    lock_fd = os.open(layout.instance_lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        _print("HYBA Mine is already running on this machine (see: hyba-mine status).")
        return EXIT_CONFIG
    try:
        pool = _active_pool(args, layout)
        if pool is None:
            return EXIT_CONFIG
        _print(f"HYBA Mine {__version__}: pre-flight for {get_pool(pool).name}")
        report, store = _preflight(args, layout, pool, network=True, close_lane=False)
        if not report.passed:
            return EXIT_PREFLIGHT
        state = load_state(layout)
        if args.fleet == "on":
            report.lane.close()
            try:
                executor = load_fleet_executor(args.fleet_coordinator, args.fleet_token_file, args.fleet_tls_ca)
            except DispatchError as exc:
                _print(f"{exc}; refusing --fleet on.")
                return EXIT_CONFIG
            if executor is None:
                _print("The iGPU fleet package (chronus.fleet) is not installed; refusing --fleet on.")
                return EXIT_CONFIG
            dispatcher = FleetDispatcher(executor, report.route, backend=_backend(args, state),
                                         prefer=args.prefer or state.get("prefer") or "ours")
        else:
            dispatcher = LocalIGPUDispatcher(report.lane, report.route)
        options = RuntimeOptions(
            tls_policy=args.tls or state.get("tls_policy") or "prefer",
            max_seconds=args.max_seconds,
        )
        runtime = MinerRuntime(layout, _ledger(layout), store, dispatcher, pool, options)
        layout.pid.write_text(f"{os.getpid()}\n")
        console = None
        if args.console_port:
            from hyba_mine.console import ConsoleServer

            try:
                console = ConsoleServer(layout, _ledger(layout), args.console_port).start()
                _print(f"Local status page: {console.url}")
            except OSError as exc:
                log.warning("status page not started: %s", exc)
        _print(f"Mining on {report.route.executed} for {get_pool(pool).name}. Stop with: hyba-mine stop")

        async def main() -> int:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, runtime.request_stop, f"signal {sig.name}")
            return await runtime.run(preflight={"passed": True, "route": report.route.to_dict()})

        try:
            code = asyncio.run(main())
        finally:
            if console is not None:
                console.stop()
            dispatcher.close()
            if layout.pid.exists():
                layout.pid.unlink()
        _print(f"HYBA Mine stopped (exit {code}).")
        return code
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def cmd_stop(args) -> int:
    layout = _layout()
    if args.disable_autostart:
        from hyba_mine import autostart

        autostart.disable()
        _print("Auto-start disabled.")
    pid = _miner_pid(layout)
    if pid is None:
        _print("HYBA Mine is not running.")
        return 0
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            _print("HYBA Mine stopped.")
            return 0
        time.sleep(0.25)
    _print(f"HYBA Mine (pid {pid}) did not stop within {args.timeout:g} s.")
    return 1


def cmd_status(args) -> int:
    layout = _layout()
    ledger = _ledger(layout)
    while True:
        summary = summarize(ledger.records())
        _print(json.dumps(summary, indent=2) if args.json else render_text(summary))
        if not args.watch:
            return 0
        time.sleep(args.watch)
        _print()


def cmd_ledger(args) -> int:
    layout = _layout()
    ledger = _ledger(layout)
    if args.action == "verify":
        result = ledger.verify()
        _print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.ok else 1
    records = list(ledger.records())[-args.n:]
    for record in records:
        _print(json.dumps(record, sort_keys=True))
    return 0


def cmd_backends(args) -> int:
    """Detect this Mac's backends, select one from the option and run its known-answer tests."""
    from hyba_mine.bist import select_lane

    state = load_state(_layout())
    backend = _backend(args, state)
    prefer = args.prefer or state.get("prefer") or "ours"
    route, lane, checks = select_lane(backend, prefer=prefer, mode_a_workers=args.workers, full_window=args.full_window)
    if lane is not None:
        lane.close()
    passed = route is not None and all(check.passed for check in checks)
    if args.json:
        _print(json.dumps({"passed": passed, "route": route.to_dict() if route else None,
                           "checks": [c.to_dict() for c in checks]}, indent=2, default=str))
    else:
        for check in checks:
            _print(f"  [{'PASS' if check.passed else 'FAIL'}] {check.name}{' - ' + check.detail if check.detail else ''}")
        if route is not None:
            fields = route.to_dict()
            _print(f"Backend: requested {fields['requested_backend']}, prefer {fields['preference']}, detected "
                   f"{', '.join(fields['detected_backends'])} -> executed {fields['executed_backend']}"
                   f" (fallback_reason: {fields['fallback_reason'] or 'none'})")
        else:
            _print(f"Backend {backend} (prefer {prefer}) is not available here; failing closed.")
    return 0 if passed else EXIT_PREFLIGHT


def cmd_config(args) -> int:
    layout = _layout()
    backend = args.backend or args.route
    backend = "igpu" if backend == "mode_a" else backend
    changes = {key: value for key, value in (("route", backend), ("prefer", args.prefer), ("tls_policy", args.tls))
               if value}
    state = update_state(layout, **changes) if changes else load_state(layout)
    if changes:
        _ledger(layout).append("config_changed", changes)
    shown = {key: state.get(key) for key in ("active_pool", "route", "prefer", "tls_policy", "credential_store")}
    shown["backend"] = shown.pop("route")
    _print(json.dumps(shown, indent=2))
    return 0


def cmd_autostart(args) -> int:
    from hyba_mine import autostart

    layout = _layout()
    if args.action == "enable":
        path = autostart.enable(Path(args.run_script).expanduser(), layout, start=not args.no_start)
        _print(f"Auto-start enabled: {path} (logs in {layout.logs}).")
    elif args.action == "disable":
        autostart.disable()
        _print("Auto-start disabled.")
    _print(json.dumps(autostart.status(), indent=2))
    return 0


# -------------------------------------------------------------------- parser
def _backend_options(p) -> None:
    p.add_argument("--backend", choices=BACKENDS,
                   help="auto (detect, then choose by --prefer) or exactly one backend; absent fails closed")
    p.add_argument("--prefer", choices=PREFERENCES,
                   help="ours (default): the Chronus iGPU even when the Mac has a GPU; host: Metal when it passes")
    p.add_argument("--route", choices=ROUTES, help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hyba-mine", description="HYBA Mine: internal treasury mining runtime.")
    parser.add_argument("--version", action="version", version=f"hyba-mine {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("pools", help="list the four supported pools").set_defaults(func=cmd_pools)

    p = sub.add_parser("login", help="store a pool login on this machine")
    p.add_argument("pool", choices=POOL_IDS)
    p.add_argument("--store", choices=("keychain", "file"))
    p.add_argument("--username")
    p.add_argument("--password-stdin", action="store_true", help="read the password from standard input")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("logout", help="remove a stored pool login")
    p.add_argument("pool", choices=POOL_IDS)
    p.set_defaults(func=cmd_logout)

    p = sub.add_parser("approve", help="operator approval to mine on this machine")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_approve)
    sub.add_parser("revoke", help="withdraw the approval").set_defaults(func=cmd_revoke)

    p = sub.add_parser("pool", help="show or switch the active pool (live while mining)")
    p.add_argument("action", choices=("show", "use"))
    p.add_argument("pool", nargs="?", choices=POOL_IDS)
    p.add_argument("--wait", type=float, default=20.0)
    p.set_defaults(func=cmd_pool)

    for name, func in (("preflight", cmd_preflight), ("start", cmd_start)):
        p = sub.add_parser(name, help="pre-flight checks" if name == "preflight" else "pre-flight, then mine")
        p.add_argument("--pool", choices=POOL_IDS)
        _backend_options(p)
        p.add_argument("--tls", choices=TLS_POLICIES)
        p.add_argument("--workers", type=int, help="Mode A worker processes (default: performance cores)")
        if name == "preflight":
            p.add_argument("--offline", action="store_true", help="skip the Stratum handshake (reports FAIL)")
            p.add_argument("--json", action="store_true")
        else:
            p.add_argument("--console-port", type=int, default=8765, help="local status page port (0 disables)")
            p.add_argument("--fleet", choices=("off", "on"), default="off")
            p.add_argument("--fleet-coordinator", help="fleet coordinator URL (default http://127.0.0.1:8740)")
            p.add_argument("--fleet-token-file", help="fleet token file (default ~/.chronus/fleet/token)")
            p.add_argument("--fleet-tls-ca", help="certificate of the fleet coordinator")
            p.add_argument("--max-seconds", type=float)
        p.set_defaults(func=func)

    p = sub.add_parser("stop", help="stop the running miner")
    p.add_argument("--disable-autostart", action="store_true")
    p.add_argument("--timeout", type=float, default=20.0)
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("status", help="status computed from the ledger")
    p.add_argument("--json", action="store_true")
    p.add_argument("--watch", type=float, default=0.0)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("ledger", help="verify or show the ledger")
    p.add_argument("action", choices=("verify", "tail"))
    p.add_argument("-n", type=int, default=20)
    p.set_defaults(func=cmd_ledger)

    p = sub.add_parser("backends", help="detect backends, select one by --backend/--prefer and run its KATs")
    _backend_options(p)
    p.add_argument("--workers", type=int, help="Chronus iGPU (Mode A) worker processes")
    p.add_argument("--full-window", action="store_true", help="known-answer tests over a full plan window")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_backends)

    p = sub.add_parser("config", help="show or set the default backend, preference and TLS policy")
    _backend_options(p)
    p.add_argument("--tls", choices=TLS_POLICIES)
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("autostart", help="launchd auto-start at login (macOS)")
    p.add_argument("action", choices=("enable", "disable", "status"))
    p.add_argument("--run-script", default=str(REPO_RUN_SCRIPT))
    p.add_argument("--no-start", action="store_true", help="install for next login without loading the agent now")
    p.set_defaults(func=cmd_autostart)
    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "pool" and args.action == "use" and not args.pool:
        parser.error("pool use needs a pool name")
    try:
        return args.func(args)
    except (ValueError, CredentialStoreError) as exc:
        _print(f"error: {exc}")
        return EXIT_CONFIG
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0


if __name__ == "__main__":
    sys.exit(main())
