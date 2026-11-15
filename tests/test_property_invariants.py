"""Property-based invariant tests (Hypothesis).

Covers cross-cutting algebraic invariants:
- F_257 gate algebra (involutions, phases, CNOT)
- Rank-2 subspace iterate exactly matches dense statevector evolution
- Golden/metallic lane hashing bounds and determinism
- Nonce-range partitioning is a disjoint exact cover under both weightings
- Zeckendorf and binary traversal visit identical candidates
- 256-bit limb encoding roundtrips
- KMS Ed25519 sign/verify roundtrips and forgery resistance
- Theseus content-addressed store/reconstruct roundtrips
"""

import hashlib

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from chronus.backends.limbs import (
    LIMB_MASK,
    MAX_SIGNED_256,
    MIN_SIGNED_256,
    decode_int256,
    encode_int256,
)
from chronus.execution.mining import partition_nonce_range, search_nonce_range
from chronus.quantum.statevector import P, StateVector
from chronus.quantum.subspace import (
    subspace_iterate,
    uniform_subspace,
)
from chronus.storage.phyllotaxis import (
    GOLDEN_RATIO_CONJUGATE_64,
    PhyllotaxisMesh,
    golden_angle_hash,
    golden_lane,
    metallic_conjugate_64,
)

MAX_EXAMPLES = dict(max_examples=60, deadline=None)


def _field_elems(amp):
    return all(0 <= a < P for a in amp)


# ---------------------------------------------------------------------------
# F_257 statevector algebra
# ---------------------------------------------------------------------------

state_qubits = st.integers(min_value=1, max_value=5)
gate_names = st.sampled_from(["X", "Y", "Z", "H", "S", "T"])


@given(n=state_qubits, data=st.data())
@settings(**MAX_EXAMPLES)
def test_gate_application_preserves_field_membership(n, data):
    state = StateVector(n)
    ops = data.draw(st.lists(st.tuples(gate_names, st.integers(0, n - 1)), max_size=12))
    for gate, qubit in ops:
        state.apply(gate, qubit)
    assert len(state.amplitudes) == 1 << n
    assert _field_elems(state.amplitudes)


@given(n=state_qubits, qubit=st.data())
@settings(**MAX_EXAMPLES)
def test_involution_gates_square_to_identity(n, qubit):
    q = qubit.draw(st.integers(0, n - 1))
    for gate in ("X", "Z", "H", "Y"):
        state = StateVector(n)
        state.apply("H", 0)  # move off the trivial basis state
        before = list(state.amplitudes)
        state.apply(gate, q).apply(gate, q)
        assert state.amplitudes == before, f"{gate}^2 != I on qubit {q}"


@given(n=state_qubits, qubit=st.data())
@settings(**MAX_EXAMPLES)
def test_phase_gate_orders(n, qubit):
    q = qubit.draw(st.integers(0, n - 1))
    s = StateVector(n)
    for _ in range(4):
        s.apply("S", q)
    assert s.equivalent(StateVector(n)), "S^4 != I"
    t = StateVector(n)
    for _ in range(8):
        t.apply("T", q)
    assert t.equivalent(StateVector(n)), "T^8 != I"


@given(n=st.integers(min_value=2, max_value=5), data=st.data())
@settings(**MAX_EXAMPLES)
def test_cnot_is_involution_and_x_when_control_set(n, data):
    control = data.draw(st.integers(0, n - 1))
    target = data.draw(st.integers(0, n - 1).filter(lambda q: q != control))
    state = StateVector(n)
    # Randomize the state first
    for q in range(n):
        state.apply("H", q)
    before = list(state.amplitudes)
    state.cnot(control, target).cnot(control, target)
    assert state.amplitudes == before


@given(n=st.integers(min_value=2, max_value=4), data=st.data())
@settings(**MAX_EXAMPLES)
def test_cnot_flips_target_exactly_when_control_set(n, data):
    control = data.draw(st.integers(0, n - 1))
    target = data.draw(st.integers(0, n - 1).filter(lambda q: q != control))
    state = StateVector(n)
    state.apply("X", control)  # |...1...> on control
    before = list(state.amplitudes)
    state.cnot(control, target)
    cstride, tstride = 1 << control, 1 << target
    for index, amp in enumerate(before):
        expected_index = index
        if index & cstride:
            expected_index = index ^ tstride
        assert state.amplitudes[expected_index] == amp


