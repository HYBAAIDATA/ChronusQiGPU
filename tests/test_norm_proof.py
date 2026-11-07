"""Sigma-protocol norm preimage proofs over F_257[phi]."""

import json

import pytest

from chronus.execution import NativeMathReferenceBackend
from chronus.security.norm_proof import GROUP_ORDER, P, NormProof, norm, prove, verify


def test_field_arithmetic_norm_identities():
    assert norm((1, 0)) == 1
    assert norm((0, 1)) == 256  # N(phi) = -1
    assert norm((1, 1)) == 1    # N(1 + phi) = 1
    assert norm((3, 4)) == (9 + 12 - 16) % P


def test_proof_round_trip_and_tamper_rejection():
    witness = (42, 17)
    proof = prove(witness)
    assert proof.statement == norm(witness)
    assert verify(proof)
    # Tampered commitment, response or statement must fail.
    assert not verify(NormProof(proof.statement, (proof.commitment + 1) % P, proof.response))
    assert not verify(NormProof((proof.statement + 1) % P, proof.commitment, proof.response))
    assert not verify(NormProof(
        proof.statement, proof.commitment,
        ((proof.response[0] + 1) % P, proof.response[1]),
    ))


def test_proofs_do_not_reveal_witness_and_are_randomized():
    witness = (100, 200)
    proofs = [prove(witness) for _ in range(8)]
    commitments = {proof.commitment for proof in proofs}
    assert len(commitments) > 1  # randomized commitments
    assert all(verify(proof) for proof in proofs)


def test_deterministic_nonce_for_reproducible_vectors():
    assert prove((7, 9), nonce=1234) == prove((7, 9), nonce=1234)


def test_wrong_witness_statement_fails_verification():
    proof = prove((5, 5))
    forged = NormProof((proof.statement + 7) % P, proof.commitment, proof.response)
    assert not verify(forged)


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
