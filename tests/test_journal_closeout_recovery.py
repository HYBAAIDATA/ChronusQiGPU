"""Scoped real-journal regression; not a substitute for installed custody tests.

Loads the stdlib-only journal source directly, without importing unavailable
repository package initialisers. The reported evidence must retain this scope.
"""
from __future__ import annotations
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import threading
import time
import pytest

JOURNAL_PATH = Path(__file__).resolve().parents[1] / 'aethel/enterprise/journal.py'

def load_journal():
    spec = importlib.util.spec_from_file_location('closeout_real_journal', JOURNAL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def mod():
    return load_journal()

@pytest.fixture
def wal(tmp_path, mod):
    return mod.WriteAheadJournal(tmp_path/'wal.jsonl')

def txn(j, op_id, **extra):
    j.append_intent({'op_id':op_id, 'op':'put', 'record_id':op_id, **extra})
    j.seal(op_id, {'record_id':op_id})

def sealed_ids(j):
    return [r['op_id'] for r in j.recover()]

def test_valid_history_does_not_rewrite(wal):
    txn(wal, 'one'); before=wal.path.read_bytes()
    assert sealed_ids(wal)==['one']
    assert wal.path.read_bytes()==before
    assert not list(wal.path.parent.glob('*.repair-*.bin'))

def test_tail_without_pending_is_repaired_and_second_restart_sees_append(wal, mod):
    txn(wal,'one'); original=wal.path.read_bytes()+b'{"op_id":'
    wal.path.write_bytes(original)
    assert sealed_ids(wal)==['one']
    evidence=list(wal.path.parent.glob('*.repair-*.bin'))
    assert len(evidence)==1 and evidence[0].read_bytes()==original
    txn(wal,'two')
    assert sealed_ids(mod.WriteAheadJournal(wal.path))==['one','two']

def test_dangling_intent_is_removed_without_dropping_other_commit(wal):
    wal.append_intent({'op_id':'dangling'})
    txn(wal,'kept')
    original=wal.path.read_bytes()
    assert sealed_ids(wal)==['kept']
    assert b'dangling' not in wal.path.read_bytes()
    assert next(wal.path.parent.glob('*.repair-*.bin')).read_bytes()==original
    txn(wal,'next'); assert sealed_ids(wal)==['kept','next']

def test_complete_final_row_without_newline_is_normalised(wal):
    txn(wal,'one'); original=wal.path.read_bytes().rstrip(b'\n'); wal.path.write_bytes(original)
    assert sealed_ids(wal)==['one']; assert wal.path.read_bytes().endswith(b'\n')
    txn(wal,'two'); assert sealed_ids(wal)==['one','two']

def test_append_refuses_unrecovered_partial_tail(wal, mod):
    wal.path.write_bytes(b'{"op_id":')
    with pytest.raises(mod.JournalCorruptionError): wal.append_intent({'op_id':'new'})
    assert wal.path.read_bytes()==b'{"op_id":'

def test_malformed_interior_refuses_without_rewrite(wal, mod):
    txn(wal,'one'); raw=wal.path.read_bytes()+b'broken\n'+b'{"op_id":"two","status":"intent"}\n'; wal.path.write_bytes(raw)
    with pytest.raises(mod.JournalCorruptionError): wal.recover()
    assert wal.path.read_bytes()==raw

@pytest.mark.parametrize('row',[
 [], {'op_id':'x','status':'unknown'}, {'op_id':4,'status':'intent'},
 {'op_id':'','status':'intent'}, {'op_id':'x','status':[]},
 {'op_id':'x','status':'intent','ts':True}, {'op_id':'x','status':'intent','ts':float('nan')},
])
def test_invalid_schema_refuses_without_rewrite(wal, mod, row):
    raw=(json.dumps(row)+'\n').encode(); wal.path.write_bytes(raw)
    with pytest.raises(mod.JournalCorruptionError): wal.recover()
    assert wal.path.read_bytes()==raw

def test_duplicate_json_keys_are_not_last_value_wins(wal, mod):
    raw=b'{"op_id":"one","op_id":"two","status":"intent"}\n'; wal.path.write_bytes(raw)
    with pytest.raises(mod.JournalCorruptionError): wal.recover()
    assert wal.path.read_bytes()==raw

def test_orphan_seal_cannot_invent_commit(wal, mod):
    raw=b'{"op_id":"orphan","status":"sealed"}\n'; wal.path.write_bytes(raw)
    with pytest.raises(mod.JournalCorruptionError): wal.recover()
    assert wal.path.read_bytes()==raw

def test_duplicate_intent_id_is_ambiguous(wal, mod):
    wal.append_intent({'op_id':'same'}); wal.append_intent({'op_id':'same'})
    raw=wal.path.read_bytes()
    with pytest.raises(mod.JournalCorruptionError): wal.recover()
    assert wal.path.read_bytes()==raw

def test_mismatched_seal_binding_refuses(wal, mod):
    wal.append_intent({'op_id':'one','record_id':'A'}); wal.seal('one', {'record_id':'B'})
    raw=wal.path.read_bytes()
    with pytest.raises(mod.JournalCorruptionError): wal.recover()
    assert wal.path.read_bytes()==raw

@pytest.mark.parametrize('field',['op_id','status','ts'])
def test_seal_extras_cannot_override_reserved_fields(wal, mod, field):
    with pytest.raises(mod.JournalCorruptionError): wal.seal('one',{field:'forged'})
    assert wal.path.read_bytes()==b''

def test_append_intent_rejects_sealed_status(wal, mod):
    with pytest.raises(mod.JournalCorruptionError): wal.append_intent({'op_id':'one','status':'sealed'})

@pytest.mark.parametrize('kind',['bytes','rows','line'])
def test_read_budgets_fail_without_repair(tmp_path, mod, kind):
    p=tmp_path/'wal.jsonl'; txn(mod.WriteAheadJournal(p),'one'); raw=p.read_bytes()
    opts={'bytes':{'max_journal_bytes':len(raw)-1},'rows':{'max_rows':1},'line':{'max_row_bytes':4}}[kind]
    with pytest.raises(mod.JournalLimitError): mod.WriteAheadJournal(p,**opts).recover()
    assert p.read_bytes()==raw

def test_append_size_limit_is_fail_closed(tmp_path, mod):
    j=mod.WriteAheadJournal(tmp_path/'wal.jsonl', max_row_bytes=16)
    with pytest.raises(mod.JournalLimitError): j.append_intent({'op_id':'too-large'})
    assert j.path.read_bytes()==b''

def test_atomic_replace_failure_preserves_original_and_evidence(wal, mod, monkeypatch):
    txn(wal,'one'); raw=wal.path.read_bytes()+b'{"x":'; wal.path.write_bytes(raw)
    def fail(*args): raise OSError('injected rename failure')
    with monkeypatch.context() as m:
        m.setattr(mod.os,'replace', fail)
        with pytest.raises(OSError): wal.recover()
    assert wal.path.read_bytes()==raw
    assert next(wal.path.parent.glob('*.repair-*.bin')).read_bytes()==raw
    assert sealed_ids(wal)==['one']
    assert not [p for p in wal.path.parent.glob('wal.jsonl.repair-*') if p.suffix!='.bin']

def test_evidence_failure_never_rewrites_journal(wal, mod, monkeypatch):
    txn(wal,'one'); raw=wal.path.read_bytes()+b'{'; wal.path.write_bytes(raw)
    def fail(path): raise OSError('injected fsync failure')
    monkeypatch.setattr(mod,'_fsync_directory',fail)
    with pytest.raises(OSError): wal.recover()
    assert wal.path.read_bytes()==raw

def test_iter_rows_is_snapshot_and_never_repairs(wal):
    txn(wal,'one'); raw=wal.path.read_bytes()+b'{'; wal.path.write_bytes(raw)
    assert len(list(wal.iter_rows()))==2
    assert wal.path.read_bytes()==raw
    assert not list(wal.path.parent.glob('*.repair-*.bin'))

def test_recover_holds_lock_across_parse_and_repair(wal, mod, monkeypatch):
    txn(wal,'one'); wal.append_intent({'op_id':'dangling'})
    entered=threading.Event(); release=threading.Event(); appended=threading.Event(); errors=[]
    original=mod.json.loads
    def blocked(*args, **kwargs):
        if threading.current_thread().name == 'closeout-recovery-reader' and not entered.is_set():
            entered.set()
            if not release.wait(5): raise RuntimeError('test barrier timed out')
        return original(*args, **kwargs)
    monkeypatch.setattr(mod.json, 'loads', blocked)
    def recover():
        try: wal.recover()
        except BaseException as e: errors.append(e)
    def append():
        try:
            peer=mod.WriteAheadJournal(wal.path); txn(peer,'two'); appended.set()
        except BaseException as e: errors.append(e)
    reader=threading.Thread(target=recover,name='closeout-recovery-reader'); reader.start(); assert entered.wait(5)
    writer=threading.Thread(target=append); writer.start()
    try: assert not appended.wait(.15)
    finally: release.set(); reader.join(5); writer.join(5)
    assert not reader.is_alive() and not writer.is_alive() and not errors and appended.is_set()
    monkeypatch.setattr(mod.json,'loads',original)
    assert sealed_ids(wal)==['one','two']


def test_filelock_reentrant_and_released_after_exception(tmp_path, mod):
    lock=mod.FileLock(tmp_path/'lock')
    with pytest.raises(RuntimeError):
        with lock:
            with lock: raise RuntimeError('injected')
    with lock:
        with lock: pass
    assert lock._depth==0 and lock._fh is None

def test_lock_acquire_setup_failure_does_not_leak_thread_lock(tmp_path, mod, monkeypatch):
    lock=mod.FileLock(tmp_path/'lock'); original=mod.Path.mkdir
    with monkeypatch.context() as m:
        def fail(*args,**kwargs): raise PermissionError('injected')
        m.setattr(mod.Path,'mkdir',fail)
        with pytest.raises(PermissionError): lock.acquire()
    assert lock._depth==0 and lock._fh is None
    with lock: pass

def process_writer(path, prefix):
    j=load_journal().WriteAheadJournal(path)
    coordination=load_journal().FileLock(Path(path).parent/'custody.lock')
    for i in range(10):
        with coordination: txn(j,f'{prefix}-{i}')

def test_concurrent_process_journal_append_and_recovery(wal):
    # Exercises WAL append/repair locking only, not whole-custody CAS/quota semantics.
    wal.append_intent({'op_id':'dangling'})
    ctx=multiprocessing.get_context('spawn')
    peers=[ctx.Process(target=process_writer,args=(str(wal.path),str(i))) for i in range(3)]
    for p in peers: p.start()
    try:
        coordination=load_journal().FileLock(wal.path.parent/'custody.lock')
        for _ in range(4):
            with coordination: wal.recover()
            time.sleep(.02)
        for p in peers: p.join(15)
        assert all(p.exitcode==0 for p in peers)
        ids=sealed_ids(wal); assert len(ids)==30 and len(set(ids))==30
        assert sealed_ids(load_journal().WriteAheadJournal(wal.path))==ids
    finally:
        for p in peers:
            if p.is_alive(): p.terminate(); p.join()

@pytest.mark.skipif(os.name=='nt',reason='symlink creation policy is host-specific on Windows')
def test_symlink_journal_rejected(tmp_path, mod):
    target=tmp_path/'target'; target.write_bytes(b'original'); path=tmp_path/'wal.jsonl'; path.symlink_to(target)
    with pytest.raises(mod.JournalCorruptionError): mod.WriteAheadJournal(path)
    assert target.read_bytes()==b'original'
