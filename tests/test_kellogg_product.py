"""Kellogg as a standalone product: specification registry, exact tensor
networks in custody, certificates, substrate, channels, surface code, 11D
vector, DMRG and the correctness benchmarks."""

from __future__ import annotations

import itertools
import random
from fractions import Fraction

import numpy as np
import pytest

from kellogg import exact_linalg as la
from kellogg.benchmark import BENCHMARKS, run
from kellogg.certificate import (
    CertificateError,
    aggregate,
    certificate_from_dict,
    certify,
    compose,
    merkle_proof,
    merkle_root,
    verify_certificate,
    verify_merkle_proof,
)
from kellogg.channels import (
    KrausChannel,
    PauliHamiltonian,
    amplitude_damping_half,
    dephasing_half,
    pauli_rotation,
    quantum_fisher_information,
    total_z_half,
)
from kellogg.custody import CustodyError, FoldStoreCustody, ResidentCustody
from kellogg.cyclotomic import I8, INV_SQRT2_8, ONE8, Q8, ZERO8, ZETA8_8
from kellogg.exact_network import ExactMPO, ExactMPS, ExactTensorTrain, ghz_circuit, ising_mpo
from kellogg.exact_tensor import GATES, F4, ExactStateVector, NotInF4
from kellogg.quantum_tensor import dual_frame_is_dual, lucas_bound
from kellogg.spec import REGISTRY, verify_registry
from kellogg.substrate import (
    QPhi,
    beta_expansion_value,
    cassini_step,
    lucas_cassini,
    lucas_wind,
    parry_admissible,
    phi_beta_expansion,
)
from kellogg.surface_code import PlanarSurfaceCode, edge_star_report
from kellogg.tensor_network import HeisenbergHamiltonianMPO, TensorTrain, tt_svd
from kellogg.vector11 import fold, fold_certificate, lift, unfold

HALF = Q8(1, 0, 0, 0, 2)


def R():
    return ResidentCustody()


# -- specification -------------------------------------------------------------


def test_registry_resolves_every_symbol_and_benchmark():
    report = verify_registry()
    assert report["ok"], report["problems"]
    assert report["items"] == len(REGISTRY) >= 80


def test_registry_never_marks_a_correction_without_its_text():
    for item in REGISTRY:
        if item.status in ("CORRECTED", "REFUTED", "RESEARCH"):
            assert item.note, item.id
        if item.status == "DELEGATED":
            assert item.owner != "kellogg", item.id


# -- fields ----------------------------------------------------------------------


def test_q8_equals_f4_bit_for_bit():
    rng = random.Random(1)

    def rf():
        return Fraction(rng.randint(-40, 40), rng.randint(1, 20))

    for _ in range(500):
        x, y = F4(rf(), rf(), rf(), rf()), F4(rf(), rf(), rf(), rf())
        a, b = Q8.from_f4(x), Q8.from_f4(y)
        assert (a * b).to_f4() == x * y
        assert (a + b).to_f4() == x + y
        if y != F4():
            assert (a / b).to_f4() == x / y


def test_exact_rank_factorization_is_lossless():
    rng = random.Random(2)
    for _ in range(20):
        r = rng.randint(1, 3)
        a = [[Q8(rng.randint(-3, 3), rng.randint(-1, 1)) for _ in range(r)] for _ in range(5)]
        b = [[Q8(rng.randint(-3, 3), 0, rng.randint(-1, 1)) for _ in range(6)] for _ in range(r)]
        m = la.matmul(a, b)
        c, f, piv = la.cr_factor(m)
        assert la.equal(la.matmul(c, f), m) and len(piv) <= r


# -- exact tensor network ------------------------------------------------------------


def test_ghz_is_exact_and_minimal():
    psi = ghz_circuit(12, custody=R())
    assert psi.bonds() == [1] + [2] * 11 + [1]
    assert psi.norm2() == ONE8
    assert psi.probability(5, 0) == HALF
    assert psi.cut_purity(5) == HALF
    assert all(len(set(psi.sample(s))) == 1 for s in range(4))
    assert psi.ledger.verify_chain()


