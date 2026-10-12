#!/usr/bin/env python3
"""Sovereign boundary proof pack: executed evidence, not a description.

Run inside a sovereign deployment (``HYBA_SOVEREIGN_MODE=air_gapped`` with
an audit path and attestation key, e.g. the Docker image on an
``internal: true`` network). The pack:

1. probes the *network layer* from a child interpreter that has no
   in-process hook (``python -I``): can this host reach the internet or
   resolve public names at all?  Reported separately -- the hook is not
   evidence of network isolation;
2. installs the AL HARAS sovereign control plane in this process;
3. attempts real egress (TCP, UDP, DNS, HTTPS ingestion, asyncio), cloud
   storage (s3://, az://, gs://) and external ingestion, which must all be
   refused and recorded; a loopback connection and a local storage path,
   which must be admitted;
4. proves the boundary propagates to supervised workers
   (``python -m al_haras.sovereign_exec``) into the same audit chain;
5. issues an HMAC-signed attestation anchored to the audit head, verifies
   it, and runs tamper tests (edit, delete, truncate) on a copy of the
   exported chain, each of which must be detected.

Everything lands in ``--out``: attestation.json, audit.jsonl,
denied_events.json, verification.json, tamper_tests.json,
network_probe.json, results.json and summary.md. Exit 0 only when every
expectation holds (and, with ``--require-network-isolation``, the network
probe found no route out).

    python scripts/sovereign_proof_pack.py --out sovereign-proof
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from al_haras.sovereign_control import (  # noqa: E402
    ENV_AUDIT,
    ENV_MODE,
    SovereignBoundaryDenied,
    SovereignEgressDenied,
    admit_location,
    install_from_env,
    read_audit,
    verify_attestation,
)

PUBLIC_TCP = ("1.1.1.1", 443)
PUBLIC_UDP = ("8.8.8.8", 53)
PUBLIC_NAME = "pypi.org"

NETWORK_PROBE = textwrap.dedent(
    """
    import json, socket
    out = {}
    for name, (host, port) in {"tcp_1.1.1.1:443": ("1.1.1.1", 443),
                               "tcp_8.8.8.8:53": ("8.8.8.8", 53)}.items():
        try:
            socket.create_connection((host, port), timeout=4).close()
            out[name] = "reachable"
        except OSError as exc:
            out[name] = f"unreachable: {type(exc).__name__}: {exc}"
    try:
        socket.getaddrinfo("pypi.org", 443)
        out["dns_pypi.org"] = "resolved"
    except OSError as exc:
        out["dns_pypi.org"] = f"unresolved: {type(exc).__name__}: {exc}"
    print(json.dumps(out))
    """
)

WORKER_PROBE = textwrap.dedent(
    """
    import socket, sys
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=4).close()
        print("WORKER_EGRESS_REACHED")
        sys.exit(3)
    except PermissionError as exc:
        print("WORKER_EGRESS_DENIED", type(exc).__name__)
    """
)


def network_probe() -> dict[str, Any]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYBA_SOVEREIGN")}
    proc = subprocess.run(
        [sys.executable, "-I", "-c", NETWORK_PROBE],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    try:
        results = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        results = {"error": proc.stderr[-500:]}
    isolated = bool(results) and all(
        str(v).startswith(("unreachable", "unresolved")) for v in results.values()
    )
    return {
        "method": "child interpreter (python -I) without the in-process hook",
        "results": results,
        "network_isolated": isolated,
    }


class Pack:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def expect(self, name: str, expected: str, action: Callable[[], Any]) -> None:
        started = time.perf_counter()
        try:
            detail = action()
            observed = "allowed"
        except (SovereignEgressDenied, SovereignBoundaryDenied) as exc:
            detail, observed = f"{type(exc).__name__}: {exc}", "denied"
        except OSError as exc:
            # Libraries wrap the boundary's PermissionError (urllib: URLError
            # .reason); anything else is not our boundary and is recorded as is.
            cause = _sovereign_cause(exc)
            if cause is not None:
                detail, observed = f"{type(exc).__name__} <- {type(cause).__name__}: {cause}", "denied"
            else:
                detail, observed = f"{type(exc).__name__}: {exc}", "os-error"
        except Exception as exc:  # noqa: BLE001 - a failed product check is evidence too
            detail, observed = f"{type(exc).__name__}: {exc}", "error"
        self.checks.append(
            {
                "check": name,
                "expected": expected,
                "observed": observed,
                "passed": observed == expected,
                "detail": str(detail)[:300],
                "ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )


def _sovereign_cause(exc: BaseException) -> BaseException | None:
    seen: set[int] = set()
    stack: list[Any] = [exc]
    while stack:
        item = stack.pop()
        if not isinstance(item, BaseException) or id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, (SovereignEgressDenied, SovereignBoundaryDenied)):
            return item
        stack += [getattr(item, "reason", None), item.__cause__, item.__context__]
    return None


def _loopback_round_trip() -> str:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        conn, _ = server.accept()
        conn.sendall(b"ok")
        conn.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    with socket.create_connection(("127.0.0.1", port), timeout=4) as client:
        data = client.recv(2)
    thread.join(timeout=4)
    server.close()
    return f"127.0.0.1:{port} -> {data!r}"


async def _asyncio_egress() -> str:
    reader, writer = await asyncio.wait_for(asyncio.open_connection(*PUBLIC_TCP), 5)
    writer.close()
    return "connected"


def _theseus_round_trip(work: Path, key: bytes) -> str:
    from aethel.enterprise.custody import EnterpriseCustody

    admit_location(str(work / "theseus"), kind="storage")
    custody = EnterpriseCustody(work / "theseus", tenant="sovereign-tenant", hmac_key=key)
    envelope = custody.put(b"sovereign record", record_id="sovereign-proof-1")
    custody.close()
    reopened = EnterpriseCustody(work / "theseus", tenant="sovereign-tenant", hmac_key=key)
    try:
        payload = reopened.get("sovereign-proof-1")
    finally:
        reopened.close()
    if payload != b"sovereign record":
        raise RuntimeError("THESEUS returned a different payload after restart")
    return f"generation {envelope.generation}, digest {envelope.content_digest[:16]}"


def _ovid_round_trip(work: Path, key: bytes) -> str:
    from hyba_db import EdgeKind, NodeKind, OntologyStore, Quota
    from hyba_db.theseus_custody import TheseusFileCustody

    admit_location(str(work / "ovid"), kind="storage")
    (work / "ovid").mkdir(parents=True, exist_ok=True)
    custody = TheseusFileCustody(work / "ovid" / "custody", hmac_key=key)
    with OntologyStore(work / "ovid" / "ontology.db", key, custody=custody) as store:
        tenant = store.provision_client("sovereign", Quota(100, 100_000))
        a = store.add_node(tenant.tenant_id, NodeKind.GPU, {"name": "enclave-device"})
        store.add_node(tenant.tenant_id, NodeKind.KERNEL, {"name": "fold"},
                       connect_from=a.id, edge_kind=EdgeKind.DISPATCHES)
        reached = store.traverse(tenant.tenant_id, a.id)
        report = store.verify_database(tenant.tenant_id)
        passed = report["passed"] if isinstance(report, dict) else report.passed
    if not passed:
        raise RuntimeError("OVID verify_database failed inside the boundary")
    return f"{len(reached)} nodes traversed, verify_database passed"


def _chronus_workload(work: Path, key: bytes) -> str:
    from chronus.virtual_igpu.abi import ExecutionPolicy, Workload, WorkloadKind
    from chronus.virtual_igpu.runtime import RuntimeDaemon
    from hyba_db.theseus_custody import TheseusFileCustody

    custody = TheseusFileCustody(work / "chronus-custody", hmac_key=key)
    daemon = RuntimeDaemon(store_dir=work / "chronus-vigpu", custody=custody)
    result = daemon.submit(
        Workload(
            id="sovereign.proof/1",
            kind=WorkloadKind.LUCAS_TRANSFORM,
            tenant="sovereign",
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={"n": 10},
            constraints={"custody": "required"},
        )
    )
    state = result.metrics.get("custody", {})
    if result.status != "ok" or state.get("state") != "committed":
        raise RuntimeError(f"CHRONUS workload not committed: {result.status} {state}")
    if not custody.verify("sovereign", state["record_id"]):
        raise RuntimeError("CHRONUS custody record does not verify")
    return f"status ok, custody {state['state']} ({state['record_id'][:40]})"


def tamper_tests(records: list[dict[str, Any]], attestation: dict[str, Any], key: bytes) -> list[dict]:
    out = []
    denied_index = next(
        (i for i, r in enumerate(records) if r.get("event", {}).get("event") == "denied"), 0
    )

    edited = copy.deepcopy(records)
    edited[denied_index]["event"]["target"] = "10.0.0.1:443"
    deleted = copy.deepcopy(records)
    del deleted[denied_index]
    anchor = int(attestation["audit"]["records"])
    truncated = copy.deepcopy(records[: max(anchor - 1, 0)])
    rehashed = copy.deepcopy(records)
    # A forger who rewrites the event *and* recomputes every hash from that
    # point makes a self-consistent chain; the signed anchor catches it.
    from al_haras.audit import digest

    rehashed[denied_index]["event"]["target"] = "10.0.0.1:443"
    previous = rehashed[denied_index - 1]["record_hash"] if denied_index else "GENESIS"
    for record in rehashed[denied_index:]:
        record["previous_hash"] = previous
        record["record_hash"] = digest({"event": record["event"], "previous_hash": previous})
        previous = record["record_hash"]

    for name, chain in (
        ("edit a denied event's target", edited),
        ("delete a denied event", deleted),
        ("truncate before the attested head", truncated),
        ("rewrite and re-hash the chain (no key)", rehashed),
    ):
        verdict = verify_attestation(attestation, key, chain)
        out.append(
            {
                "tamper": name,
                "detected": not verdict["valid"],
                "chain_valid": verdict.get("chain_valid"),
                "audit_anchor_matches": verdict.get("audit_anchor_matches"),
                "first_broken_record": verdict.get("first_broken_record"),
            }
        )
    forged = copy.deepcopy(attestation)
    forged["denials"] = {}
    verdict = verify_attestation(forged, key, records)
    out.append(
        {
            "tamper": "edit the attestation's denial counts",
            "detected": not verdict["valid"],
            "signature_valid": verdict["signature_valid"],
        }
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path("sovereign-proof"))
    parser.add_argument("--skip-network-probe", action="store_true")
    parser.add_argument("--require-network-isolation", action="store_true")
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    if (os.environ.get(ENV_MODE) or "connected") == "connected":
        print(f"{ENV_MODE} must be private or air_gapped for a proof pack", file=sys.stderr)
        return 2

    probe = {"skipped": True} if args.skip_network_probe else network_probe()
    (out / "network_probe.json").write_text(json.dumps(probe, indent=2) + "\n", encoding="utf-8")

    plane = install_from_env(role="proof-pack")
    assert plane is not None
    pack = Pack()
    pack.expect("loopback TCP round trip", "allowed", _loopback_round_trip)
    pack.expect(
        f"TCP egress {PUBLIC_TCP[0]}:{PUBLIC_TCP[1]}",
        "denied",
        lambda: socket.create_connection(PUBLIC_TCP, timeout=4).close(),
    )
    pack.expect(
        f"UDP egress {PUBLIC_UDP[0]}:{PUBLIC_UDP[1]}",
        "denied",
        lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"\x00", PUBLIC_UDP),
    )
    pack.expect(f"DNS resolution of {PUBLIC_NAME}", "denied", lambda: socket.getaddrinfo(PUBLIC_NAME, 443))
    pack.expect(
        "HTTPS ingestion via urllib (https://pypi.org/simple/)",
        "denied",
        lambda: urllib.request.urlopen("https://pypi.org/simple/", timeout=4).status,
    )
    pack.expect("asyncio TCP egress", "denied", lambda: asyncio.run(_asyncio_egress()))
    for uri in ("s3://hyba-exfil/records.tar", "az://exfil/container/blob", "gs://exfil/object"):
        pack.expect(f"cloud storage {uri}", "denied", lambda uri=uri: admit_location(uri, kind="storage"))
    pack.expect(
        "external ingestion https://data.example.com/feed.csv",
        "denied",
        lambda: admit_location("https://data.example.com/feed.csv", kind="ingestion"),
    )
    local = Path(os.environ.get("HYBA_SOVEREIGN_PROOF_LOCAL") or tempfile.gettempdir()) / "sovereign-data"
    local.mkdir(parents=True, exist_ok=True)
    pack.expect("local storage path", "allowed", lambda: admit_location(str(local), kind="storage"))

    # The sovereign products themselves, working inside the boundary on
    # local storage only (no mining, pool or wallet path is imported).
    work = Path(tempfile.mkdtemp(prefix="sovereign-products-", dir=str(local.parent)))
    product_key = plane.policy.attestation_key[:32]
    pack.expect("THESEUS custody put/restart/get under the boundary", "allowed",
                lambda: _theseus_round_trip(work, product_key))
    pack.expect("OVID ontology write + verify_database under the boundary", "allowed",
                lambda: _ovid_round_trip(work, product_key))
    pack.expect("CHRONUS workload committed to THESEUS custody", "allowed",
                lambda: _chronus_workload(work, product_key))

    worker = out / "worker_probe.py"
    worker.write_text(WORKER_PROBE, encoding="utf-8")

    def _worker() -> str:
        proc = subprocess.run(
            [sys.executable, "-m", "al_haras.sovereign_exec", str(worker)],
            capture_output=True, text=True, timeout=60, cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")]))},
        )
        if "WORKER_EGRESS_DENIED" in proc.stdout:
            raise SovereignEgressDenied(f"worker: {proc.stdout.strip()}")
        return f"rc={proc.returncode} stdout={proc.stdout.strip()} stderr={proc.stderr.strip()[-200:]}"

    pack.expect("supervised worker egress (al_haras.sovereign_exec)", "denied", _worker)

    attestation = plane.attestation()
    key = plane.policy.attestation_key
    records = read_audit(Path(os.environ[ENV_AUDIT]))
    worker_denials = [
        r for r in records
        if r["event"].get("event") == "denied" and str(r["event"].get("role", "")).startswith("worker:")
    ]
    verification = verify_attestation(attestation, key, records)
    tampers = tamper_tests(records, attestation, key)
    denied = [r["event"] for r in records if r["event"].get("event") == "denied"]

    (out / "attestation.json").write_text(json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with open(out / "audit.jsonl", "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    (out / "denied_events.json").write_text(json.dumps(denied, indent=2) + "\n", encoding="utf-8")
    (out / "verification.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    (out / "tamper_tests.json").write_text(json.dumps(tampers, indent=2) + "\n", encoding="utf-8")

    expectations = {
        "boundary_checks": all(c["passed"] for c in pack.checks),
        "worker_denial_in_shared_chain": bool(worker_denials),
        "attestation_verifies": verification["valid"],
        "every_tamper_detected": all(t["detected"] for t in tampers),
    }
    if args.require_network_isolation:
        expectations["network_isolated"] = bool(probe.get("network_isolated"))
    passed = all(expectations.values())
    results = {
        "schema": "hyba.sovereign-proof-pack/1",
        "passed": passed,
        "expectations": expectations,
        "checks": pack.checks,
        "network_probe": probe,
        "attestation": {
            "mode": attestation["policy"]["mode"],
            **{k: attestation[k] for k in ("policy_digest", "key_id", "audit", "denials", "build")},
        },
    }
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    (out / "summary.md").write_text(_summary(results, tampers), encoding="utf-8")
    print(json.dumps({"passed": passed, "expectations": expectations}, indent=2))
    return 0 if passed else 1


def _summary(results: dict[str, Any], tampers: list[dict]) -> str:
    mark = {True: "PASS", False: "FAIL"}
    probe = results["network_probe"]
    if probe.get("skipped"):
        network = "not probed (--skip-network-probe)"
    else:
        network = (
            "no route out: the host network is isolated"
            if probe["network_isolated"]
            else "REACHABLE: this host is not network-isolated; only the in-process boundary held"
        )
    lines = [
        "## Sovereign boundary proof pack",
        "",
        f"Overall: **{mark[results['passed']]}**  ",
        f"Mode: `{results['attestation']['mode']}` · policy digest "
        f"`{results['attestation']['policy_digest'][:16]}` · key id `{results['attestation']['key_id']}`  ",
        f"Network layer (probed without the hook): {network}",
        "",
        "| Check | Expected | Observed | Result |",
        "|---|---|---|---|",
    ]
    for check in results["checks"]:
        lines.append(
            f"| {check['check']} | {check['expected']} | {check['observed']} | {mark[check['passed']]} |"
        )
    lines += ["", "| Tamper attempt on the exported chain | Detected |", "|---|---|"]
    for tamper in tampers:
        lines.append(f"| {tamper['tamper']} | {mark[tamper['detected']]} |")
    audit = results["attestation"]["audit"]
    lines += [
        "",
        f"Audit chain: {audit['records']} records at attestation, head `{audit['head_hash'][:16]}`, "
        f"valid={audit['chain_valid']}. Build commit `{results['attestation']['build']['commit'][:12]}`.",
        "",
        "Truth boundary: the in-process hook is defence in depth; network isolation is only what "
        "the probe above observed. No accreditation is claimed.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
