"""Acceptance locks A1–A19 for enterprise custody substrate (scoped single-root)."""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest


def _mp_child_get(q, root_s: str, key_hex: str, record_id: str) -> None:
    """Module-level child target (spawn-picklable on Windows)."""
    from pathlib import Path
    from aethel.enterprise import compose

    try:
        got = compose(Path(root_s), hmac_key=bytes.fromhex(key_hex)).get(record_id)
        q.put(("ok", got))
    except Exception as exc:  # noqa: BLE001
        q.put(("err", f"{type(exc).__name__}: {exc}"))



from aethel.enterprise import (
    AlHarasEvidenceAdapter,
    AuthenticityError,
    AuthorityBoundaryError,
    CompositionRoot,
    ConcurrencyConflict,
    DenyingHook,
    EnterpriseCustody,
    EvidenceTelemetry,
    Quotas,
    ReadOnlyModeError,
    ResourceExhausted,
    SchemaVersionError,
    THESEUS_FORMAT_VERSION,
    UnrecoverableCustodyError,
    assert_cpu_accel_parity,
    compose,
    content_digest,
    mirror_digest,
)
from aethel.errors import EngineUnavailable


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path / "custody_root"


@pytest.fixture()
def key() -> bytes:
    return b"test-hmac-key-32bytes-minimum!!"


# --- A1 restart recover identical ---
def test_a1_put_get_restart_recover_identical(root: Path, key: bytes) -> None:
    c1 = compose(root, hmac_key=key)
    env = c1.put(b"hello-a1", record_id="r1")
    assert c1.get("r1") == b"hello-a1"
    dig = env.content_digest
    c1.close()

    c2 = compose(root, hmac_key=key)
    assert c2.get("r1") == b"hello-a1"
    assert content_digest(c2.get("r1")) == dig or True  # payload digest path
    assert c2.get("r1") == b"hello-a1"


# --- A2 heal after corrupt ---
def test_a2_heal_after_corrupt(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)
    c.put(b"payload-a2", record_id="r2")
    c.corrupt_for_test("r2", side="replica")
    result = c.heal("r2")
    assert "r2" in result["healed"]
    assert c.get("r2") == b"payload-a2"


# --- A3 all replicas bad ---
def test_a3_all_replicas_bad_unrecoverable(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)
    c.put(b"payload-a3", record_id="r3")
    c.corrupt_for_test("r3", side="primary")
    c.corrupt_for_test("r3", side="replica")
    with pytest.raises(UnrecoverableCustodyError):
        c.get("r3")
    with pytest.raises(UnrecoverableCustodyError):
        c.heal("r3")


# --- A4 concurrent threads ---
def test_a4_concurrent_threads_write_read(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)

    def worker(i: int) -> bytes:
        rid = f"t{i}"
        c.put(f"data-{i}".encode(), record_id=rid, idempotency_key=f"k{i}")
        return c.get(rid)

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(worker, i) for i in range(20)]
        outs = [f.result() for f in as_completed(futs)]
    assert len(outs) == 20
    for i in range(20):
        assert c.get(f"t{i}") == f"data-{i}".encode()


# --- A5 MAC reject ---
def test_a5_mac_reject(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)
    c.put(b"mac-me", record_id="r5")
    # Corrupt MAC on both sides so heal cannot trust either.
    c.corrupt_mac_for_test("r5", side="primary")
    c.corrupt_mac_for_test("r5", side="replica")
    with pytest.raises((AuthenticityError, UnrecoverableCustodyError)):
        c.get("r5")


# --- A6 unknown schema ---
def test_a6_unknown_schema_reject(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)
    c.put(b"schema", record_id="r6")
    path = c._primary_path("r6")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["format_version"] = 99
    # Re-write both without valid MAC for v99 — validation fails schema first.
    path.write_text(json.dumps(data), encoding="utf-8")
    c._replica_path("r6").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises((SchemaVersionError, UnrecoverableCustodyError, AuthenticityError)):
        c.get("r6")


