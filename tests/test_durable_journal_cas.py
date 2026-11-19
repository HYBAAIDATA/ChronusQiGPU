"""Journal compare-and-swap and incremental-read integration tests using local SQLite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from chronus.storage.durable import CustodyConflictError, DurableTheseusService

pytestmark = pytest.mark.real


@pytest.fixture
def custody(tmp_path):
    return DurableTheseusService(str(tmp_path / 'custody.sqlite3'))


@pytest.mark.parametrize('bad', [-2, True, False, 0.0, '0'])
def test_invalid_expected_sequence_does_not_append(custody, bad):
    with pytest.raises(ValueError, match='expected_last_sequence'):
        custody.append_journal_event('t', 'TEST', b'payload', expected_last_sequence=bad)
    assert custody.get_journal('t') == []


def test_stale_claim_leaves_chain_unchanged_and_can_retry(custody):
    first = custody.append_journal_event('t', 'FIRST', b'one', expected_last_sequence=-1)
    for stale in (-1, 1, 100):
        with pytest.raises(CustodyConflictError, match='journal tip moved'):
            custody.append_journal_event('t', 'STALE', b'two', expected_last_sequence=stale)
        assert custody.get_journal('t') == [first]
    second = custody.append_journal_event('t', 'SECOND', b'two', expected_last_sequence=0)
    assert second.sequence == 1
    assert second.prev_entry_hash == first.entry_hash
    reopened = DurableTheseusService(custody.path)
    assert reopened.get_journal('t') == [first, second]
    assert reopened.reconstruct('t', second.object_id) == b'two'


def test_incremental_reads_are_exclusive_ordered_and_tenant_scoped(custody):
    entries = []
    for i in range(3):
        entries.append(custody.append_journal_event('a', 'TEST', str(i).encode(), expected_last_sequence=i - 1))
        custody.append_journal_event('b', 'OTHER', b'other')
    for after, expected in [(-1, entries), (0, entries[1:]), (1, entries[2:]), (2, []), (99, [])]:
        assert custody.get_journal('a', after_sequence=after) == expected
    assert custody.get_journal('missing', after_sequence=-1) == []
    assert [entry.sequence for entry in custody.get_journal('b')] == [0, 1, 2]


def test_two_connections_claiming_empty_tip_have_exactly_one_winner(custody):
    other = DurableTheseusService(custody.path)
    barrier = Barrier(2)

    def claim(service):
        barrier.wait(timeout=5)
        try:
            return service.append_journal_event('t', 'CLAIM', b'payload', expected_last_sequence=-1)
        except CustodyConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, [custody, other]))
    winners = [entry for entry in results if entry is not None]
    assert len(winners) == 1
    assert custody.get_journal('t') == winners
    assert winners[0].sequence == 0


def test_cas_tips_are_independent_per_tenant_even_for_identical_payloads(custody):
    a0 = custody.append_journal_event('a', 'TEST', b'same', expected_last_sequence=-1)
    b0 = custody.append_journal_event('b', 'TEST', b'same', expected_last_sequence=-1)
    a1 = custody.append_journal_event('a', 'TEST', b'same', expected_last_sequence=0)
    with pytest.raises(CustodyConflictError):
        custody.append_journal_event('a', 'TEST', b'same', expected_last_sequence=0)
    b1 = custody.append_journal_event('b', 'TEST', b'same', expected_last_sequence=0)
    assert custody.get_journal('a') == [a0, a1]
    assert custody.get_journal('b') == [b0, b1]
    assert a1.prev_entry_hash == a0.entry_hash
    assert b1.prev_entry_hash == b0.entry_hash
    assert custody.reconstruct('a', a1.object_id) == b'same'
    assert custody.reconstruct('b', b1.object_id) == b'same'
