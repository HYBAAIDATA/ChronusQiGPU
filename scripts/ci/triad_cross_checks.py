#!/usr/bin/env python3
"""Execute the Chronus-OVID-THESEUS cross-triad checks and emit JSON evidence.

Every check runs the maintained production code (no mocks). Each result is one
of PASS (behaviour observed as required), FAIL (behaviour observed and it
violates the requirement) or GAP (the required capability is not present in the
maintained tree, so nothing can be observed). The script never upgrades a GAP
or FAIL; it exits 0 only to allow evidence capture, and reports the counts.

Usage: python scripts/ci/triad_cross_checks.py [--out path.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from chronus.storage.durable import DurableTheseusService  # noqa: E402
from chronus.triad import ProductionTriad, TriadReceipt  # noqa: E402

RESULTS: list[dict] = []


def record(check_id: str, requirement: str, status: str, detail: str, **extra) -> None:
    RESULTS.append({"id": check_id, "requirement": requirement, "status": status,
                    "detail": detail, **extra})


def _raises(fn) -> str | None:
    try:
        fn()
    except Exception as exc:  # the type is reported, never swallowed silently
        return f"{type(exc).__name__}: {exc}"
    return None


def check_fresh_process_replay(tmp: Path) -> None:
    db = tmp / "replay.sqlite3"
    payload = os.urandom(4096)
    triad = ProductionTriad(str(db))
    receipt = triad.put("tenant-a", payload)
    del triad
    code = (
        "import json,sys,hashlib;sys.path.insert(0,sys.argv[3]);"
        "from chronus.triad import ProductionTriad,TriadReceipt;"
        "t=ProductionTriad(sys.argv[1]);r=TriadReceipt(**json.loads(sys.argv[2]));"
        "p=t.materialise(r);print(json.dumps({'sha':hashlib.sha256(p).hexdigest(),"
        "'verify':t.verify(r),'integrity':t.theseus.evidence()['integrity'],'pid':__import__('os').getpid()}))"
    )
    proc = subprocess.run([sys.executable, "-c", code, str(db), json.dumps(receipt.to_dict()), str(ROOT / "src")],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        record("X1", "Fresh-process replay of a triad commit", "FAIL", proc.stderr.strip()[-400:])
        return
    out = json.loads(proc.stdout)
    ok = out["sha"] == hashlib.sha256(payload).hexdigest() and out["verify"] and out["integrity"] == "PASS"
    record("X1", "Fresh-process replay of a triad commit", "PASS" if ok else "FAIL",
           f"child pid {out['pid']} (parent {os.getpid()}) materialised sha256 match={out['sha'] == hashlib.sha256(payload).hexdigest()}, "
           f"verify={out['verify']}, integrity={out['integrity']}")


def check_orphans(tmp: Path) -> None:
    # (a) SQLite record/journal rows whose content object is missing.
    db = tmp / "orphan_a.sqlite3"
    store = DurableTheseusService(str(db))
    rec = store.store("tenant-a", b"orphan-me")
    store.append_journal_event("tenant-a", "STATE_COMMITTED", b"orphan-me")
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys=OFF")
    con.execute("DELETE FROM objects WHERE object_id=?", (rec.object_id,))
    con.commit(); con.close()
    err = _raises(lambda: DurableTheseusService(str(db)).verify_store())
    record("X2a", "Orphan reconciliation: SQLite rows -> missing THESEUS object", "PASS" if err else "FAIL",
           f"verify_store on reopen raised {err}" if err else "dangling record/journal rows were accepted")

    # (b) THESEUS content objects not referenced by any tenant record or journal row.
    db = tmp / "orphan_b.sqlite3"
    store = DurableTheseusService(str(db))
    store.store("tenant-a", b"referenced")
    stray = b"unreferenced-object"
    con = sqlite3.connect(db)
    con.execute("INSERT INTO objects(object_id,payload,size_bytes) VALUES(?,?,?)",
                (hashlib.sha256(stray).hexdigest(), stray, len(stray)))
    con.commit(); con.close()
    reopened = DurableTheseusService(str(db))
    err = _raises(reopened.verify_store)
    exposes = any("orphan" in k or "unreferenced" in k for k in json.dumps(reopened.stats()).split('"'))
    if err:
        record("X2b", "Orphan reconciliation: THESEUS object -> no SQLite record", "PASS", f"detected: {err}")
    else:
        record("X2b", "Orphan reconciliation: THESEUS object -> no SQLite record", "GAP",
               "an unreferenced content object passes verify_store and is not reported by stats()/evidence(); "
               f"no reconciliation or garbage-collection report exists (stats exposes orphan count: {exposes})")

    # (c) Protected shard files vs THESEUS manifests (both directions).
    db = tmp / "orphan_c.sqlite3"; shards = tmp / "shards"
    triad = ProductionTriad(str(db))
    original = os.urandom(8192)
    receipt = triad.protect_payload("tenant-a", original, shards, shard_count=4)
    files = sorted(p for p in shards.rglob("*") if p.is_file())
    (shards / "stray.shard").write_bytes(b"no-manifest")
    recovered = triad.recover_protected_payload(receipt, shards)
    # Reverse direction: is a shard file without a manifest enumerated anywhere?
    # The maintained API surface is ProtectedTheseusService; record what it exposes.
    from chronus.storage.protected import ProtectedTheseusService
    surface = sorted(n for n in dir(ProtectedTheseusService) if not n.startswith("_"))
    enumerates = any(k in n for n in surface for k in ("orphan", "scan", "reconcile", "list", "audit"))
    record("X2c", "Orphan reconciliation: shard files without a THESEUS manifest", "PASS" if enumerates else "GAP",
           f"{len(files)} shard files + 1 stray; recovery returned the original bytes: {recovered == original}; "
           f"ProtectedTheseusService public API {surface} has no enumeration/reconciliation entry point"
           if not enumerates else f"enumeration entry point present: {surface}")
    # Forward direction: manifest whose shard files are missing must fail closed (two losses).
    for victim in files[:2]:
        victim.unlink()
    try:
        again = triad.recover_protected_payload(receipt, shards)
    except Exception as exc:
        record("X2d", "Protected manifest with two missing shard files fails closed", "PASS",
               f"recovery raised {type(exc).__name__}: {exc}")
    else:
        record("X2d", "Protected manifest with two missing shard files fails closed", "FAIL",
               f"recovery returned {len(again)} bytes (matches original: {again == original})")


def check_tenant_isolation_and_concurrency(tmp: Path) -> None:
    db = tmp / "tenants.sqlite3"
    triad = ProductionTriad(str(db))
    ra = triad.put("tenant-a", b"secret-a")
    foreign = TriadReceipt(**{**ra.to_dict(), "tenant_id": "tenant-b"})
    err = _raises(lambda: triad.materialise(foreign))
    record("X3", "Tenant isolation: tenant B cannot materialise tenant A's receipt", "PASS" if err else "FAIL",
           f"cross-tenant materialise raised {err}" if err else "cross-tenant read succeeded")

    errors: list[str] = []
    receipts: list[TriadReceipt] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        try:
            local = ProductionTriad(str(db))
            for j in range(10):
                r = local.put(f"tenant-{i % 4}", f"payload-{i}-{j}".encode())
                with lock:
                    receipts.append(r)
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    start = time.perf_counter()
    [t.start() for t in threads]; [t.join() for t in threads]
    elapsed = time.perf_counter() - start
    child = (
        "import sys;sys.path.insert(0,sys.argv[2]);from chronus.triad import ProductionTriad;"
        "t=ProductionTriad(sys.argv[1]);[t.put('tenant-proc',b'p%d'%i) for i in range(20)]"
    )
    procs = [subprocess.Popen([sys.executable, "-c", child, str(db), str(ROOT / "src")],
                              stderr=subprocess.PIPE, text=True) for _ in range(3)]
    for p in procs:
        _, stderr = p.communicate(timeout=300)
        if p.returncode:
            errors.append(stderr.strip()[-300:])
    final = ProductionTriad(str(db))
    bad = [r for r in receipts if not final.verify(r)]
    integ = _raises(final.theseus.verify_store)
    continuity = all(final.theseus.verify_journal_continuity(t) for t in
                     [f"tenant-{k}" for k in range(4)] + ["tenant-proc"])
    ok = not errors and not bad and integ is None and continuity and len(receipts) == 80
    record("X4", "Concurrency: 8 threads x 10 puts + 3 processes x 20 puts on one store", "PASS" if ok else "FAIL",
           f"thread puts={len(receipts)} in {elapsed:.2f}s, errors={errors[:2]}, unverifiable={len(bad)}, "
           f"verify_store={'PASS' if integ is None else integ}, journal continuity={continuity}")


def check_fail_closed(tmp: Path) -> None:
    db = tmp / "failclosed.sqlite3"
    triad = ProductionTriad(str(db))
    r = triad.put("tenant-a", os.urandom(2048))
    con = sqlite3.connect(db)
    con.execute("UPDATE objects SET payload=? WHERE object_id=?", (os.urandom(2048 + 64), r.representation_object_id))
    con.commit(); con.close()
    # Read path on the instance that was open before the corruption (no constructor re-verification).
    err_read = _raises(lambda: triad.materialise(r))
    # Open path on a fresh instance.
    err_open = _raises(lambda: ProductionTriad(str(db)))
    record("X5a", "Fail-closed on unrecoverable content corruption (read path and open path)",
           "PASS" if (err_open and err_read) else "FAIL",
           f"materialise on open instance -> {err_read}; reopen -> {err_open}")

    db = tmp / "journal.sqlite3"
    triad = ProductionTriad(str(db))
    triad.put("tenant-a", b"one"); triad.put("tenant-a", b"two")
    con = sqlite3.connect(db)
    con.execute("UPDATE journal SET entry_hash=? WHERE tenant_id='tenant-a' AND sequence=0", ("0" * 64,))
    con.commit(); con.close()
    err_open = _raises(lambda: ProductionTriad(str(db)))
    if err_open:
        record("X5b", "Fail-closed on journal tamper", "PASS", f"reopen refused: {err_open}")
        return
    reopened = ProductionTriad(str(db))
    cont = reopened.theseus.verify_journal_continuity("tenant-a")
    err = _raises(reopened.theseus.verify_store)
    record("X5b", "Fail-closed on journal tamper", "PASS" if (not cont and err) else "FAIL",
           f"reopen accepted; continuity={cont}; verify_store -> {err}")


def check_readiness_and_console(tmp: Path) -> None:
    os.environ.setdefault("CHRONUS_ENV", "test")
    try:
        from fastapi.testclient import TestClient
        from chronus.service.app import create_app
    except Exception as exc:
        record("X6", "Readiness derived from component health", "FAIL", f"service import failed: {exc}")
        return
    # Behavioural probe: corrupt every custody store the service can be configured with,
    # then ask the deployed app whether it is ready.
    custody = tmp / "service_custody.sqlite3"
    store = DurableTheseusService(str(custody))
    rec = store.store("tenant-a", b"service-custody")
    con = sqlite3.connect(custody)
    con.execute("UPDATE objects SET payload=? WHERE object_id=?", (b"corrupted", rec.object_id))
    con.commit(); con.close()
    custody_env = ("CHRONUS_MINING_CUSTODY_PATH", "CHRONUS_MINING_ADMIN_CUSTODY_PATH")
    saved = {k: os.environ.get(k) for k in custody_env}
    try:
        for k in custody_env:
            os.environ[k] = str(custody)
        client = TestClient(create_app())
        ready = client.get("/health/ready")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    body = ready.json() if ready.headers.get("content-type", "").startswith("application/json") else {}
    if ready.status_code >= 500 and ready.status_code != 503:
        status = "FAIL"
    elif ready.status_code == 503:
        status = "PASS"
    else:
        status = "GAP"
    record("X6", "Readiness derived from component health (THESEUS custody)", status,
           f"with every configurable custody store corrupted ({', '.join(custody_env)}), the deployed app "
           f"(Dockerfile CMD chronus.service.app:app) answered /health/ready {ready.status_code} {json.dumps(body)[:200]}")

    from chronus.execution.reference import NativeMathReferenceBackend
    backing = type(NativeMathReferenceBackend._theseus).__name__
    record("X7", "Chronus Studio Web Console shows durable triad custody state",
           "GAP" if backing != "DurableTheseusService" else "PASS",
           f"/console storage panel reads NativeMathReferenceBackend._theseus = {backing} "
           "(in-memory compatibility helper), not the ProductionTriad/DurableTheseusService custody store; "
           "frontend/app has no triad/THESEUS custody view")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="-")
    args = ap.parse_args()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for fn in (check_fresh_process_replay, check_orphans, check_tenant_isolation_and_concurrency,
                   check_fail_closed, check_readiness_and_console):
            try:
                fn(tmp)
            except Exception as exc:
                record(fn.__name__, fn.__doc__ or fn.__name__, "FAIL", f"check crashed: {type(exc).__name__}: {exc}")
    doc = {
        "schema": "chronus-triad-cross-checks-v1",
        "git_sha": sha,
        "evidence_class": "SOFTWARE_VERIFIED",
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "machine": platform.machine(), "physical_device_evidence": False},
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {s: sum(1 for r in RESULTS if r["status"] == s) for s in ("PASS", "FAIL", "GAP")},
        "results": RESULTS,
    }
    text = json.dumps(doc, indent=2)
    if args.out == "-":
        print(text)
    else:
        Path(args.out).write_text(text + "\n")
    print(json.dumps(doc["summary"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
