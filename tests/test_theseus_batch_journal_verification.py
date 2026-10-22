"""Batched journal membership must never cache away physical or tenant checks."""
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from aethel.storage_topology import TheseusPhysicalStore, StorageTopologyError


def prepared(tmp_path):
    store = TheseusPhysicalStore(tmp_path)
    payload = b'authentic mathematical storage payload'
    address = store.commit(payload, tenant_id='tenant-a', scope='test')
    return store, address, payload


def test_journal_is_opened_once_and_each_replica_still_checked(tmp_path):
    store, address, payload = prepared(tmp_path)
    original = Path.open
    opens = []
    journal = store.journal_path('tenant-a')
    def observed(path, *args, **kw):
        if path == journal:
            opens.append(str(path))
        return original(path, *args, **kw)
    with patch.object(Path, 'open', observed):
        with store.verification_batch('tenant-a') as verify:
            for _ in range(10):
                assert verify(address, payload)
            store.replica_path(address).write_bytes(b'corrupt')
            assert not verify(address, payload)
    assert len(opens) == 1
    with pytest.raises(StorageTopologyError, match='closed'):
        verify(address, payload)


def test_append_or_same_size_edit_invalidates_current_snapshot(tmp_path):
    store, address, payload = prepared(tmp_path)
    journal = store.journal_path('tenant-a')
    before = journal.stat()
    with pytest.raises(StorageTopologyError, match='changed'):
        with store.verification_batch('tenant-a') as verify:
            assert verify(address, payload)
            data = journal.read_bytes()
            journal.write_bytes(data.replace(b'COMMITTED', b'FORBIDDEN'))
            os.utime(journal, ns=(before.st_atime_ns, before.st_mtime_ns))
            verify(address, payload)
    # A fresh pass reads current journal state, not the former membership.
    with store.verification_batch('tenant-a') as verify:
        assert not verify(address, payload)


def test_change_after_last_object_invalidates_entire_pass(tmp_path):
    store, address, payload = prepared(tmp_path)
    with pytest.raises(StorageTopologyError, match='changed'):
        with store.verification_batch('tenant-a') as verify:
            assert verify(address, payload)
            with store.journal_path('tenant-a').open('a') as stream:
                stream.write('{}\n')


def test_tenant_isolation_and_corrupt_journal_fail_closed(tmp_path):
    store, address, payload = prepared(tmp_path)
    with store.verification_batch('tenant-b') as verify:
        assert not verify(address, payload)
    with store.journal_path('tenant-a').open('a') as stream:
        stream.write('not-json\n')
    with pytest.raises(StorageTopologyError, match='batch replay'):
        with store.verification_batch('tenant-a'):
            pass