def test_unknown_gate_and_bad_qubit_rejected():
    state = StateVector(2)
    with pytest.raises(ValueError):
        state.apply("NOPE", 0)
    with pytest.raises(ValueError):
        state.apply("X", 5)
    with pytest.raises(ValueError):
        state.cnot(0, 0)
    with pytest.raises(ValueError):
        StateVector(0)
    with pytest.raises(ValueError):
        StateVector(2, amplitudes=[1, 2, 3])


# ---------------------------------------------------------------------------
# Rank-2 subspace iterate == dense evolution (cross-implementation invariant)
# ---------------------------------------------------------------------------


@given(
    n=st.integers(min_value=1, max_value=6),
    marked_count=st.integers(min_value=1, max_value=31),
    alpha=st.integers(min_value=0, max_value=P - 1),
    beta=st.integers(min_value=0, max_value=P - 1),
)
@settings(**MAX_EXAMPLES)
def test_subspace_iterate_matches_dense_evolution(n, marked_count, alpha, beta):
    assume(marked_count < (1 << n))
    dense = StateVector(n)
    u = pow(30, n, P)  # uniform amplitude
    dense.amplitudes = [u] * (1 << n)
    marked_set = set(range(marked_count))

    # Dense: oracle multiplies marked amplitudes by alpha
    for m in marked_set:
        dense.amplitudes[m] = (alpha * dense.amplitudes[m]) % P
    # Dense: diffusion maps a -> (1+beta)*mean - beta*a
    mean = (sum(dense.amplitudes) * pow(1 << n, -1, P)) % P
    dense.amplitudes = [((1 + beta) * mean - beta * a) % P for a in dense.amplitudes]

    sub = subspace_iterate(uniform_subspace(n, marked_count), alpha, beta)
    for index, amp in enumerate(dense.amplitudes):
        expected = sub.marked_amplitude if index in marked_set else sub.unmarked_amplitude
        assert amp == expected


# ---------------------------------------------------------------------------
# Phyllotaxis / metallic hashing invariants
# ---------------------------------------------------------------------------


@given(digest=st.binary(min_size=1, max_size=64), lanes=st.integers(1, 4096))
@settings(**MAX_EXAMPLES)
def test_golden_lane_within_bounds(digest, lanes):
    lane = golden_lane(digest, lanes)
    assert 0 <= lane < lanes


@given(key=st.one_of(st.text(min_size=1, max_size=64), st.binary(min_size=1, max_size=64)))
@settings(**MAX_EXAMPLES)
def test_golden_angle_hash_deterministic_and_bounded(key):
    first = golden_angle_hash(key)
    second = golden_angle_hash(key)
    assert first == second
    assert 0 <= first < 1 << 64


@given(m=st.integers(min_value=1, max_value=12))
@settings(**MAX_EXAMPLES)
def test_metallic_conjugate_reproduces_golden_and_bounds(m):
    value = metallic_conjugate_64(m)
    assert 0 <= value < 1 << 64
    if m == 1:
        assert value == GOLDEN_RATIO_CONJUGATE_64


@given(key=st.text(min_size=1, max_size=48), lanes=st.integers(1, 128))
@settings(**MAX_EXAMPLES)
def test_mesh_map_key_pure_and_in_range(key, lanes):
    mesh = PhyllotaxisMesh(lanes=lanes)
    lane_a, coord_a = mesh.map_key(key)
    lane_b, coord_b = mesh.map_key(key)
    assert lane_a == lane_b and coord_a == coord_b
    assert 0 <= lane_a < lanes
    multi = mesh.map_key_multiscale(key, silver_lanes=8, bronze_lanes=4)
    assert 0 <= multi["silver_partition"] < 8
    assert 0 <= multi["bronze_route"] < 4


@given(lanes=st.one_of(st.integers(max_value=0), st.just(True)))
@settings(max_examples=10)
def test_mesh_rejects_invalid_lane_counts(lanes):
    with pytest.raises(ValueError):
        PhyllotaxisMesh(lanes=lanes)