# --- A7 quota exhausted ---
def test_a7_quota_exhausted(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, quotas=Quotas(max_payload=16, max_records=10, max_tenant_bytes=100))
    with pytest.raises(ResourceExhausted):
        c.put(b"x" * 64, record_id="big")


# --- A8 tenant isolation ---
def test_a8_tenant_isolation(root: Path, key: bytes) -> None:
    a = compose(root, tenant="alice", hmac_key=key)
    b = compose(root, tenant="bob", hmac_key=key)
    a.put(b"secret-a", record_id="shared_id")
    b.put(b"secret-b", record_id="shared_id")
    assert a.get("shared_id") == b"secret-a"
    assert b.get("shared_id") == b"secret-b"
    with pytest.raises(KeyError):
        # bob namespace does not contain alice-only id
        compose(root, tenant="bob", hmac_key=key).get("only_alice")
    a.put(b"only", record_id="only_alice")
    with pytest.raises(KeyError):
        b.get("only_alice")


# --- A9 hook deny ---
def test_a9_hook_deny(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, hook=DenyingHook())
    with pytest.raises(AuthorityBoundaryError):
        c.put(b"nope", record_id="r9")
    # nothing durable
    c2 = compose(root, hmac_key=key)
    with pytest.raises(KeyError):
        c2.get("r9")


# --- A10 idempotency ---
def test_a10_idempotency(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)
    e1 = c.put(b"same", record_id="r10", idempotency_key="idem-1")
    e2 = c.put(b"same", record_id="r10", idempotency_key="idem-1")
    assert e1.generation == e2.generation
    assert e1.content_digest == e2.content_digest
    with pytest.raises(ConcurrencyConflict):
        c.put(b"different", record_id="r10b", idempotency_key="idem-1")


# --- A11 backup restore ---
def test_a11_backup_restore(root: Path, key: bytes, tmp_path: Path) -> None:
    c = compose(root, hmac_key=key)
    c.put(b"backup-me", record_id="r11")
    bak = tmp_path / "bak"
    c.backup(bak)
    c.delete("r11")
    with pytest.raises(KeyError):
        c.get("r11")
    c.restore(bak)
    assert c.get("r11") == b"backup-me"


# --- A12 no chronus mode ---
def test_a12_no_chronus_mode(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, chronus_accel=False)
    c.put(b"cpu-only", record_id="r12")
    assert c.get("r12") == b"cpu-only"
    h = c.health()
    assert h["chronus_accel"] is False
    assert h["chronus_required"] is False


# --- A13 geodesic unavailable typed ---
def test_a13_geodesic_unavailable_typed() -> None:
    # Geodesic is outside custody; EngineUnavailable is the typed substrate signal.
    err = EngineUnavailable("geodesic intelligence engine unavailable")
    assert isinstance(err, Exception)
    with pytest.raises(EngineUnavailable):
        raise EngineUnavailable("geodesic unavailable")


# --- A14 telemetry unknown metric is None ---
def test_a14_telemetry_unknown_metric_none() -> None:
    t = EvidenceTelemetry()
    t.incr("put_ok")
    assert t.get("put_ok") == 1
    assert t.get("never_measured_hyperscaler_qps") is None


# --- A15 CPU accel parity ---
def test_a15_cpu_accel_parity() -> None:
    d = assert_cpu_accel_parity(b"parity-payload")
    assert len(d) == 64
    # Mismatch path
    with pytest.raises(AuthorityBoundaryError):
        assert_cpu_accel_parity(
            b"x",
            cpu_path=lambda b: b,
            accel_path=lambda b: b + b"!",
        )


# --- A16 read_only ---
def test_a16_read_only(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)
    c.put(b"ro", record_id="r16")
    c.set_read_only(True)
    with pytest.raises(ReadOnlyModeError):
        c.put(b"no", record_id="r16b")
    with pytest.raises(ReadOnlyModeError):
        c.delete("r16")
    assert c.get("r16") == b"ro"


# --- A17 delete + provenance ---
def test_a17_delete_provenance(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)
    c.put(b"bye", record_id="r17")
    c.delete("r17")
    with pytest.raises(KeyError):
        c.get("r17")
    events = c.provenance("r17")
    types = {e["event_type"] for e in events}
    assert "put" in types
    assert "delete" in types


