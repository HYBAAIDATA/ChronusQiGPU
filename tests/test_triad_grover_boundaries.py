"""Search termination and receipt boundaries on small, synthetic domains."""
from fractions import Fraction

import pytest

from chronus.kernels.gl2_transform import FoldedRegisterN
from chronus.ovid.folded_custody import OvidAdapter, OvidFoldedAdapter, TheseusAdapter, attest, verify_attested
from chronus.quantum.triad_grover import (
    EVENT_EXHAUSTED, EVENT_VERIFIED, decode_exact_fraction, encode_exact_fraction,
    exact_grover_two_amplitude_trajectory, run_triad_exact_grover_search,
)
from chronus.storage.durable import DurableTheseusService
from chronus.triad import open_production_triad

pytestmark = pytest.mark.real


@pytest.fixture
def adapter(tmp_path):
    return OvidFoldedAdapter(OvidAdapter(), TheseusAdapter(DurableTheseusService(str(tmp_path / 'custody.sqlite3')), 't'))


def test_empty_search_records_exhaustion_without_collapsing(adapter):
    handle = adapter.stage_domain('empty', FoldedRegisterN.from_domain_offset(100, num_generators=3))
    seen = []

    def reject(value):
        seen.append(value)
        return False

    result = run_triad_exact_grover_search(adapter=adapter, handle=handle, oracle_predicate=reject)
    assert sorted(seen) == list(range(100, 108))
    assert (result.found, result.marked_count, result.iterations, result.handle_version) == (False, 0, 0, 0)
    assert result.winner_value is result.winner_index is result.winner_schedule_position is None
    assert result.total_marked_probability == result.single_target_probability == 0
    assert result.oracle_evaluations == result.states_materialised == 8
    assert adapter.restore_from_theseus('empty') == handle
    receipts = adapter.theseus.journal_receipts([EVENT_EXHAUSTED, EVENT_VERIFIED])
    assert len(receipts) == 1 and receipts[0][0] == EVENT_EXHAUSTED
    assert decode_exact_fraction(verify_attested(receipts[0][1])['total_marked_probability']) == 0


def test_all_marked_uses_first_explicit_schedule_value_and_zero_iterations(adapter):
    handle = adapter.stage_domain('all', FoldedRegisterN.from_domain_offset(100, num_generators=2))
    verified = []

    def verify(value):
        verified.append(value)
        return True

    result = run_triad_exact_grover_search(adapter=adapter, handle=handle, oracle_predicate=lambda _: True,
                                          geodesic_order=[3, 1, 0, 2], winner_verifier=verify)
    assert (result.iterations, result.marked_count, result.winner_index, result.winner_value) == (0, 4, 3, 103)
    assert result.winner_schedule_position == 1
    assert result.total_marked_probability == 1
    assert result.single_target_probability == Fraction(1, 4)
    assert result.full_vector_checked
    assert verified == [103]
    assert adapter.restore_from_theseus('all').register.unfold_mk().readout_winner() == (3, (0, 103))


@pytest.mark.parametrize('N,M', [(True, 1), (4, False), (4.0, 1), (4, '1')])
def test_trajectory_requires_integer_counts(N, M):
    with pytest.raises(TypeError, match='integers'):
        exact_grover_two_amplitude_trajectory(N, M)


@pytest.mark.parametrize('N,M', [(0, 0), (-1, 1), (4, 0), (4, -1), (4, 5)])
def test_trajectory_rejects_impossible_counts(N, M):
    with pytest.raises(ValueError, match='require N'):
        exact_grover_two_amplitude_trajectory(N, M)


def test_majority_marked_stops_at_first_non_increase():
    # The documented contract selects the first peak, even if a later one is higher.
    assert exact_grover_two_amplitude_trajectory(8, 5) == [(0, Fraction(1), Fraction(1), Fraction(5, 8))]


@pytest.mark.parametrize('value', [Fraction(0), Fraction(-31, 17), Fraction(1), Fraction(1 << 15000, 3)])
def test_exact_fraction_signed_and_zero_roundtrip(value):
    assert decode_exact_fraction(encode_exact_fraction(value)) == value


@pytest.mark.parametrize('value', [0, 1.0, '1/2', None])
def test_fraction_encoder_rejects_inexact_input(value):
    with pytest.raises(TypeError, match='Fraction'):
        encode_exact_fraction(value)


@pytest.mark.parametrize('field', ['body_crc32c', 'body_sha256'])
def test_receipt_rejects_missing_integrity_field(field):
    receipt = attest({'artifact_id': 'test', 'nested': {'value': 1}})
    del receipt[field]
    with pytest.raises(ValueError, match='mismatch'):
        verify_attested(receipt)


@pytest.mark.parametrize('num_generators', [0, 25, True, 1.5])
def test_invalid_search_width_leaves_no_journal_artifact(tmp_path, num_generators):
    triad = open_production_triad(tmp_path)
    with pytest.raises(ValueError, match='num_generators'):
        triad.exact_grover_search('t', bytes(76), 0, 0, num_generators=num_generators)
    assert triad.theseus.get_journal('t') == []