def test_mps_matches_dense_exact_state_vector():
    rng = random.Random(5)
    n = 5
    sv = ExactStateVector.basis(n, 0)
    m = ExactMPS.zeros(n, custody=R())
    for _ in range(40):
        if rng.random() < 0.5:
            q, g = rng.randrange(n), rng.choice(["H", "S", "T", "X", "Z", "Tdg"])
            sv = sv.apply_single(q, GATES[g])
            m.apply_1q(q, g)
        else:
            c, t = rng.sample(range(n), 2)
            sv = sv.apply_cnot(c, t)
            m.cnot(c, t)
    # ExactStateVector indexes qubit 0 as the least significant bit; MPS site 0 is the first leg.
    dense = [Q8.from_f4(a) for a in sv.amplitudes]
    reorder = [int(format(i, f"0{n}b")[::-1], 2) for i in range(2**n)]
    assert m.to_dense() == [dense[reorder[i]] for i in range(2**n)]
    assert m.norm2() == ONE8


def test_identical_cores_share_one_custody_block():
    psi = ghz_circuit(400, custody=R())
    assert psi.unique_blocks() <= 3


def test_custody_is_the_only_storage_and_fails_closed():
    custody = R()
    psi = ExactMPS.zeros(6, custody=custody, window=2)
    psi.apply_1q(0, "H")
    psi.apply_2q(0, "CNOT")
    ref = psi.refs[3]
    for _ in range(custody.holds(ref)):
        custody.release(ref)
    psi._cache.clear()
    with pytest.raises(CustodyError):
        psi.core(3)


def test_trains_sharing_custody_keep_each_others_blocks():
    custody = R()
    a = ExactMPS.zeros(120, custody=custody, window=2)
    b = ExactMPS.zeros(120, custody=custody, window=2)
    b.apply_1q(7, "H")
    b.close()
    a._cache.clear()
    assert a.norm2() == ONE8
    assert custody.accounting()["resident_bytes"] > 0
    a.close()
    assert custody.accounting()["resident_bytes"] == 0


def test_aethel_fold_store_is_bound_by_protocol():
    aethel = pytest.importorskip("aethel.fold_store")
    custody = FoldStoreCustody(aethel.PersistentFoldStore(default_depth=2))
    psi = ghz_circuit(20, custody=custody)
    assert psi.norm2() == ONE8
    assert custody.accounting()["fold_blocks"] >= 3


def test_mpo_unitarity_and_hermiticity_are_decided_exactly():
    h = [[INV_SQRT2_8, INV_SQRT2_8], [INV_SQRT2_8, -INV_SQRT2_8]]
    assert ExactMPO.from_local([h] * 3, custody=R()).is_unitary()
    assert not ExactMPO.from_local([[[ONE8, ONE8], [ZERO8, ONE8]]] * 2, custody=R()).is_unitary()
    assert ising_mpo(4, custody=R()).is_hermitian()


def test_exact_tt_from_dense_roundtrip():
    rng = random.Random(9)
    vals = [Q8(rng.randint(-3, 3), rng.randint(-1, 1), rng.randint(-2, 2)) for _ in range(24)]
    tt = ExactTensorTrain.from_dense(vals, [2, 3, 4], custody=R())
    assert tt.to_dense() == vals


def test_voyage_amplitudes_carry_q_zeta8_phases():
    psi = ghz_circuit(30, custody=R())
    psi.apply_1q(0, "T")
    psi.apply_1q(29, "S")
    assert psi.entry([1] * 30) == ZETA8_8 * I8 * INV_SQRT2_8
    assert psi.entry([0] * 30) == INV_SQRT2_8


# -- certificates --------------------------------------------------------------------


def test_certificates_compose_only_when_boundaries_meet():
    a = certify("op", "Q(zeta8)", "m", "0" * 64, "1" * 64)
    b = certify("op", "Q(zeta8)", "m", "1" * 64, "2" * 64)
    c = compose(a, b)
    assert c.input_boundary == "0" * 64 and c.output_boundary == "2" * 64
    with pytest.raises(CertificateError):
        compose(b, a)
    with pytest.raises(CertificateError):
        certify("op", "Q(zeta8)", "m", "0" * 64, "1" * 64, {"x": 0.5})


