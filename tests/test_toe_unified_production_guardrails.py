"""Adversarial regression evidence; these tests do not certify deployment readiness."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading

import pytest

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.data_layer import UnifiedDataLayer
from toe.unified.intelligence import ModelRegistry
from toe.unified.operations import Operations
from toe.unified.security import AccessDenied, SecurityModel

OP = dict(operator_digest='d', operator_kind='event_stream')


def rows(offset=0, flip=False):
    return [{'x': float(i + offset), 'y': int(i + offset > 5) ^ flip} for i in range(12)]


def locked_platform():
    p = UnifiedAnalyticsPlatform()
    p.security.enforced = True
    p.security.grant('root', 'admin')
    p.security.authenticate('root')
    p.security.grant('reader', 'reader')
    p.security.authenticate('reader')
    return p


def test_no_probe_is_unknown():
    assert Operations().availability() is None


def test_partial_ingest_never_publishes(monkeypatch):
    import toe.unified.data_layer as dl
    layer = UnifiedDataLayer()
    before = deepcopy({k: v for k, v in vars(layer).items() if k != '_lock'})
    real_compress = dl.zlib.compress
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('injected compression failure')
        return real_compress(*args, **kwargs)

    monkeypatch.setattr(dl.zlib, 'compress', fail_second)
    with pytest.raises(OSError):
        layer.ingest('s', 'e', [{'id': 1}, {'id': 2}], **OP)
    assert {k: v for k, v in vars(layer).items() if k != '_lock'} == before


def test_nested_payloads_are_detached_on_every_public_read():
    layer = UnifiedDataLayer()
    original = {'nested': {'values': [1, 2]}}
    layer.ingest('s', 'e', [original], **OP)
    original['nested']['values'].append(3)
    exported = layer.snapshot()
    exported[0]['payload']['nested']['values'].append(4)
    indexed = layer.rows('e')[0]
    indexed.payload['nested']['values'].append(5)
    scanned = layer.scan_rows('e')[0]
    scanned.payload['nested']['values'].append(6)
    assert layer.snapshot()[0]['payload'] == {'nested': {'values': [1, 2]}}
    assert layer.restore_payload(layer.snapshot()[0]['digest']) == {'nested': {'values': [1, 2]}}


def test_import_failure_rolls_back_all_groups():
    p = UnifiedAnalyticsPlatform()
    with pytest.raises((TypeError, ValueError)):
        p.import_records([
            {'source': 's', 'entity': 'a', 'payload': {'id': 1}},
            {'source': 's', 'entity': 'z', 'payload': {'bad': float('nan')}},
        ])
    assert p.export_records() == []
    assert p.data.audit == []
    assert p._receipts == []


def test_import_verifies_claimed_content_digest():
    p = UnifiedAnalyticsPlatform()
    with pytest.raises(ValueError, match='digest'):
        p.import_records([{'source': 's', 'entity': 'e', 'payload': {'id': 1}, 'digest': 'forged'}])
    assert p.export_records() == []


def test_import_retains_quarantine_and_source_lineage():
    source = UnifiedAnalyticsPlatform()
    receipt = source.ingest_rows('s', 'e', [{'nested': [1]}])['receipt']
    source.quarantine(receipt.batch_id)
    exported = source.export_records()
    dest = UnifiedAnalyticsPlatform()
    dest.import_records(exported)
    imported = dest.export_records()[0]
    assert imported['quarantined'] is True
    assert imported['lineage'][-1]['operator_digest'] == exported[0]['operator_digest']
    exported[0]['payload']['nested'].append(99)
    assert dest.export_records()[0]['payload'] == {'nested': [1]}
    assert dest.ask('count e')['rows'][0]['count'] == 0


@pytest.mark.parametrize('call', [
    lambda p: p.govern('e', 'public', 1, 'mallory'),
    lambda p: p.quarantine('missing'),
    lambda p: p.release('missing'),
    lambda p: p.import_records([]),
    lambda p: p.watch('missing', [{'x': 1, 'y': 1}]),
    lambda p: p._monitor_tick(),
    lambda p: p.retire('source'),
    lambda p: p.recognize_value(1, 'source'),
    lambda p: p.file_patent('claim'),
    lambda p: p.start(),
])
def test_reader_cannot_mutate_through_alternate_facade_paths(call):
    p = locked_platform()
    with pytest.raises(AccessDenied):
        call(p)


def test_actor_identity_does_not_leak_into_background_thread():
    sec = SecurityModel()
    sec.enforced = True
    sec.grant('root', 'admin')
    sec.authenticate('root')
    def background():
        with pytest.raises(AccessDenied):
            sec.authorize('heal')
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(background).result(timeout=2)
    sec.authorize('heal')


def test_retrain_requires_nonempty_heldout_data():
    registry = ModelRegistry()
    registry.train('m', rows(), ['x'], 'y')
    with pytest.raises(ValueError, match='held.out'):
        registry.retrain('m', rows(20))
    assert registry.get('m').version == 1


def test_retrain_rejects_training_validation_overlap():
    registry = ModelRegistry()
    registry.train('m', rows(), ['x'], 'y')
    with pytest.raises(ValueError, match='overlap'):
        registry.retrain('m', rows(20), rows(20))
    assert registry.get('m').version == 1


def test_train_cannot_bypass_retraining_controls():
    registry = ModelRegistry()
    registry.train('m', rows(), ['x'], 'y')
    with pytest.raises(ValueError, match='retrain'):
        registry.train('m', rows(20), ['x'], 'y')
    assert registry.get('m').version == 1


def test_health_never_claims_production_qualification():
    p = UnifiedAnalyticsPlatform()
    h = p.health()
    assert h['availability'] is None
    assert h['status'] == 'blocked'
    assert h['production_ready'] is False
    gate = next(g for g in p.phases() if g.name == 'availability')
    assert gate.measured is None and gate.passed is False


def test_retrain_floor_and_evidence():
    registry = ModelRegistry(accuracy_floor=1.0)
    registry.train('m', rows(), ['x'], 'y')
    heldout = [{'x': 100.5 + i, 'y': i % 2} for i in range(12)]
    result = registry.retrain('m', rows(20), heldout)
    assert not result.replaced
    assert result.reason == 'candidate_below_accuracy_floor'
    assert result.status == 'rejected'
    assert len(result.evaluation_digest) == 64
    assert registry.get('m').version == 1


def test_stale_candidate_cannot_overwrite_newer_model(monkeypatch):
    import toe.unified.intelligence as intelligence
    registry = ModelRegistry()
    registry.train('m', rows(), ['x'], 'y')
    entered, release = threading.Event(), threading.Event()
    real_fit = intelligence.tensor_fit

    def controlled_fit(*args, **kwargs):
        if threading.current_thread().name == 'old-candidate':
            entered.set()
            assert release.wait(5)
        return real_fit(*args, **kwargs)

    monkeypatch.setattr(intelligence, 'tensor_fit', controlled_fit)
    heldout = [{'x': i + 0.25, 'y': int(i > 5)} for i in range(12)]
    results, failures = [], []
    def old_candidate():
        try:
            results.append(registry.retrain('m', rows(), heldout))
        except BaseException as exc:
            failures.append(exc)
    old = threading.Thread(target=old_candidate, name='old-candidate')
    old.start()
    try:
        assert entered.wait(5)
        newer = registry.retrain('m', rows(), heldout)
        assert newer.replaced and newer.live_version == 2
    finally:
        release.set()
        old.join(5)
    assert not old.is_alive() and not failures
    assert results[0].reason == 'live_model_changed_during_evaluation'
    assert results[0].live_version == registry.get('m').version == 2


def test_returned_model_cannot_mutate_live_registry():
    registry = ModelRegistry()
    result = registry.train('m', rows(), ['x'], 'y')
    result.record.version = 999
    detached = registry.get('m')
    detached.version = 888
    assert registry.get('m').version == 1


def test_checkpoint_roundtrip_and_rollback_to_new_layer(tmp_path):
    from toe.unified.checkpoint import load_checkpoint, save_checkpoint
    layer = UnifiedDataLayer()
    batch = layer.ingest('s', 'e', [{'v': [1, 2]}], **OP)
    layer.quarantine(batch.batch_id)
    path = tmp_path / 'checkpoint.json'
    checksum = save_checkpoint(layer, path)
    before = layer.snapshot()
    layer.ingest('s', 'e', [{'v': [3]}], **OP)
    restored = load_checkpoint(path)
    assert restored.snapshot() == before
    assert len(layer.snapshot()) == 2  # no in-place overwrite
    next_batch = restored.ingest('s', 'e', [{'v': [4]}], **OP)
    assert next_batch.batch_id == 'b2'
    assert len(checksum) == 64
    assert path.stat().st_mode & 0o777 == 0o600


def test_checkpoint_survives_fresh_process(tmp_path):
    import pathlib
    import subprocess
    import sys
    from toe.unified.checkpoint import save_checkpoint
    layer = UnifiedDataLayer()
    layer.ingest('s', 'e', [{'v': [1, 2]}], **OP)
    path = tmp_path / 'checkpoint.json'
    save_checkpoint(layer, path)
    root = pathlib.Path(__file__).resolve().parents[1]
    # Real imports on a complete checkout/installed artifact; namespace bypass
    # is permitted ONLY in the explicitly labelled limited snapshot runner.
    program = '''
import sys, types
root, path = sys.argv[1:]
import os
if os.environ.get('EUCLID_FOCUSED_SNAPSHOT') == '1':
    for name in ('toe', 'kellogg'):
        module = types.ModuleType(name); module.__path__ = [root + '/' + name]; sys.modules[name] = module
elif __import__('pathlib').Path(root, 'toe', '__init__.py').is_file():
    sys.path.insert(0, root)
from toe.unified.checkpoint import load_checkpoint
layer = load_checkpoint(path)
assert layer.snapshot()[0]['payload'] == {'v': [1, 2]}
assert layer.ingest('s','e',[{'v':[3]}],operator_digest='d',operator_kind='k').batch_id == 'b2'
print('restart recovery verified')
'''
    completed = subprocess.run([sys.executable, '-c', program, str(root), str(path)],
                               capture_output=True, text=True, timeout=10, cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert 'restart recovery verified' in completed.stdout


def test_checkpoint_write_failure_preserves_previous_file(tmp_path, monkeypatch):
    import toe.unified.checkpoint as cp
    layer = UnifiedDataLayer()
    layer.ingest('s', 'e', [{'n': 1}], **OP)
    path = tmp_path / 'checkpoint.json'
    cp.save_checkpoint(layer, path)
    previous = path.read_bytes()
    layer.ingest('s', 'e', [{'n': 2}], **OP)
    def fail_replace(*args):
        raise OSError('injected atomic replace failure')
    monkeypatch.setattr(cp.os, 'replace', fail_replace)
    with pytest.raises(OSError):
        cp.save_checkpoint(layer, path)
    assert path.read_bytes() == previous
    assert len(cp.load_checkpoint(path).snapshot()) == 1
    assert list(tmp_path.iterdir()) == [path]


def test_checkpoint_corruption_and_missing_file_fail_closed(tmp_path):
    import json
    from toe.unified.checkpoint import save_checkpoint, load_checkpoint
    layer = UnifiedDataLayer()
    layer.ingest('s', 'e', [{'n': 1}], **OP)
    path = tmp_path / 'checkpoint.json'
    save_checkpoint(layer, path)
    envelope = json.loads(path.read_text())
    envelope['state']['records'][0]['payload']['n'] = 999
    path.write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match='checksum'):
        load_checkpoint(path)
    with pytest.raises(FileNotFoundError):
        load_checkpoint(tmp_path / 'missing.json')


def test_checkpoint_rejects_consistently_hashed_but_inconsistent_state(tmp_path):
    import hashlib
    import json
    from toe.unified.checkpoint import save_checkpoint, load_checkpoint
    from toe.unified.data_layer import _canonical
    layer = UnifiedDataLayer()
    layer.ingest('s', 'e', [{'n': 1}], **OP)
    path = tmp_path / 'checkpoint.json'
    save_checkpoint(layer, path)
    envelope = json.loads(path.read_text())
    envelope['state']['by_entity'] = {}
    envelope['sha256'] = hashlib.sha256(_canonical(envelope['state']).encode()).hexdigest()
    path.write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match='index'):
        load_checkpoint(path)


def test_configuration_probe_is_not_availability_evidence():
    p = UnifiedAnalyticsPlatform()
    p.connect('confluent.cloud', {'events': [{'entity': 'Event', 'id': 1}]})
    p.heal()
    assert p.health()['availability'] is None
    assert p.operations.probes == 0


def test_stale_probe_does_not_make_health_healthy(monkeypatch):
    import toe.unified.operations as operations
    p = locked_platform()
    p.security.authenticate('root')
    p.start()
    now = [100.0]
    monkeypatch.setattr(operations.time, 'monotonic', lambda: now[0])
    p.operations_note(True)
    assert p.health()['status'] == 'healthy'
    now[0] += 61
    h = p.health()
    assert h['status'] == 'unavailable'
    assert h['probe_evidence_fresh'] is False
    assert h['production_ready'] is False


def test_monitor_thread_does_not_borrow_interactive_admin():
    p = locked_platform()
    p.security.authenticate('root')
    failures = []
    def run():
        try:
            p._monitor_tick()
        except AccessDenied:
            failures.append('blocked')
    thread = threading.Thread(target=run)
    thread.start()
    thread.join(2)
    assert not thread.is_alive() and failures == ['blocked']


def test_rejected_probe_sample_is_not_counted():
    ops = Operations()
    with pytest.raises(TypeError):
        ops.note_probe('healthy')
    assert ops.probes == 0 and ops.availability() is None


def test_rest_entity_cannot_downgrade_origin_scheme():
    from dataclasses import replace
    from toe.unified.catalog import CATALOG
    from toe.unified.connectors import ConnectorError, RestDriver
    spec = replace(next(s for s in CATALOG if s.protocol == 'rest'),
                   entities=('http://api.vendor.example/steal',))
    with pytest.raises(ConnectorError, match='outside base_url'):
        RestDriver().extract(spec, {'base_url': 'https://api.vendor.example', 'token': 'test'},
                             spec.entities[0], 'batch')


def test_redirect_does_not_send_bearer_to_foreign_origin():
    from dataclasses import replace
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from toe.unified.catalog import CATALOG
    from toe.unified.connectors import ConnectorError, RestDriver
    foreign_requests = []
    class Foreign(BaseHTTPRequestHandler):
        def do_GET(self):
            foreign_requests.append(self.headers.get('Authorization'))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'[]')
        def log_message(self, *args):
            pass
    foreign = ThreadingHTTPServer(('127.0.0.1', 0), Foreign)
    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header('Location', f'http://127.0.0.1:{foreign.server_port}/steal')
            self.end_headers()
        def log_message(self, *args):
            pass
    origin = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (foreign, origin)]
    for thread in threads:
        thread.start()
    try:
        spec = replace(next(s for s in CATALOG if s.protocol == 'rest'), entities=('entity',))
        with pytest.raises(ConnectorError, match='outside base_url origin'):
            RestDriver().extract(spec, {'base_url': f'http://127.0.0.1:{origin.server_port}',
                                       'token': 'test-only-not-a-secret'}, 'entity', 'batch')
        assert foreign_requests == []
    finally:
        for server in (origin, foreign):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(2)


def test_atomic_import_never_exposes_active_quarantined_rows(monkeypatch):
    p = UnifiedAnalyticsPlatform()
    entered, proceed, reading = threading.Event(), threading.Event(), threading.Event()
    real_quarantine = UnifiedDataLayer.quarantine_payloads
    def hold_before_quarantine(layer, rows):
        entered.set()
        assert proceed.wait(5)
        return real_quarantine(layer, rows)
    monkeypatch.setattr(UnifiedDataLayer, 'quarantine_payloads', hold_before_quarantine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        importing = pool.submit(p.import_records, [
            {'source': 's', 'entity': 'e', 'payload': {'id': 1}, 'quarantined': True},
        ])
        try:
            assert entered.wait(5)
            def read():
                reading.set()
                return p.export_records()
            observation = pool.submit(read)
            assert reading.wait(5)
            with pytest.raises(TimeoutError):
                observation.result(timeout=0.05)
        finally:
            proceed.set()
        importing.result(timeout=5)
        assert all(row['quarantined'] for row in observation.result(timeout=5))


@pytest.mark.parametrize('payload', [{'x': float('inf')}, {'x': object()}, {1: 'integer-key'},
                                    {'nested': {False: 'key'}}, {'tuple': (1, 2)}])
def test_lossy_or_non_json_payloads_are_rejected_atomically(payload):
    layer = UnifiedDataLayer()
    with pytest.raises((TypeError, ValueError)):
        layer.ingest('s', 'e', [{'id': 1}, payload], **OP)
    assert layer.snapshot() == [] and layer.audit == []


def test_production_start_and_readiness_fail_closed():
    from toe.unified.platform import GateUnavailable
    p = UnifiedAnalyticsPlatform()
    with pytest.raises(GateUnavailable):
        p.start(production=True)
    assert p.started is False
    assert p.readiness()['ready'] is False
    assert p.readiness()['status'] == 'blocked'


def test_policies_do_not_alias_store():
    from toe.unified.data_layer import Policy
    layer = UnifiedDataLayer()
    policy = Policy('e', 'restricted', 30, 'owner')
    published = layer.set_policy(policy)
    policy.classification = 'public'
    published.classification = 'public'
    layer.policy_for('e').classification = 'public'
    assert layer.policy_for('e').classification == 'restricted'


def test_checkpoint_preserves_governance_and_audit(tmp_path):
    from toe.unified.checkpoint import save_checkpoint, load_checkpoint
    from toe.unified.data_layer import Policy
    layer = UnifiedDataLayer()
    layer.set_policy(Policy('e', 'restricted', 30, 'owner'))
    layer.ingest('s', 'e', [{'id': 1}], **OP)
    path = tmp_path / 'checkpoint.json'
    save_checkpoint(layer, path)
    recovered = load_checkpoint(path)
    assert recovered.audit == layer.audit
    assert recovered.policy_for('e') == layer.policy_for('e')
    assert recovered.snapshot() == layer.snapshot()


def test_legacy_evaluation_flag_cannot_bypass_validation():
    registry = ModelRegistry()
    registry.train('m', rows(), ['x'], 'y')
    with pytest.raises(ValueError, match='held-out'):
        registry.retrain('m', rows(20), require_evaluation=False)
    assert registry.get('m').version == 1


def test_per_call_floor_cannot_weaken_registry_floor():
    registry = ModelRegistry(accuracy_floor=1.0)
    registry.train('m', rows(), ['x'], 'y')
    evaluation = [{'x': i + 0.25, 'y': i % 2} for i in range(12)]
    result = registry.retrain('m', rows(), evaluation, min_accuracy=0.0)
    assert not result.replaced and result.reason == 'candidate_below_accuracy_floor'


def test_bulk_quarantine_validates_all_payloads_before_mutating():
    layer = UnifiedDataLayer()
    layer.ingest('s', 'e', [{'id': 1}], **OP)
    with pytest.raises(ValueError):
        layer.quarantine_payloads([('s', 'e', {'id': 1}), ('s', 'e', {'id': float('nan')})])
    assert layer.snapshot()[0]['quarantined'] is False


def test_mutated_invalid_policy_cannot_be_published():
    from toe.unified.data_layer import Policy
    layer = UnifiedDataLayer()
    policy = Policy('e', 'restricted', 30, 'owner')
    policy.max_null_rate = -1
    with pytest.raises(ValueError):
        layer.set_policy(policy)
    assert layer.audit == []
