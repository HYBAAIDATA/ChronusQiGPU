"""Interrupted custody writes resume from exact requests, not invented evidence."""
import json

import pytest

from hyba_db.models import IntegrityFailure
from test_m3_adversarial import _plane, _put


@pytest.mark.parametrize('fail_at', [1, 2, 3, 4])
def test_resume_after_each_custody_boundary(tmp_path, monkeypatch, fail_at):
    store, custody, tenant = _plane(tmp_path)
    root = tmp_path / 'cas'
    original = custody.put_record
    calls = 0

    def fail(t, record):
        nonlocal calls
        calls += 1
        if calls == fail_at:
            raise RuntimeError('injected custody quota failure')
        return original(t, record)

    monkeypatch.setattr(custody, 'put_record', fail)
    with pytest.raises(RuntimeError, match='injected'):
        _put(store, tenant, root)
    intent = store._db.execute("SELECT * FROM file_intents WHERE state!='COMMITTED'").fetchone()
    retained = json.loads(intent['detail_json'])
    assert retained['request']['links'] == [['external:test', 'adv', 'describes']]
    assert 'injected' in retained['error']
    monkeypatch.setattr(custody, 'put_record', original)
    result = store.files.resume_write_intent(tenant, intent['intent_id'], root)
    assert result['state'] == 'COMMITTED'
    assert result['request_source'] == 'retained'
    assert store.files.reconcile_files(tenant, root).passed
    assert store.files.verify_database(tenant)['passed']
    after = store._db.execute('SELECT detail_json FROM file_intents WHERE intent_id=?', (intent['intent_id'],)).fetchone()
    assert json.loads(after[0])['error'] == retained['error']
    assert not store.files.resume_write_intent(tenant, intent['intent_id'], root)['replayed']
    store.close()
    custody.close()


def _failed(tmp_path, monkeypatch):
    store, custody, tenant = _plane(tmp_path)
    original = custody.put_record
    monkeypatch.setattr(custody, 'put_record', lambda *a: (_ for _ in ()).throw(RuntimeError('quota')))
    with pytest.raises(RuntimeError):
        _put(store, tenant, tmp_path / 'cas')
    monkeypatch.setattr(custody, 'put_record', original)
    intent = store._db.execute("SELECT * FROM file_intents WHERE state!='COMMITTED'").fetchone()
    return store, custody, tenant, intent


@pytest.mark.parametrize('attack', ['bytes', 'request', 'root', 'legacy'])
def test_resume_refuses_corruption_and_inference(tmp_path, monkeypatch, attack):
    from pathlib import Path
    store, custody, tenant, intent = _failed(tmp_path, monkeypatch)
    root = tmp_path / 'cas'
    kwargs = {}
    if attack == 'bytes':
        Path(intent['final_uri']).write_bytes(b'corrupt')
    elif attack == 'request':
        req = json.loads(intent['detail_json'])['request']
        req['producer'] = 'pool'
        kwargs['legacy_request'] = req
    elif attack == 'root':
        root = tmp_path / 'other'
    else:
        detail = json.loads(intent['detail_json'])
        detail.pop('request')
        with store._tx() as db:
            db.execute('UPDATE file_intents SET detail_json=? WHERE intent_id=?', (json.dumps(detail), intent['intent_id']))
    with pytest.raises(IntegrityFailure):
        store.files.resume_write_intent(tenant, intent['intent_id'], root, **kwargs)
    assert not store.files.reconcile_files(tenant, tmp_path / 'cas').passed
    store.close()
    custody.close()


def test_restart_automatically_resumes_retained_request(tmp_path, monkeypatch):
    from chronus.mla1517.mining.storage_recorder import MiningStorageRecorder
    from test_m3_adversarial import INTEGRITY_KEY, CUSTODY_KEY
    store, custody, tenant, intent = _failed(tmp_path, monkeypatch)
    namespace = store._db.execute('SELECT namespace FROM tenants WHERE tenant_id=?', (tenant,)).fetchone()[0]
    store.close()
    custody.close()
    for key, value in {
        'PYTHIA_STORAGE_DB': str(tmp_path / 'adv.db'),
        'PYTHIA_STORAGE_ROOT': str(tmp_path / 'cas'),
        'PYTHIA_STORAGE_CUSTODY_ROOT': str(tmp_path / 'custody'),
        'PYTHIA_STORAGE_INTEGRITY_KEY_HEX': INTEGRITY_KEY.hex(),
        'PYTHIA_STORAGE_CUSTODY_KEY_HEX': CUSTODY_KEY.hex(),
        'PYTHIA_STORAGE_TENANT': namespace,
    }.items():
        monkeypatch.setenv(key, value)
    recorder = MiningStorageRecorder.from_env(strict=True)
    try:
        assert recorder.files.reconcile_files(tenant, tmp_path / 'cas').passed
        assert recorder._fresh_job_observed is False
        assert recorder._store._db.execute('SELECT state FROM file_intents WHERE intent_id=?', (intent['intent_id'],)).fetchone()[0] == 'COMMITTED'
    finally:
        recorder._store.close()
        recorder.files.custody.close()


def test_recovery_receipt_failure_does_not_commit_original(tmp_path, monkeypatch):
    store, custody, tenant, intent = _failed(tmp_path, monkeypatch)
    original = custody.put_record

    def fail_receipt(t, record):
        if record.kind == 'file_write_recovery':
            raise RuntimeError('recovery receipt quota')
        return original(t, record)

    monkeypatch.setattr(custody, 'put_record', fail_receipt)
    with pytest.raises(RuntimeError, match='recovery receipt quota'):
        store.files.resume_write_intent(tenant, intent['intent_id'], tmp_path / 'cas')
    assert not store.files.reconcile_files(tenant, tmp_path / 'cas').passed
    monkeypatch.setattr(custody, 'put_record', original)
    store.files.resume_write_intent(tenant, intent['intent_id'], tmp_path / 'cas')
    assert store.files.reconcile_files(tenant, tmp_path / 'cas').passed
    store.close()
    custody.close()
