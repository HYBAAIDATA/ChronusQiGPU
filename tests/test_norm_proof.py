"""Sigma-protocol norm preimage proofs over F_257[phi]."""

import json

import pytest

from chronus.execution import NativeMathReferenceBackend
from chronus.security.norm_proof import GROUP_ORDER, P, NormProof, norm, prove, verify


def test_field_arithmetic_norm_identities():
    assert norm((1, 0)) == 1
    assert norm((0, 1)) == 256  # N(phi) = -1
    assert norm((1, 1)) == 1  # N(1 + phi) = 1
    assert norm((3, 4)) == (9 + 12 - 16) % P


def test_proof_round_trip_and_tamper_rejection():
    proof = prove((42, 17), nonce=987654321)  # deterministic: no flakiness
    assert proof.statement == norm((42, 17))
    assert verify(proof)
    # Soundness is 1/257 per forgery attempt: across all 256 possible
    # single-step tamper values per axis, detection must be overwhelming.
    for tamper in (
        lambda p, d: NormProof(p.statement, (p.commitment + d) % P, p.response),
        lambda p, d: NormProof((p.statement + d) % P, p.commitment, p.response),
        lambda p, d: NormProof(
            p.statement, p.commitment, ((p.response[0] + d) % P, p.response[1])
        ),
        lambda p, d: NormProof(
            p.statement, p.commitment, (p.response[0], (p.response[1] + d) % P)
        ),
    ):
        detected = sum(not verify(tamper(proof, d)) for d in range(1, P))
        assert detected >= 250, f"tamper detection too weak: {detected}/256"


def test_proofs_do_not_reveal_witness_and_are_randomized():
    witness = (100, 200)
    proofs = [prove(witness) for _ in range(8)]
    commitments = {proof.commitment for proof in proofs}
    assert len(commitments) > 1  # randomized commitments
    assert all(verify(proof) for proof in proofs)


def test_deterministic_nonce_for_reproducible_vectors():
    assert prove((7, 9), nonce=1234) == prove((7, 9), nonce=1234)


def test_wrong_witness_statement_fails_verification():
    proof = prove((5, 5), nonce=24601)  # deterministic nonce
    detected = sum(
        not verify(
            NormProof((proof.statement + d) % P, proof.commitment, proof.response)
        )
        for d in range(1, P)
    )
    assert detected >= 250, f"forgery detection too weak: {detected}/256"


def test_zero_and_out_of_range_elements_rejected():
    with pytest.raises(ValueError):
        prove((0, 0))
    with pytest.raises(ValueError):
        prove((257, 0))
    with pytest.raises(ValueError):
        NormProof.from_dict({"statement": 1, "commitment": 1, "response": [0, 0]})


def test_group_order_matches_field():
    assert GROUP_ORDER == 66048


def test_norm_proof_workload_via_native_backend():
    backend = NativeMathReferenceBackend()
    proved = backend.execute(
        json.dumps({"operation": "prove", "witness": [42, 17]}).encode(),
        "OVID_NORM_PROOF",
    )
    assert proved["valid"] is True
    checked = backend.execute(
        json.dumps({"operation": "verify", "proof": proved}).encode(),
        "OVID_NORM_PROOF",
    )
    assert checked["valid"] is True
    proved["response"][0] = (proved["response"][0] + 1) % P
    tampered = backend.execute(
        json.dumps({"operation": "verify", "proof": proved}).encode(),
        "OVID_NORM_PROOF",
    )
    assert tampered["valid"] is False
    with pytest.raises(ValueError):
        backend.execute(json.dumps({"operation": "other"}).encode(), "OVID_NORM_PROOF")
