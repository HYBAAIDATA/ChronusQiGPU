"""Phase 1 reference runtime: exactness, proof, and coverage tests.

Every assertion is a falsifiable property, not a smoke test. Identity
checks run over ranges so a regression at a specific index is caught rather
than a lucky sample passing.
"""

import sys
import tempfile
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mla1517_platform_v3.4" / "python"))

# NB: mla1517.core also exports a `cassini()` FUNCTION, so importing
# `from mla1517 import cassini` binds whichever name won the package
# namespace. Import the module explicitly to avoid that collision.
import mla1517.cassini as cassini_mod  # noqa: E402
from mla1517 import binet_view, constants, fibonacci_store as fs  # noqa: E402
from mla1517 import lucas_scale, m32_geometry, pisot_fold, prime_address, query  # noqa: E402
from mla1517 import zeckendorf_codec as zc  # noqa: E402
from mla1517.prime_db import PrimeDB, VerificationError  # noqa: E402
from mla1517.state import MLA1517State, LogicalState, descriptor_size  # noqa: E402

# === exact Fibonacci / Lucas ===============================================


def test_fibonacci_and_lucas_are_exact():
    assert fs.fib(15) == 610
    assert fs.lucas(15) == 1364
    assert fs.fib(17) == 1597
    assert fs.lucas(17) == 3571


def test_fast_doubling_matches_recurrence():
    a, b = 0, 1
    for n in range(300):
        assert fs.fib_pair(n) == (a, b)
        a, b = b, a + b


def test_negative_index_refused():
    with pytest.raises(ValueError):
        fs.fib(-1)


# === Cassini identities ====================================================


def test_cassini_lucas_form_over_range():
    v = cassini_mod.verify_range(200)
    assert v["passed"], v["failures"][:3]


def test_cassini_all_four_identities_over_long_range():
    v = cassini_mod.verify_range(1000)
    assert v["passed"], v["failures"][:3]


def test_q_matrix_trace_equals_lucas():
    for n in range(200):
        assert cassini_mod.q_matrix_trace(n) == fs.lucas(n)


def test_q_matrix_determinant_is_signed_one():
    for n in range(100):
        assert cassini_mod.q_matrix_determinant(n) == constants.cassini_seal(n)


def test_corrupted_state_fails_its_seal():
    assert fs.is_valid_fib_state(*fs.fib_pair(30)) is True
    assert fs.is_valid_fib_state(999, 1000) is False


# === Zeckendorf ============================================================


def test_zeckendorf_is_a_bijection_up_to_999():
    for n in range(1, 1000):
        idx = zc.encode(n)
        assert zc.decode(idx) == n
        for a, b in zip(idx, idx[1:]):
            assert b - a >= 2


def test_zeckendorf_mask_roundtrip():
    for n in range(1, 500):
        assert zc.from_mask(zc.to_mask(n)) == n


def test_adjacent_mask_is_refused_not_normalised():
    with pytest.raises(zc.ZeckendorfError):
        zc.from_mask(0b11)


# === Binet view ============================================================


def test_binet_residual_decays_with_n():
    """Pisot behaviour: the conjugate term vanishes, so the residual shrinks."""
    late = abs(float(binet_view.binet_exact(79).residual))
    early = abs(float(binet_view.binet_exact(15).residual))
    assert late < early


def test_binet_reports_exact_value_and_residual():
    v = binet_view.binet_exact(50)
    assert v.exact == fs.fib(50)


# === Pisot fold ============================================================


def test_lossless_fold_roundtrips():
    r = pisot_fold.pisot_fold(50)
    assert pisot_fold.is_lossless(r.folded)
    assert pisot_fold.pisot_unfold(r.folded) == r.folded.exact_value


def test_non_lossless_fold_refuses_to_unfold():
    r = pisot_fold.pisot_fold(50, lossless=False)
    with pytest.raises(ValueError):
        pisot_fold.pisot_unfold(r.folded)


# === Lucas scale ===========================================================


def test_first_declared_transition_15_to_17_is_accepted():
    t = lucas_scale.authorise(15, 17)
    assert t.accepted
    assert t.reason is None
    assert t.lucas_source == 1364 and t.lucas_target == 3571
    assert t.lucas_ratio == Fraction(3571, 1364)


def test_off_ladder_scale_is_refused():
    assert lucas_scale.authorise(15, 99).reason == "family_not_allowed"
    assert lucas_scale.authorise(15, 0).reason == "index_out_of_bounds"


def test_climb_stays_at_the_top():
    assert lucas_scale.climb(10) == 12
    assert lucas_scale.climb(79) == 79


# === M32 geometry ==========================================================


def test_m32_topology_is_32_nodes_connected():
    top = m32_geometry.build_topology()
    assert top.nodes == 32
    assert top.execution_nodes == 12 and top.memory_nodes == 20
    assert top.connected is True
    assert top.edges > 0


