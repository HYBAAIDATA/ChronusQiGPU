# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""chronus-fleet: run the Chronus iGPU fleet from the command line.

    chronus-fleet init [--tls-host imac.local]       create token, signing key, TLS certificate
    chronus-fleet coordinator --port 8740 [--host 0.0.0.0 for the LAN] [--tls]
    chronus-fleet join --coordinator URL --token-file FILE [--tls-ca CERT] [--backend auto] [--prefer ours]
    chronus-fleet status --coordinator URL --token-file FILE
    chronus-fleet bench [--backend auto] [--prefer ours]  detect backends: probe, self-test, timed runs
    chronus-fleet run --coordinator URL --kernel m15_fold --size 16MiB [--backend auto] [--prefer ours]
    chronus-fleet verify-receipt receipt.json [--public-key HEX]
    chronus-fleet tier status                            tier, entitlement, demand, scale available
    chronus-fleet tier grant --tier 2 --expires 30d      owner, on the coordinator: signed scale grant
    chronus-fleet tier set --tier 1                      owner, on the coordinator: move to a tier

--backend auto|igpu|metal|opencl|cuda|simd|reference picks the backend;
--prefer ours (default) runs the Chronus iGPU even when the host has a GPU,
--prefer host uses the host GPU (Metal, OpenCL or CUDA) when it passes its
self-test. A named backend runs exactly there or fails closed.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import time
import socket
import sys
import threading
from pathlib import Path
from typing import Any

from chronus.execution.lifecycle import ShutdownSignals, join_until
from chronus.fleet.backends import BACKEND_CHOICES, DEFAULT_PREFERENCE, PREFERENCES
from chronus.fleet.canonical import deterministic_bytes
from chronus.fleet.errors import FleetError
from chronus.fleet.kernels import DEVICE_ROUTES
from chronus.fleet.lattice import DEFAULT_VIRTUAL_UNITS, RESIDENT_RUNGS
from chronus.fleet.transport import DEFAULT_PORT

HOME_ENV = "CHRONUS_FLEET_HOME"
DEFAULT_COORDINATOR = f"http://127.0.0.1:{DEFAULT_PORT}"


def fleet_home() -> Path:
    return Path(os.environ.get(HOME_ENV, "~/.chronus/fleet")).expanduser()


def _size(text: str) -> int:
    units = {"kib": 1 << 10, "mib": 1 << 20, "gib": 1 << 30, "kb": 1000, "mb": 10**6, "gb": 10**9, "b": 1}
    lowered = text.strip().lower()
    for suffix, factor in units.items():
        if lowered.endswith(suffix):
            return int(float(lowered[: -len(suffix)]) * factor)
    return int(lowered)


def _token(args: argparse.Namespace) -> str:
    from chronus.fleet.auth import load_token

    token_file = args.token_file
    if args.token is None and token_file is None and not os.environ.get("CHRONUS_FLEET_TOKEN"):
        default = fleet_home() / "token"
        if default.exists():
            token_file = default
    return load_token(args.token, token_file)