def test_phyllotaxis_sequence_injectivity():
    """Golden-turn numerators are injective over sequences below the modulus."""
    from chronus.storage.phyllotaxis import phyllotaxis_coordinate

    digest = hashlib.sha256(b"x").digest()
    seen = {}
    for seq in range(500):
        coord = phyllotaxis_coordinate(seq, digest, 8)
        assert coord.golden_turns_numerator not in seen
        seen[coord.golden_turns_numerator] = seq


# ---------------------------------------------------------------------------
# Nonce-range partitioning: disjoint exact cover under both weightings
# ---------------------------------------------------------------------------


@given(
    start=st.integers(min_value=0, max_value=1 << 20),
    width=st.integers(min_value=0, max_value=1 << 16),
    weights=st.sampled_from(["uniform", "lucas"]),
)
@settings(**MAX_EXAMPLES)
def test_partition_is_disjoint_exact_cover(start, width, weights):
    stop = start + width
    lanes = partition_nonce_range(start, stop, weights=weights)
    assert len(lanes) == 32
    assert lanes[0][0] == start
    assert lanes[-1][1] == stop
    for (a0, a1), (b0, b1) in zip(lanes, lanes[1:]):
        assert a0 <= a1  # monotone
        assert a1 == b0  # contiguous, no gaps or overlaps


@given(start=st.integers(min_value=-5, max_value=-1))
@settings(max_examples=5)
def test_partition_rejects_negative_range(start):
    with pytest.raises(ValueError):
        partition_nonce_range(start, 10)
    with pytest.raises(ValueError):
        partition_nonce_range(0, 10, weights="bogus")


# ---------------------------------------------------------------------------
# Mining traversal: zeckendorf and binary agree exactly
# ---------------------------------------------------------------------------

_HEADER = bytes(range(80))


@given(start=st.integers(0, 5000), width=st.integers(1, 64))
@settings(max_examples=12, deadline=None)
def test_zeckendorf_traversal_matches_binary(start, width):
    stop = start + width
    target = (1 << 256) - 1  # permissive target: every candidate matches
    binary = search_nonce_range(
        _HEADER, start, stop, target, workers=1, step_order="binary"
    )
    zeck = search_nonce_range(
        _HEADER, start, stop, target, workers=1, step_order="zeckendorf"
    )
    assert binary["tested"] == zeck["tested"] == width
    assert binary["match_count"] == zeck["match_count"] == width
    assert binary["matches"] == zeck["matches"]


@given(width=st.integers(1, 32))
@settings(max_examples=8, deadline=None)
def test_unrolled_engine_matches_library(width):
    target = (1 << 256) - 1
    lib = search_nonce_range(_HEADER, 0, width, target, engine="library")
    unrolled = search_nonce_range(_HEADER, 0, width, target, engine="unrolled")
    assert lib["matches"] == unrolled["matches"]


def test_search_rejects_impossible_target_and_bad_header():
    with pytest.raises(ValueError):
        search_nonce_range(b"short", 0, 10, 1)
    with pytest.raises(ValueError):
        search_nonce_range(_HEADER, 0, 10, 1 << 256)
    with pytest.raises(ValueError):
        search_nonce_range(_HEADER, 5, 5, 1)
    with pytest.raises(ValueError):
        search_nonce_range(_HEADER, 0, 70000, 1)


def test_zero_target_finds_no_matches():
    result = search_nonce_range(_HEADER, 0, 8, 0, workers=1)
    # Only a hash of exactly zero could match; sha256d never returns 0 here.
    assert result["match_count"] == 0


# ---------------------------------------------------------------------------
# 256-bit limb encoding
# ---------------------------------------------------------------------------


@given(value=st.integers(min_value=MIN_SIGNED_256, max_value=MAX_SIGNED_256))
@settings(**MAX_EXAMPLES)
def test_limb_roundtrip(value):
    limbs = encode_int256(value)
    assert all(0 <= limb <= LIMB_MASK for limb in limbs)
    assert decode_int256(limbs) == value


@given(value=st.one_of(
    st.integers(max_value=MIN_SIGNED_256 - 1),
    st.integers(min_value=MAX_SIGNED_256 + 1),
))
@settings(max_examples=10)
def test_limb_encode_rejects_out_of_range(value):
    with pytest.raises(OverflowError):
        encode_int256(value)


def test_limb_encode_rejects_non_int():
    with pytest.raises(TypeError):
        encode_int256(True)
    with pytest.raises(TypeError):
        encode_int256("7")


