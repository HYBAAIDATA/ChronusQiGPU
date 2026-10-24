"""Real AL HARAS/SQLite/HMAC; RuntimeDouble is transport-only, not math evidence."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

from hyba_turing_service.control import Conflict, Denied, Unavailable
from hyba_turing_service.runtime import DurableRuntime, ResultCustody
from test_control import env, REQUEST, RuntimeDouble  # noqa: F401
from test_enterprise import service, headers  # noqa: F401

KEY = b"TEST-ONLY-RECOVERY-KEY-DO-NOT-DEPLOY" * 2


def interrupt(env, tmp_path, monkeypatch, *, verdict="PASS"):
    p, ops, a, _, onboard, *_ = env
    onboard()
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    custody = ResultCustody(tmp_path / "custody", integrity_key=KEY)
    runtime = RuntimeDouble(verdict)
    wrapped = DurableRuntime(
        runtime, custody, "a", "j", admission_hash=p._job("a", "j")["request_hash"]
    )
    original = p._complete_report

    def stop_before_database(*args, **kwargs):
        raise OSError("TEST interruption after durable report receipt, before completion")

    monkeypatch.setattr(p, "_complete_report", stop_before_database)
    with pytest.raises(OSError):
        p.execute(ops, "operator", tenant="a", job="j", runtime=wrapped)
    monkeypatch.setattr(p, "_complete_report", original)
    assert p._job("a", "j")["state"] == "running"
    return custody, runtime


def recover(p, ops, source):
    return p.recover_result(
        ops, "operator", tenant="a", job="j", reason="TEST recovery investigation", source=source
    )


def test_durable_result_recovers_after_database_restart_without_execution(
    env, tmp_path, monkeypatch
):
    custody, runtime = interrupt(env, tmp_path, monkeypatch)
    p, ops, a, _, _, reopen, *_ = env
    restarted = reopen()
    try:
        report = recover(restarted, ops, ResultCustody(tmp_path / "custody", integrity_key=KEY))
        assert report["verdict"] == "PASS"
        assert restarted._job("a", "j")["state"] == "completed"
        assert len(restarted.usage(a, "alice", tenant="a")) == 1
        assert recover(restarted, ops, custody) == report
        assert restarted.reconcile(ops, "operator")["issues"] == []
        assert runtime.calls == 1
    finally:
        restarted.close()


def test_recovery_from_unknown_does_not_execute(env, tmp_path, monkeypatch):
    custody, runtime = interrupt(env, tmp_path, monkeypatch)
    p, ops, *_ = env
    p.db.execute("UPDATE jobs SET state='unknown' WHERE tenant='a' AND job='j'")
    recover(p, ops, custody)
    assert p._job("a", "j")["state"] == "completed"
    assert runtime.calls == 1


def test_failed_retained_execution_is_not_promoted(env, tmp_path, monkeypatch):
    custody, runtime = interrupt(env, tmp_path, monkeypatch, verdict="FAIL")
    p, ops, a, *_ = env
    assert recover(p, ops, custody)["verdict"] == "FAIL"
    assert p._job("a", "j")["state"] == "failed"
    assert p.usage(a, "alice", tenant="a") == []
    assert runtime.calls == 1


def test_customer_cannot_recover_operator_job(env, tmp_path, monkeypatch):
    custody, _ = interrupt(env, tmp_path, monkeypatch)
    p, _, a, *_ = env
    with pytest.raises(Denied):
        p.recover_result(a, "alice", tenant="a", job="j", reason="test", source=custody)
    assert p._job("a", "j")["state"] == "running"


def test_unsigned_legacy_report_is_not_recovery_evidence(env, tmp_path, monkeypatch):
    custody, _ = interrupt(env, tmp_path, monkeypatch)
    p, ops, *_ = env
    next(custody.root.rglob("*.receipt")).unlink()
    with pytest.raises(Unavailable):
        recover(p, ops, custody)
    assert p._job("a", "j")["state"] == "running"


@pytest.mark.parametrize("part", ["report", "signature", "admission", "tenant", "job", "request"])
def test_tampering_is_rejected_without_state_or_usage_change(env, tmp_path, monkeypatch, part):
    custody, _ = interrupt(env, tmp_path, monkeypatch)
    p, ops, *_ = env
    receipt = next(custody.root.rglob("*.receipt"))
    if part == "report":
        next(custody.root.rglob("*.json")).write_text('{"verdict":"PASS"}')
    else:
        value = json.loads(receipt.read_text())
        if part == "signature":
            value["signature"] = "0" * 64
        else:
            key = {"admission": "admission_hash", "request": "request_digest"}.get(part, part)
            value["body"][key] = "foreign"
        receipt.write_text(json.dumps(value))
    with pytest.raises(Unavailable):
        recover(p, ops, custody)
    assert p._job("a", "j")["state"] == "running"
    assert p.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0] == 0


def test_valid_other_admission_receipt_cannot_be_substituted(env, tmp_path, monkeypatch):
    custody, _ = interrupt(env, tmp_path, monkeypatch)
    p, ops, *_ = env
    with pytest.raises(Unavailable):
        custody.recover("a", "j", REQUEST, admission_hash="foreign-admission")
    with pytest.raises(Unavailable):
        custody.recover(
            "a", "j", {**REQUEST, "seed": 999}, admission_hash=p._job("a", "j")["request_hash"]
        )
    assert p._job("a", "j")["state"] == "running"


def test_wrong_key_rejected_and_retained_key_rotation_works(env, tmp_path, monkeypatch):
    custody, _ = interrupt(env, tmp_path, monkeypatch)
    p, ops, *_ = env
    with pytest.raises(Unavailable):
        recover(p, ops, ResultCustody(custody.root, integrity_key=b"wrong" * 8))
    rotated = ResultCustody(
        custody.root, integrity_key=b"new-key" * 8, previous_integrity_keys=(KEY,)
    )
    recover(p, ops, rotated)
    assert p._job("a", "j")["state"] == "completed"


def test_recovery_never_overrides_operator_resolution(env, tmp_path, monkeypatch):
    custody, _ = interrupt(env, tmp_path, monkeypatch)
    p, ops, *_ = env
    original = custody.recover

    def resolve_during_read(*args, **kwargs):
        report = original(*args, **kwargs)
        p.resolve_unknown(ops, "operator", tenant="a", job="j", reason="TEST fence")
        return report

    monkeypatch.setattr(custody, "recover", resolve_during_read)
    with pytest.raises(Conflict):
        recover(p, ops, custody)
    assert p._job("a", "j")["state"] == "failed"
    assert p.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0] == 0


def test_recovery_audit_failure_rolls_back_completion_and_usage(env, tmp_path, monkeypatch):
    custody, _ = interrupt(env, tmp_path, monkeypatch)
    p, ops, *_ = env
    original = p._audit

    def audit_failure(tenant, actor, action, detail):
        if action == "recover_complete":
            raise OSError("TEST audit unavailable")
        return original(tenant, actor, action, detail)

    monkeypatch.setattr(p, "_audit", audit_failure)
    with pytest.raises(OSError):
        recover(p, ops, custody)
    assert p._job("a", "j")["state"] == "running"
    assert p.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0] == 0
    assert p.db.execute("SELECT COUNT(*) FROM delivery").fetchone()[0] == 0


def test_concurrent_recovery_records_completion_once(env, tmp_path, monkeypatch):
    custody, runtime = interrupt(env, tmp_path, monkeypatch)
    p, ops, _, _, _, reopen, *_ = env

    def once(_):
        other = reopen()
        try:
            return recover(other, ops, custody)
        finally:
            other.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(once, range(2)))
    assert results[0] == results[1]
    assert p.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0] == 1
    assert (
        len([a for a in p.audit(env[2], "alice", tenant="a") if a["action"] == "recover_complete"])
        == 1
    )
    assert runtime.calls == 1


@pytest.mark.parametrize("part", ["report", "receipt"])
def test_symlinked_evidence_is_rejected(env, tmp_path, monkeypatch, part):
    custody, _ = interrupt(env, tmp_path, monkeypatch)
    p, ops, *_ = env
    path = next(custody.root.rglob("*.json" if part == "report" else "*.receipt"))
    saved = tmp_path / "saved"
    saved.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(saved)
    with pytest.raises(Unavailable):
        recover(p, ops, custody)


def test_http_operator_recovery_uses_configured_source_and_rejects_customer(service, monkeypatch):
    s = service
    custody = ResultCustody(s.tmp / "authenticated-custody", integrity_key=KEY)
    s.deps.custody = custody
    admitted = s.client.post(
        "/api/customer/a/jobs",
        headers=headers(s, "bob"),
        json=dict(project="p", job="http-recover", request=REQUEST),
    )
    assert admitted.status_code == 200
    row = s.plane._job("a", "http-recover")
    report = RuntimeDouble().run(REQUEST)
    custody.commit_execution(
        "a", "http-recover", REQUEST, report, admission_hash=row["request_hash"]
    )
    s.plane.db.execute("UPDATE jobs SET state='unknown' WHERE job='http-recover'")
    path = "/api/ops/customers/a/recover-result"
    body = dict(job="http-recover", reason="TEST operator investigation")
    assert s.client.post(path, headers=headers(s, "bob"), json=body).status_code == 403
    response = s.client.post(path, headers=headers(s, "operator"), json=body)
    assert response.status_code == 200, response.text
    assert response.json()["result"]["verdict"] == "PASS"
    assert s.plane._job("a", "http-recover")["state"] == "completed"
    assert s.client.post(path, headers=headers(s, "operator"), json=body).status_code == 200
    assert s.plane.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0] == 1


def test_recovery_is_disabled_without_a_key(tmp_path):
    custody = ResultCustody(tmp_path / "unsigned")
    custody.commit("a", "j", RuntimeDouble().run(REQUEST))
    with pytest.raises(Unavailable):
        custody.recover("a", "j", REQUEST, admission_hash="test")


@pytest.mark.parametrize("key", [b"short", "not-bytes", True])
def test_invalid_integrity_keys_rejected(tmp_path, key):
    with pytest.raises(ValueError):
        ResultCustody(tmp_path / "invalid", integrity_key=key)


def test_configured_custody_derives_separate_key_and_retains_rotation(tmp_path):
    import base64
    import hashlib
    import hmac
    from hyba_turing_service.main import configured_custody

    old_file = tmp_path / "old-key"
    new_file = tmp_path / "new-key"
    old_file.write_bytes(base64.b64encode(b"TEST-old-custody-master-key-000000"))
    new_file.write_bytes(base64.b64encode(b"TEST-new-custody-master-key-000000"))
    old_file.chmod(0o600)
    new_file.chmod(0o600)
    config = dict(custody_root=str(tmp_path / "results"), operator_key_file=str(old_file))
    original = configured_custody(config)
    assert original._integrity_keys == (
        hmac.new(
            base64.b64decode(old_file.read_bytes()), b"turing-service-recovery-v1", hashlib.sha256
        ).digest(),
    )
    report = RuntimeDouble().run(REQUEST)
    original.commit_execution("a", "j", REQUEST, report, admission_hash="test")
    config.update(
        custody_integrity_key_file=str(new_file),
        previous_custody_integrity_key_files=[str(old_file)],
    )
    rotated = configured_custody(config)
    assert rotated.recover("a", "j", REQUEST, admission_hash="test") == report
    config.pop("previous_custody_integrity_key_files")
    with pytest.raises(Unavailable):
        configured_custody(config).recover("a", "j", REQUEST, admission_hash="test")


@pytest.mark.parametrize("raw", [b"not base64!", b"c2hvcnQ="])
def test_configured_custody_rejects_invalid_master_key(tmp_path, raw):
    from hyba_turing_service.main import configured_custody

    key = tmp_path / "private-key"
    key.write_bytes(raw)
    key.chmod(0o600)
    with pytest.raises(ValueError):
        configured_custody(dict(custody_root=str(tmp_path / "results"), operator_key_file=str(key)))