def test_laplacian_gap_is_positive():
    assert m32_geometry.laplacian_gap(m32_geometry.build_topology()) > 0


def test_gap_is_named_as_a_graph_metric_not_energy():
    s = m32_geometry.spectral_gap(m32_geometry.build_topology())
    assert s["is_binding_energy"] is False
    assert s["physical_quantity"] is False
    assert s["positive"] is True


def test_partitions_are_disjoint_and_complete():
    parts = m32_geometry.route_partitions(32)
    flat = [n for p in parts for n in p]
    assert len(flat) == len(set(flat))
    assert len(parts) == 32


# === prime addressing ======================================================


# === 11D state and 64-byte ABI ============================================


def test_descriptor_is_exactly_64_bytes():
    assert descriptor_size() == constants.STATE_BYTES == 64


def test_descriptor_matches_the_native_abi():
    from mla1517.primedb_engine import MLA1517State as Native

    assert [f[0] for f in MLA1517State._fields_] == [f[0] for f in Native._fields_]


def test_state_digest_is_stable_with_signed_seal():
    s = LogicalState(
        index=17,
        lucas_scale=15,
        zeckendorf_mask=5,
        prime_address=59,
        site=27,
        cassini_seal=-1,
        version=1,
        payload=b"x",
    )
    assert s.digest() == s.digest()
    assert len(s.digest()) == 64


def test_site_routing_is_bounded():
    from mla1517.state import m32_site_for

    assert 0 <= m32_site_for(59) < 32


# === PRIME-DB ==============================================================


def test_put_and_get_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        db = PrimeDB(td)
        for i in range(1, 25):
            db.put(f"o{i}", i, scale=15, payload=f"p{i}".encode())
        assert len(db) == 24
        assert db.verify_all()["passed"]
        assert db.get("o17").state.cassini_seal == constants.cassini_seal(17)


def test_duplicate_write_is_idempotent():
    with tempfile.TemporaryDirectory() as td:
        db = PrimeDB(td)
        db.put("o", 5, payload=b"a")
        first = db.lineage("o")
        db.put("o", 5, payload=b"a")
        assert db.lineage("o") == first


def test_lineage_is_append_only():
    with tempfile.TemporaryDirectory() as td:
        db = PrimeDB(td)
        db.put("o", 5, payload=b"a")
        n1 = len(db.lineage("o"))
        db.put("o", 6, payload=b"b")
        assert len(db.lineage("o")) == n1 + 1


def test_corrupted_state_is_quarantined_not_returned():
    with tempfile.TemporaryDirectory() as td:
        db = PrimeDB(td)
        db.put("o", 5, payload=b"a")
        obj = db._objects["o"]
        tampered = LogicalState(
            index=5,
            lucas_scale=15,
            zeckendorf_mask=9,
            prime_address=11,
            site=11,
            cassini_seal=1,
            version=1,
            payload=b"TAMPERED",
        )
        db._objects["o"] = type(obj)("o", obj.digest, tampered, obj.lineage, True)
        with pytest.raises(VerificationError):
            db.get("o")
        assert "o" in db.quarantine()


def test_replay_rebuilds_from_journal():
    with tempfile.TemporaryDirectory() as td:
        db = PrimeDB(td)
        for i in range(1, 10):
            db.put(f"o{i}", i, payload=b"x")
        assert PrimeDB(td).replay() == 9


# === query ================================================================


def test_resonance_query_is_a_bounded_scan():
    with tempfile.TemporaryDirectory() as td:
        db = PrimeDB(td)
        for i in range(1, 25):
            db.put(f"o{i}", i, payload=b"x")
        r = query.query(db, "d5_resonance", d5_mask=1)
        assert r.supported
        assert "O(n)" in r.complexity
        assert r.scanned == len(db)


def test_unsupported_predicate_fails_at_plan_time():
    with tempfile.TemporaryDirectory() as td:
        r = query.query(PrimeDB(td), "no_such_predicate")
        assert r.supported is False
        assert r.matches == []


def test_prime_addressing_is_a_location_scheme_not_capacity():
    b = prime_address.address_capacity_boundary()
    # The claim is the leading token; the sentence carries its rationale.
    assert b["physical_capacity_gain"].startswith("NOT CLAIMED")
    assert "many-to-one" in b["injectivity"]
    # The store-level boundary is where the reference/native split lives.
    from mla1517.prime_db import CAPACITY_BOUNDARY

    assert CAPACITY_BOUNDARY["reference_implementation"] is True
    assert CAPACITY_BOUNDARY["native_library_present"] is False


def test_primes_are_exact_and_ordered():
    vals = [prime_address.prime_at(i) for i in range(10)]
    assert vals == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    assert prime_address.prime_index_of(29) == 9


def test_prime_gap_is_positive():
    assert prime_address.prime_gap(0) == 1
    assert prime_address.prime_gap(10) > 0