def test_tampered_certificate_fails_and_aggregate_reports_it():
    a = certify("op", "Q", "m", "0" * 64, "1" * 64)
    forged = type(a)(**{**a.__dict__, "op": "other"})
    with pytest.raises(CertificateError):
        verify_certificate(forged)
    agg = aggregate([a, forged])
    assert agg.results == (True, False) and not agg.valid


def test_merkle_inclusion_proofs():
    leaves = [f"{i:064x}" for i in range(13)]
    root = merkle_root(leaves)
    for i in range(13):
        assert verify_merkle_proof(leaves[i], merkle_proof(leaves, i), root)


def test_certificate_json_is_strict_and_tamper_evident():
    cert = certify("strict", "Q", "software", "0" * 64, "1" * 64)
    row = cert.to_dict()
    assert certificate_from_dict(row) == cert

    changed_payload = dict(row)
    changed_payload["parameters"] = {"changed": True}
    with pytest.raises(CertificateError, match="digest mismatch"):
        certificate_from_dict(changed_payload)

    changed_parent = dict(row)
    changed_parent["input_boundary"] = "2" * 64
    with pytest.raises(CertificateError, match="digest mismatch"):
        certificate_from_dict(changed_parent)

    reordered = dict(reversed(list(row.items())))
    assert certificate_from_dict(reordered) == cert  # canonical order is semantic, not insertion order.

    unknown = dict(row)
    unknown["surprise"] = True
    with pytest.raises(CertificateError, match="unknown field"):
        certificate_from_dict(unknown)

    malformed = dict(row)
    malformed.pop("machine_type")
    with pytest.raises(CertificateError, match="missing field"):
        certificate_from_dict(malformed)


def test_merkle_verifier_rejects_changed_root_proof_and_invalid_side():
    leaves = [f"{i:064x}" for i in range(5)]
    proof = merkle_proof(leaves, 2)
    root = merkle_root(leaves)
    assert verify_merkle_proof(leaves[2], proof, root)
    assert not verify_merkle_proof(leaves[2], proof, "f" * 64)

    changed = list(proof)
    side, sibling = changed[0]
    changed[0] = (side, ("0" if sibling[0] != "0" else "1") + sibling[1:])
    assert not verify_merkle_proof(leaves[2], changed, root)

    invalid_side = list(proof)
    invalid_side[0] = ("X", invalid_side[0][1])
    with pytest.raises(CertificateError, match="invalid Merkle proof side"):
        verify_merkle_proof(leaves[2], invalid_side, root)


# -- substrate -------------------------------------------------------------------------


def test_substrate_identities_with_the_corrected_lucas_sign():
    assert all(lucas_wind(n) == [2, 1, 3, 4, 7, 11, 18][n] for n in range(7))
    assert all(cassini_step(n)["fibonacci_holds"] and cassini_step(n)["lucas_holds"] for n in range(1, 100))
    assert lucas_cassini(1) == 5 != 5 * (-1) ** 1
    assert lucas_bound(15)["trace_Mn"] == 1364


def test_beta_expansion_is_exact_and_admissible():
    for k in range(50):
        x = Fraction(k, 50)
        d, r = phi_beta_expansion(x, 25)
        assert parry_admissible(d) and beta_expansion_value(d, r) == QPhi(x)


def test_dual_frame_is_the_true_dual():
    assert dual_frame_is_dual()


# -- channels, Hamiltonians, Fisher ------------------------------------------------------


def test_kraus_rank_is_a_purification_dimension():
    composed = amplitude_damping_half().compose(dephasing_half())
    assert composed.is_trace_preserving() and composed.is_isometric_dilation()
    assert len(composed.ops) == 4 and composed.kraus_rank() == 3
    bad = KrausChannel.of([[[ONE8, ZERO8], [ZERO8, ONE8]], [[ZERO8, ONE8], [ZERO8, ZERO8]]])
    assert not bad.is_trace_preserving()