def test_limb_decode_rejects_bad_limbs():
    with pytest.raises(ValueError):
        decode_int256((1, 2, 3))
    with pytest.raises(ValueError):
        decode_int256((1, 2, 3, 1 << 64))


# ---------------------------------------------------------------------------
# KMS sign/verify roundtrips and forgery resistance
# ---------------------------------------------------------------------------


@given(message=st.binary(max_size=512), key_id=st.text(min_size=1, max_size=32))
@settings(**MAX_EXAMPLES)
def test_ed25519_sign_verify_roundtrip(message, key_id):
    from chronus.security.kms import LocalMemoryKeyProvider

    provider = LocalMemoryKeyProvider()
    signature = provider.sign(key_id, message, "Ed25519")
    assert provider.verify(key_id, message, signature, "Ed25519") is True


@given(message=st.binary(min_size=1, max_size=256), data=st.data())
@settings(**MAX_EXAMPLES)
def test_ed25519_rejects_wrong_message(message, data):
    from chronus.security.kms import LocalMemoryKeyProvider

    provider = LocalMemoryKeyProvider()
    provider.register_ed25519_key("k1")
    signature = provider.sign("k1", message)
    other = data.draw(st.binary(min_size=1, max_size=256).filter(lambda m: m != message))
    assert provider.verify("k1", other, signature) is False


@given(message=st.binary(min_size=1, max_size=128))
@settings(max_examples=20, deadline=None)
def test_ed25519_signature_not_portable_across_keys(message):
    from chronus.security.kms import LocalMemoryKeyProvider

    provider = LocalMemoryKeyProvider()
    provider.register_ed25519_key("alice")
    provider.register_ed25519_key("bob")
    signature = provider.sign("alice", message)
    assert provider.verify("bob", message, signature) is False


def test_kms_unknown_algorithm_rejected():
    from chronus.security.kms import LocalMemoryKeyProvider

    provider = LocalMemoryKeyProvider()
    with pytest.raises(ValueError, match="Unsupported"):
        provider.sign("k", b"m", "ROT13")
    assert provider.verify("k", b"m", b"s", "ROT13") is False


# ---------------------------------------------------------------------------
# Theseus content-addressed storage roundtrips
# ---------------------------------------------------------------------------


@given(
    payload=st.binary(min_size=1, max_size=2048),
    tenant=st.text(min_size=1, max_size=24),
)
@settings(**MAX_EXAMPLES)
def test_theseus_store_reconstruct_roundtrip(payload, tenant):
    from chronus.security.ovid import OVIDStorage
    from chronus.storage.theseus import TheseusService

    svc = TheseusService(OVIDStorage(), lane_count=8)
    record = svc.store(tenant, payload)
    assert record.object_id == hashlib.sha256(payload).hexdigest()
    assert svc.reconstruct(tenant, record.object_id) == payload
    # Content addressing: storing the same payload twice is idempotent
    again = svc.store(tenant, payload)
    assert again.object_id == record.object_id
    assert svc.query(tenant) == [record.object_id]


@given(payload=st.binary(min_size=1, max_size=256))
@settings(max_examples=20)
def test_theseus_tenant_isolation(payload):
    from chronus.security.ovid import OVIDStorage
    from chronus.storage.theseus import TheseusService

    svc = TheseusService(OVIDStorage(), lane_count=8)
    record = svc.store("tenant-a", payload)
    assert svc.query("tenant-b") == []
    with pytest.raises(KeyError):
        svc.get_record("tenant-b", record.object_id)
    with pytest.raises(KeyError):
        svc.reconstruct("tenant-b", record.object_id)


@given(payload=st.binary(min_size=1, max_size=256), increment=st.integers(1, 100))
@settings(max_examples=20)
def test_theseus_scale_preserves_content_address(payload, increment):
    from chronus.security.ovid import OVIDStorage
    from chronus.storage.theseus import TheseusService

    svc = TheseusService(OVIDStorage(), lane_count=8)
    record = svc.store("tenant-a", payload)
    scaled = svc.scale_record("tenant-a", record.object_id, increment)
    assert scaled.object_id == record.object_id
    assert scaled.scale_index == record.scale_index + increment
    assert svc.reconstruct("tenant-a", scaled.object_id) == payload
