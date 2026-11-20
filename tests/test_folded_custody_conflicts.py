"""Version provenance and adapter cache isolation with local SQLite custody."""
import pytest

from chronus.kernels.gl2_transform import FoldedRegisterN
from chronus.ovid.folded_custody import OvidAdapter, OvidFoldedAdapter, TheseusAdapter
from chronus.storage.durable import DurableTheseusService

pytestmark = pytest.mark.real


@pytest.fixture
def adapters(tmp_path):
    path = str(tmp_path / 'custody.sqlite3')
    return tuple(
        OvidFoldedAdapter(OvidAdapter(), TheseusAdapter(DurableTheseusService(path), 't'))
        for _ in range(2)
    )


def test_cached_miss_is_refreshed_after_another_adapter_commits(adapters):
    writer, reader = adapters
    assert reader.theseus.latest_receipt('domain') is None
    with pytest.raises(KeyError):
        reader.restore_from_theseus('domain')
    staged = writer.stage_domain('domain', FoldedRegisterN.from_domain_offset(50, num_generators=3))
    assert reader.restore_from_theseus('domain') == staged
    collapsed = writer.commit_collapse_step(staged, 2, 1)
    assert reader.restore_from_theseus('domain') == collapsed


def test_identical_retry_is_idempotent_across_adapters(adapters):
    writer, reader = adapters
    register = FoldedRegisterN.from_domain_offset(50, num_generators=3)
    staged = writer.stage_domain('domain', register)
    collapsed = writer.commit_collapse_step(staged, 1, 1)
    before = writer.theseus.custody.get_journal('t')
    assert reader.stage_domain('domain', register) == staged
    assert reader.commit_collapse_step(staged, 1, 1) == collapsed
    assert writer.theseus.custody.get_journal('t') == before


def test_same_frame_with_different_collapse_provenance_is_a_conflict(adapters):
    writer, reader = adapters
    # Repeating either already resolved decision leaves the same wire frame,
    # but the version must still retain which generator was committed.
    register = FoldedRegisterN.from_domain_offset(5, num_generators=2, k=8)
    register = register.collapse_generator(0, 0).collapse_generator(1, 0)
    staged = writer.stage_domain('domain', register)
    chosen = writer.commit_collapse_step(staged, 0, 0)
    assert staged.register.collapse_generator(1, 0) == chosen.register
    before = writer.theseus.custody.get_journal('t')
    with pytest.raises(ValueError, match='already committed'):
        reader.commit_collapse_step(staged, 1, 0)
    assert writer.theseus.custody.get_journal('t') == before
    assert reader.restore_from_theseus('domain') == chosen


def test_returned_receipts_cannot_mutate_cached_committed_state(adapters):
    writer, reader = adapters
    staged = writer.stage_domain('domain', FoldedRegisterN.from_domain_offset(50, num_generators=2))
    receipt = reader.theseus.committed_receipt('domain', 0)
    original = dict(receipt)
    receipt['frame_sha256'] = 'tampered'
    receipt['version'] = 99
    assert reader.theseus.committed_receipt('domain', 0) == original
    latest = reader.theseus.latest_receipt('domain')
    latest['resolved_mask'] = 3
    assert reader.restore_from_theseus('domain') == staged


def test_tenants_can_use_the_same_artifact_id_without_sharing_versions(adapters):
    writer, _ = adapters
    other = OvidFoldedAdapter(
        OvidAdapter(), TheseusAdapter(DurableTheseusService(writer.theseus.custody.path), 'other'),
    )
    first = writer.stage_domain('domain', FoldedRegisterN.from_domain_offset(50, num_generators=2))
    second = other.stage_domain('domain', FoldedRegisterN.from_domain_offset(80, num_generators=2))
    writer.commit_collapse_step(first, 0, 1)
    assert other.restore_from_theseus('domain') == second
    assert other.materialise_indices(second, [0, 3]) == [80, 83]