def test_rotations_are_exact_only_on_the_pi_over_4_grid():
    assert pauli_rotation("XZ", Fraction(1, 4), custody=R()).is_unitary()
    with pytest.raises(NotInF4):
        pauli_rotation("Z", Fraction(1, 7))
    h = PauliHamiltonian.of(2, [(1, "ZZ"), (Fraction(1, 2), "XI")])
    assert h.is_hermitian() and h.mpo(custody=R()).is_hermitian()


def test_ghz_saturates_the_heisenberg_limit_exactly():
    for n in (2, 4, 8):
        f = quantum_fisher_information(ghz_circuit(n, custody=R()), total_z_half(n, custody=R()))
        assert f == Q8(n * n)


# -- float plane ------------------------------------------------------------------------------


def test_tt_svd_respects_its_bound_where_tolerance_did_not():
    rng = np.random.default_rng(1)
    s = np.array([1.0] + [0.099] * 99)
    u, _ = np.linalg.qr(rng.standard_normal((100, 100)))
    v, _ = np.linalg.qr(rng.standard_normal((100, 100)))
    t = (u * s) @ v.T
    _, rec = tt_svd(t, 0.1)
    assert rec["bound_holds"]
    assert TensorTrain(t, max_rank=100, tolerance=0.1).relative_error(t) > 0.5


def test_heisenberg_mpo_is_the_nearest_neighbour_sum():
    from functools import reduce

    sx = 0.5 * np.array([[0, 1], [1, 0]], complex)
    sy = 0.5 * np.array([[0, -1j], [1j, 0]])
    sz = 0.5 * np.diag([1, -1]).astype(complex)
    for n in (2, 4, 6):
        explicit = sum(
            reduce(np.kron, [op if k in (i, i + 1) else np.eye(2) for k in range(n)])
            for i in range(n - 1)
            for op in (sx, sy, sz)
        )
        assert np.allclose(HeisenbergHamiltonianMPO(n).to_full_matrix(), explicit, atol=1e-14)


def test_reconstruct_refuses_to_densify_beyond_its_guard():
    from kellogg.tensor_network import TensorNetworkError

    cores = [np.ones((1, 2, 1))] * 40
    with pytest.raises(TensorNetworkError):
        TensorTrain.from_cores(cores).reconstruct()


# -- surface code, 11D vector ---------------------------------------------------------------------


def test_planar_code_encodes_one_qubit_at_the_declared_distance():
    for d in (3, 5, 7):
        r = PlanarSurfaceCode(d).verify()
        assert r.verified and r.logical_qubits == 1 and r.exact_x_distance == d
    legacy = edge_star_report(5)
    assert legacy["noncommuting_pairs"] == 0 and legacy["logical_qubits"] == 0


def test_decoders_correct_every_error_within_the_bound_at_d5():
    c = PlanarSurfaceCode(5)
    for w in (1, 2):
        for qs in itertools.combinations(range(c.n), w):
            e = sum(1 << q for q in qs)
            s = c.syndrome(c.hz, e)
            assert c.corrected(e, c.decode_exact(s))
            assert c.corrected(e, c.decode_union_find(s))


def test_11d_fold_roundtrip_is_equality():
    v = lift([QPhi(10**5, 3), QPhi(-7, 2), QPhi(1)])
    w = fold(v)
    assert w.inside_unit_ball()
    back = unfold(w)
    assert back.coeffs == v.coeffs and back.radicand == v.radicand
    assert fold_certificate(v)["roundtrip_exact"]


# -- benchmarks -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bench",
    [b for b, (axis, _) in BENCHMARKS.items() if axis == "correctness" and b != "cross_version_digest"],
)
def test_correctness_benchmarks_pass_quick(bench):
    art = run(bench, quick=True)
    assert art["passed"] is True, art.get("error") or art["result"]
    assert len(art["digest"]) == 64 and art["classification"] == "MEASURED"


def test_meta_voyage_quick():
    art = run("ten_thousand_qubit_voyage", quick=True)
    assert art["passed"] is True, art["result"]
    assert all(art["result"]["questions"].values())
