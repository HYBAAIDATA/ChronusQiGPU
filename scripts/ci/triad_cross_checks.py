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
    receipt = triad.protect_payload("tenant-a", os.urandom(8192), shards, shard_count=4)
    files = sorted(p for p in shards.rglob("*") if p.is_file())
    (shards / "stray.shard").write_bytes(b"no-manifest")
    recovered = triad.recover_protected_payload(receipt, shards)
    stray_detected = False  # no API enumerates shard files without a manifest
    for victim in files[:2]:
        victim.unlink()
    err = _raises(lambda: triad.recover_protected_payload(receipt, shards))
    record("X2c", "Orphan reconciliation: protected shard files <-> THESEUS manifest",
           "GAP" if not stray_detected else "PASS",
           f"{len(files)} shard files; recovery with a stray file present returned {len(recovered)} bytes; "
           f"two missing shards fail closed: {bool(err)} ({err}); shard files without a manifest are not "
           "enumerated or reported by any maintained API")


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
    err_open = _raises(lambda: ProductionTriad(str(db)).theseus.verify_store())
    err_read = _raises(lambda: ProductionTriad(str(db)).materialise(r))
    record("X5a", "Fail-closed on unrecoverable content corruption", "PASS" if (err_open and err_read) else "FAIL",
           f"verify_store -> {err_open}; materialise -> {err_read}")

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
    client = TestClient(create_app())
    ready = client.get("/health/ready")
    body = ready.json() if ready.headers.get("content-type", "").startswith("application/json") else {}
    import inspect
    from chronus.service.routers import health
    src = inspect.getsource(health.readiness_probe)
    derives = any(k in src for k in ("Durable", "theseus", "verify_store", "evidence(", "ProductionTriad"))
    record("X6", "Readiness derived from component health (THESEUS custody, OVID, execution)",
           "PASS" if derives else "GAP",
           f"deployed app (Dockerfile CMD chronus.service.app:app) /health/ready -> {ready.status_code} "
           f"{json.dumps(body)[:200]}; readiness_probe consults THESEUS/triad health: {derives} "
           "(it checks only the optional remote execution adapter)")

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