def _print(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(data)


# ---------------------------------------------------------------- commands
def cmd_init(args: argparse.Namespace) -> int:
    from chronus.fleet.auth import generate_self_signed, new_token, write_token_file
    from chronus.fleet.signing import FleetSigner

    home = Path(args.state_dir).expanduser() if args.state_dir else fleet_home()
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    token_path = home / "token"
    if token_path.exists():
        print(f"token already exists: {token_path}")
    else:
        write_token_file(token_path, new_token())
        print(f"fleet token written to {token_path} (mode 600); copy this file to every machine that joins")
    signer = FleetSigner.from_state_dir(home)
    print(f"ML-DSA-65 receipt key id: {signer.key_id}")
    if args.tls_host:
        cert, key = generate_self_signed(home / "tls", args.tls_host)
        print(f"TLS certificate: {cert}\nTLS key: {key} (mode 600)")
        print("copy the certificate (not the key) to every machine and pass it with --tls-ca")
    return 0


def cmd_coordinator(args: argparse.Namespace) -> int:
    from chronus.fleet.coordinator import CoordinatorConfig, FleetCoordinator

    home = Path(args.state_dir).expanduser() if args.state_dir else fleet_home()
    cert, key = args.tls_cert, args.tls_key
    if args.tls and not (cert and key):
        cert, key = str(home / "tls" / "coordinator-cert.pem"), str(home / "tls" / "coordinator-key.pem")
    config = CoordinatorConfig(
        token=_token(args),
        state_dir=home,
        host=args.host,
        port=args.port,
        tls_cert=cert,
        tls_key=key,
        tier=args.tier,
        sample_rate_ppm=args.sample_rate_ppm,
        heartbeat_interval_ms=args.heartbeat_ms,
        node_timeout_ms=args.node_timeout_ms,
        lease_ttl_ms=args.lease_ttl_ms,
        expected_workers=args.expected_workers,
        idle_poll_ms=args.idle_poll_ms,
        max_connections=args.max_connections,
        replay_capacity=args.replay_capacity,
    )
    coordinator = FleetCoordinator(config).start()
    status = coordinator.status()
    print(f"Chronus fleet coordinator {coordinator.fleet_id} on {args.host}:{coordinator.address[1]}")
    tier = coordinator.tier
    print(f"  {tier.label}: provisioned entitlement {tier.warps:,} logical warps, {tier.storage_tb:,} TB "
          f"(provisioning, not a performance claim); {status['tier']['scale']} with a signed grant")
    print(f"  receipts: ML-DSA-65, key id {status['signer']['key_id']}")
    print(f"  ledger: {status['ledger']['path']}")
    print("  waiting for workers; Ctrl-C to stop", flush=True)
    with ShutdownSignals() as notification:
        try:
            while not notification.requested:
                time.sleep(0.1)
        finally:
            coordinator.stop()
    return 0


def cmd_join(args: argparse.Namespace) -> int:
    from chronus.fleet.worker import FleetWorker, WorkerConfig

    config = WorkerConfig(
        coordinator_url=args.coordinator,
        token=_token(args),
        label=args.label or socket.gethostname(),
        owner=args.owner,
        resident_units=args.virtual_units,
        routes=args.route or None,
        backend=args.backend,
        prefer=args.prefer,
        tls_ca=args.tls_ca,
        measure=not args.no_measure,
    )
    worker = FleetWorker(config)
    print("detecting backends (probe and known-answer self-test) ...", flush=True)
    prepared = worker.prepare()
    _print_routes(prepared.to_dict())
    _print_selection(worker.selection.to_dict())
    if not worker.selection.ok:
        print(f"chronus-fleet: backend {args.backend} unavailable; failing closed", file=sys.stderr)
        return 2
    stop = threading.Event()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            worker.run()
        except BaseException as exc:  # reported below
            errors.append(exc)
        finally:
            stop.set()

    thread = threading.Thread(target=run, name="fleet-worker", daemon=True)
    with ShutdownSignals() as notification:
        thread.start()
        joined = False
        while not stop.is_set() and not notification.requested:
            if worker.node_id is not None and not joined:
                print(f"joined as {worker.node_id} (state={worker.state})", flush=True)
                joined = True
            stop.wait(0.1)
        worker.stop(leave=False)
        deadline = time.monotonic_ns() + 10_000_000_000
        survivors = join_until([thread], deadline)
        if worker._heartbeat_thread is not None:
            survivors.extend(join_until([worker._heartbeat_thread], deadline))
        if not survivors:
            leave = threading.Thread(target=worker.stop, kwargs={"leave": True},
                                     name="fleet-leave", daemon=True)
            leave.start()
            survivors.extend(join_until([leave], deadline))
        if survivors:
            print(f"worker STOP_DEGRADED; live threads: {survivors}", file=sys.stderr)
            return 1
    if errors:
        print(f"worker stopped: {errors[0]}", file=sys.stderr)
        return 1
    return 0


def _print_routes(prepared: dict[str, Any]) -> None:
    tests = {t["route"]: t for t in prepared["self_tests"]}
    for capability in prepared["capabilities"]:
        route = capability["route"]
        if not capability["available"]:
            print(f"  {route:<9} absent      {capability['reason']}")
            continue
        test = tests.get(route)
        state = "verified" if test and test["passed"] else "FAILED"
        detail = ", ".join(test["verified_kernels"]) if test and test["passed"] else (test or {}).get("error")
        print(f"  {route:<9} {state:<11} {capability['mode_label']}: {detail}")
    for m in prepared["measurements"]:
        print(
            f"    measured {m['route']}/{m['kernel']}: {m['items_per_second']:,} items/s "
            f"(best of {m['repeats']}, {m['started_at']})"
        )


def _print_selection(selection: dict[str, Any]) -> None:
    detected = ", ".join(selection["detected_backends"]) or "none"
    print(f"  backends detected: {detected}")
    executed = selection["executed_backend"] or "none (failing closed)"
    print(f"  backend: requested {selection['requested_backend']}, prefer {selection['preference']} -> {executed}")
    if selection["fallback_reason"]:
        print(f"    reason: {selection['fallback_reason']}")


def cmd_bench(args: argparse.Namespace) -> int:
    from chronus.fleet.adapters import AdapterRegistry
    from chronus.fleet.kernels import KernelRegistry, default_registry

    kernels = default_registry()
    if args.kernel:
        kernels = KernelRegistry(kernels.get(name) for name in args.kernel)
    registry = AdapterRegistry(args.route or None)
    prepared = registry.prepare(kernels, measure=True, budget_ns=args.budget_ms * 1_000_000).to_dict()
    selection = registry.selection(args.backend, args.prefer).to_dict()
    if args.json:
        prepared["selection"] = selection
        _print(prepared, True)
    else:
        print("Backends on this machine (probe, known-answer self-test, timed runs):")
        _print_routes(prepared)
        _print_selection(selection)
        print("Throughput figures are timed runs on this host only; probes are never measurements.")
    if args.backend != "auto":
        return 0 if selection["executed_backend"] else 1
    failed = [t for t in prepared["self_tests"] if not t["passed"] and t["route"] != "cuda"]
    return 1 if failed or not selection["executed_backend"] else 0


def _client(args: argparse.Namespace):
    from chronus.fleet.auth import FleetAuth
    from chronus.fleet.transport import FleetClient

    return FleetClient(args.coordinator, FleetAuth(_token(args)), "client:cli", args.tls_ca)


def cmd_status(args: argparse.Namespace) -> int:
    status = _client(args).get("/v1/status")
    if args.json:
        _print(status, True)
        return 0
    tier = status["tier"]
    state = "within entitlement" if tier["within_entitlement"] else tier["scale"]
    print(f"fleet {status['fleet_id']}  {tier['current']['label']}  {state}")
    lattice = status["composed_lattice"]
    print(f"  composed lattice: {lattice['logical_lanes']} virtual units = {lattice['logical_warps']} logical warps "
          f"(entitlement {tier['current']['warps']:,}); {lattice['label']}")
    print(f"  receipts: ML-DSA-65 key {status['signer']['key_id'][:16]}...  ledger entries {status['ledger']['entries']}")
    for node in status["nodes"]:
        routes = ", ".join(f"{r} ({info['silicon']})" for r, info in sorted(node["routes"].items()))
        rates = ", ".join(f"{k}={v:,}/s" for k, v in node["measured_items_per_second"].items()) or "unmeasured"
        flag = node["quarantined"] or node["state"]
        backend = node.get("backend") or {}
        chosen = f"backend {backend.get('executed_backend')} (prefer {backend.get('preference')})" if backend else ""
        print(f"  - {node['label']:<20} {node['node_id']:<28} {flag:<11} {routes} {chosen}")
        print(f"      measured: {rates}")
    for job in status["jobs"][-10:]:
        print(f"  job {job['job_id']} {job['kernel']:<16} {job['status']:<10} {job['tiles_done']}/{job['tiles_total']} tiles")
    return 0


def demo_work_unit(kernel: str, size: int, route: str, virtual_units: int):
    from chronus.fleet.kernels import _u32_bytes
    from chronus.fleet.workunit import WorkUnit

    if kernel in ("m15_fold", "m15_unfold"):
        return WorkUnit(kernel, deterministic_bytes("chronus.fleet.demo", size - size % 2 or 2), {}, route, virtual_units)
    if kernel == "dual_space_query":
        return WorkUnit(kernel, deterministic_bytes("chronus.fleet.demo", size - size % 4 or 4), {}, route, virtual_units)
    if kernel == "gf_matvec":
        p = 65521
        n = max(1, math.isqrt(size // 4))
        raw = deterministic_bytes("chronus.fleet.demo.gf", 4 * (n * n + n))
        words = [int.from_bytes(raw[i : i + 4], "little") % p for i in range(0, len(raw), 4)]
        return WorkUnit(kernel, _u32_bytes(words), {"p": p, "rows": n, "cols": n}, route, virtual_units)
    if kernel == "pv_lattice_fold":
        count = max(1, size // 32)
        raw = deterministic_bytes("chronus.fleet.demo.pv", 2 * count)
        values = [{"a": str(raw[2 * i] - 128), "b": str(raw[2 * i + 1] - 128), "denominator": "1"} for i in range(count)]
        return WorkUnit(kernel, json.dumps(values).encode(), {"order": 30}, route, virtual_units)
    raise FleetError(f"no demo input for kernel {kernel}; use the Python API")


def cmd_run(args: argparse.Namespace) -> int:
    from chronus.fleet.executor import FleetExecutor
    from chronus.fleet.receipts import summarise

    route = args.backend if args.backend != "auto" else args.route
    unit = demo_work_unit(args.kernel, _size(args.size), route, args.virtual_units)
    if args.prefer:
        from dataclasses import replace

        unit = replace(unit, prefer=args.prefer)
    with FleetExecutor(args.coordinator, token=_token(args), tls_ca=args.tls_ca, name="cli-run") as fleet:
        result = fleet.submit(unit, timeout=args.timeout)
    out = Path(args.receipt_out or f"receipt-{result.job_id}.json")
    out.write_text(json.dumps(result.receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print(summarise(result.receipt), True)
    print(f"receipt signature and result digest verified (ML-DSA-65) and saved to {out}")
    return 0


def _print_tier(tier: dict[str, Any]) -> None:
    current = tier["current"]
    entitlement = tier["entitlement"]
    demand = tier["demand"]
    print(f"tier: {current['label']}" + (f" (contract {current['contract']})" if current.get("contract") else "")
          + f"  [{tier['selected_by']}]")
    print(f"  entitlement: {entitlement['logical_warps']:,} logical warps x 32 lanes = "
          f"{entitlement['logical_lanes']:,} lanes; {entitlement['storage_tb']:,} TB ({entitlement['kind']})")
    print(f"  demand: {demand['logical_warps']:,} logical warps ({demand['admitted_logical_warps']:,} admitted, "
          f"{demand['waiting_machines']} machine(s) waiting, {demand['queued_jobs']} job(s) queued); "
          f"storage {demand['storage_bytes']:,} bytes")
    if tier["within_entitlement"]:
        print(f"  within entitlement; {tier['scale']} (authorise with: chronus-fleet tier grant)")
    else:
        authorised = f" authorised by {tier['scale_authorised']}" if tier["scale_authorised"] else ""
        print(f"  over entitlement: {tier['scale']}{authorised}")
    for grant in tier["grants"]:
        state = "valid" if grant["valid"] else "expired"
        print(f"  grant {grant['grant_id']}: {grant['tier']} ({grant['warps']:,} warps, {grant['storage_tb']:,} TB) "
              f"until {grant['expires_at']} [{state}]")
    for event in tier["scale_events"][-5:]:
        print(f"  scale event {event['recorded_at']}: {event['kind']} {event['subject']} -> {event['outcome']}: "
              f"{event['message']}")


def _tier_home(args: argparse.Namespace) -> Path:
    return Path(args.state_dir).expanduser() if args.state_dir else fleet_home()


def _owner_signer(home: Path):
    from chronus.fleet.signing import FleetSigner

    identity = home / "fleet.json"
    if not identity.exists():
        raise FleetError(f"{identity} not found: run this on the coordinator (start it once first)")
    fleet_id = json.loads(identity.read_text(encoding="utf-8"))["fleet_id"]
    return FleetSigner.from_state_dir(home), fleet_id


def cmd_tier(args: argparse.Namespace) -> int:
    from chronus.fleet.scale import issue_grant, issue_selection, parse_duration, write_document

    if args.tier_command == "status":
        status = _client(args).get("/v1/status")
        if args.json:
            _print(status["tier"], True)
        else:
            _print_tier(status["tier"])
        return 0
    home = _tier_home(args)
    signer, fleet_id = _owner_signer(home)
    if args.tier_command == "grant":
        document = issue_grant(
            signer, fleet_id, args.tier, parse_duration(args.expires),
            warps=args.warps, storage_tb=args.storage_tb, contract=args.contract,
        )
        path = write_document(home, document)
        print(f"scale grant {document['grant_id']}: {document['tier_label']} ({document['warps']:,} logical warps, "
              f"{document['storage_tb']:,} TB) until {document['expires_at']}")
    else:
        document = issue_selection(signer, fleet_id, args.tier)
        path = write_document(home, document)
        print(f"tier selection {document['selection_id']}: tier {args.tier}")
    print(f"signed with ML-DSA-65 key {signer.key_id[:16]}... and saved to {path}")
    print("the coordinator applies it on its next fabric tick (about 2 s); check with: chronus-fleet tier status")
    return 0


def cmd_verify_receipt(args: argparse.Namespace) -> int:
    from chronus.fleet.receipts import verify_receipt

    receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    output = Path(args.output).read_bytes() if args.output else None
    check = verify_receipt(receipt, public_key=args.public_key, output=output, ledger_path=args.ledger)
    _print(check.to_dict(), True)
    return 0 if check.valid else 1


# ------------------------------------------------------------------- parser
def _auth_options(parser: argparse.ArgumentParser, coordinator_required: bool) -> None:
    parser.add_argument("--coordinator", required=coordinator_required, default=None if coordinator_required else DEFAULT_COORDINATOR,
                        help="coordinator URL, for example https://imac.local:8740")
    parser.add_argument("--token", help="fleet token (visible to other local users in ps; prefer --token-file)")
    parser.add_argument("--token-file", help="file holding the fleet token (default ~/.chronus/fleet/token if present)")
    parser.add_argument("--tls-ca", help="certificate that signs the coordinator's TLS certificate")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chronus-fleet", description="Chronus iGPU fleet: many machines, one iGPU.")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create the fleet token, receipt signing key and optional TLS certificate")
    p.add_argument("--state-dir")
    p.add_argument("--tls-host", action="append", help="hostname or IP for the TLS certificate (repeatable)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("coordinator", help="run the coordinator")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--host", default="127.0.0.1", help="bind address; use 0.0.0.0 to accept other machines")
    p.add_argument("--state-dir")
    p.add_argument("--token")
    p.add_argument("--token-file")
    p.add_argument("--tls", action="store_true", help="use the certificate created by init --tls-host")
    p.add_argument("--tls-cert")
    p.add_argument("--tls-key")
    p.add_argument("--tier", type=int, default=1, choices=(1, 2, 3, 4, 5),
                   help="starting tier (2 and above need a valid grant: chronus-fleet tier grant; 5 is Scale)")
    p.add_argument("--sample-rate-ppm", type=int, default=125_000)
    p.add_argument("--heartbeat-ms", type=int, default=1000)
    p.add_argument("--node-timeout-ms", type=int, default=5000)
    p.add_argument("--lease-ttl-ms", type=int, default=15_000)
    p.add_argument("--expected-workers", type=int, default=1, help="planning input, not a physical capacity claim")
    p.add_argument("--idle-poll-ms", type=int, default=150)
    p.add_argument("--max-connections", type=int, default=64)
    p.add_argument("--replay-capacity", type=int, help="override replay budget above the calculated minimum")
    p.set_defaults(func=cmd_coordinator)

    p = sub.add_parser("join", help="lend this machine's verified backends to a fleet")
    _auth_options(p, coordinator_required=True)
    _backend_options(p)
    p.add_argument("--route", action="append", choices=DEVICE_ROUTES,
                   help="advanced: enable only these routes before detection (repeatable)")
    p.add_argument("--virtual-units", type=int, choices=RESIDENT_RUNGS, default=DEFAULT_VIRTUAL_UNITS)
    p.add_argument("--label", help="name shown in status (default: hostname)")
    p.add_argument("--owner", default="hyba", help="participant that owns this machine")
    p.add_argument("--no-measure", action="store_true", help="skip timed runs at start (weights stay unmeasured)")
    p.set_defaults(func=cmd_join)

    p = sub.add_parser("status", help="show nodes, backends, measured throughput, jobs and the tier")
    _auth_options(p, coordinator_required=False)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("bench", help="detect, self-test and time this machine's backends")
    _backend_options(p)
    p.add_argument("--route", action="append", choices=DEVICE_ROUTES)
    p.add_argument("--kernel", action="append")
    p.add_argument("--budget-ms", type=int, default=300)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("run", help="submit a demonstration work unit and verify its receipt")
    _auth_options(p, coordinator_required=False)
    p.add_argument("--kernel", default="m15_fold")
    p.add_argument("--size", default="16MiB")
    p.add_argument("--route", default="auto", choices=("auto",) + DEVICE_ROUTES)
    p.add_argument("--backend", choices=BACKEND_CHOICES, default="auto",
                   help="run on exactly this backend (fails closed if no machine offers it)")
    p.add_argument("--prefer", choices=PREFERENCES, help="steer auto on every worker (default: each worker's own)")
    p.add_argument("--virtual-units", type=int, choices=RESIDENT_RUNGS, default=DEFAULT_VIRTUAL_UNITS)
    p.add_argument("--timeout", type=float, default=600.0)
    p.add_argument("--receipt-out")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("verify-receipt", help="verify a saved receipt")
    p.add_argument("receipt")
    p.add_argument("--public-key", help="pinned coordinator public key (hex)")
    p.add_argument("--ledger", help="coordinator ledger.jsonl to check the anchor against")
    p.add_argument("--output", help="result bytes to check against the signed digest")
    p.set_defaults(func=cmd_verify_receipt)

    p = sub.add_parser("tier", help="tiers with the option to scale: status, grant, set")
    tier_sub = p.add_subparsers(dest="tier_command", required=True)
    q = tier_sub.add_parser("status", help="current tier, entitlement, demand and whether scale is available")
    _auth_options(q, coordinator_required=False)
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_tier)
    q = tier_sub.add_parser("grant", help="owner, on the coordinator: sign a scale grant (ML-DSA-65)")
    q.add_argument("--tier", required=True, help="2, 3, 4 or scale")
    q.add_argument("--expires", required=True, help="how long the grant lasts, for example 30d, 12h or 2w")
    q.add_argument("--warps", type=int, help="Scale only: contracted logical warps")
    q.add_argument("--storage-tb", type=int, help="Scale only: contracted storage in TB")
    q.add_argument("--contract", help="Scale only: the contract reference that sets the figure")
    q.add_argument("--state-dir", help="coordinator state directory (default ~/.chronus/fleet)")
    q.set_defaults(func=cmd_tier)
    q = tier_sub.add_parser("set", help="owner, on the coordinator: move to a tier (down any time, up under a grant)")
    q.add_argument("--tier", required=True, help="1, 2, 3, 4 or scale")
    q.add_argument("--state-dir", help="coordinator state directory (default ~/.chronus/fleet)")
    q.set_defaults(func=cmd_tier)
    return parser


def _backend_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend", choices=BACKEND_CHOICES, default="auto",
                        help="auto (detect and choose by --prefer) or exactly one backend, failing closed if absent")
    parser.add_argument("--prefer", choices=PREFERENCES, default=DEFAULT_PREFERENCE,
                        help="ours: the Chronus iGPU even when the host has a GPU (default); "
                             "host: the host GPU when present and self-tested")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING - 10 * min(args.verbose, 2),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except FleetError as exc:
        print(f"chronus-fleet: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