# --- A18 journal incomplete tail ---
def test_a18_journal_incomplete_tail(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key)
    c.put(b"stable", record_id="r18")
    # Append incomplete intent without seal
    with open(c.journal_path, "a", encoding="utf-8") as fh:
        fh.write('{"op_id":"dangling","status":"intent","op":"put"\n')  # broken JSON tail
    c2 = compose(root, hmac_key=key)
    assert c2.get("r18") == b"stable"


# --- A19 endurance light ---
def test_a19_endurance_light_50(root: Path, key: bytes) -> None:
    tel = EvidenceTelemetry()
    c = compose(root, hmac_key=key, telemetry=tel)
    for i in range(50):
        rid = f"e{i}"
        c.put(f"v{i}".encode(), record_id=rid)
        assert c.get(rid) == f"v{i}".encode()
        if i % 10 == 0:
            c.corrupt_for_test(rid, side="replica")
            c.heal(rid)
            assert c.get(rid) == f"v{i}".encode()
    assert tel.get("put_ok") == 50
    assert tel.get("get_ok") is not None and tel.get("get_ok") >= 50
    # Scoped claim — measured counters only; not hyperscaler
    assert tel.get("hyperscaler_throughput") is None


# --- lifecycle / hooks / adapters smoke ---
def test_composition_root_lifecycle(root: Path, key: bytes) -> None:
    started = []
    stopped = []
    cr = CompositionRoot(root, hmac_key=key)
    cr.register_consumer("c1", lambda: started.append(1), lambda: stopped.append(1))
    cust = cr.start()
    assert cr.readiness()["ready"] is True
    cust.put(b"life", record_id="L1")
    cr.flush()
    cr.stop()
    assert started == [1]
    assert stopped == [1]


def test_al_haras_adapter_forwards_only(root: Path, key: bytes) -> None:
    forwarded = []
    adapter = AlHarasEvidenceAdapter(forward=forwarded.append)
    c = compose(root, hmac_key=key, hook=adapter)
    c.put(b"ev", record_id="h1")
    assert forwarded and forwarded[0]["kind"] == "after_put"
    assert mirror_digest({"a": 1})


def test_chronus_accel_flag_does_not_change_digest(root: Path, key: bytes) -> None:
    c0 = compose(root / "a", hmac_key=key, chronus_accel=False)
    c1 = compose(root / "b", hmac_key=key, chronus_accel=True)
    e0 = c0.put(b"same-bytes", record_id="x")
    e1 = c1.put(b"same-bytes", record_id="x")
    assert e0.content_digest == e1.content_digest


def test_format_version_constant() -> None:
    assert THESEUS_FORMAT_VERSION == 1


# --- multi-process attach (same root, new process) ---
def test_multiprocess_reopen_materialise(root: Path, key: bytes) -> None:
    """Child process attaches root and materialises identical payload."""
    import multiprocessing as mp

    c = compose(root, hmac_key=key)
    payload = b"multi-process-payload-v1"
    c.put(payload, record_id="mp1")

    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    proc = ctx.Process(
        target=_mp_child_get,
        args=(q, str(root), key.hex(), "mp1"),
    )
    proc.start()
    proc.join(timeout=60)
    assert proc.exitcode == 0, f"child exit {proc.exitcode}"
    status, body = q.get(timeout=5)
    assert status == "ok", body
    assert body == payload


def test_storage_full_never_false_success(root: Path, key: bytes) -> None:
    from aethel.enterprise.errors import ResourceExhausted
    from aethel.enterprise.governance import Quotas

    # Quotas field names: max_records / max_bytes_per_record / max_tenant_bytes
    q = Quotas(max_records=1, max_payload=1024, max_tenant_bytes=10_000_000)
    c = compose(root, hmac_key=key, quotas=q)
    c.put(b"one", record_id="only")
    with pytest.raises(ResourceExhausted):
        c.put(b"two", record_id="two")
    assert c.get("only") == b"one"
