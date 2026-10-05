"""OVID declared transformation contracts — classification, registry, equivalence.

Locks the production contract surface for the metamorphosis plane:

- every transform in the catalog carries a mandatory exactness class
  (EXACT / BOUNDED_LOSS / APPROXIMATE / UNSUPPORTED) and a consistent
  declaration (EXACT => reversible + zero error bound);
- the versioned registry serves declared contracts, fails closed on
  unknown versions, undeclared transforms and UNSUPPORTED declarations;
- semantic/equivalence validation returns explicit evidence states —
  PASS only on byte-exact materialisation, FAIL on any tamper;
- transform provenance (TransformLineage) is emitted at fold time with
  the shared provenance fields THESEUS custody requires.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from aethel.encoding import MAX_FOLD_LEN, ZeckendorfVector, fold
from aethel.enterprise.errors import SchemaVersionError
from aethel.enterprise.ovid_registry import (
    DEFAULT_OVID_REGISTRY,
    OvidRegistry,
    fold_versioned,
    transform_contracts,
    unfold_versioned,
)
from aethel.enterprise.schema import OVID_TRANSFORM_V1
from aethel.errors import FoldDomainOverflow, ZeckendorfInvariantError
from aethel.ovid import (
    CONTRACT_VERSION,
    OVID_TRANSFORM_CONTRACTS,
    ZECKENDORF_TRANSFORM_ID,
    EvidenceState,
    Exactness,
    FoldedWorkingForm,
    TransformContract,
    TransformLineage,
    open_ovid,
    transform_contract,
)


# -- declared contract catalog ------------------------------------------------


def test_every_transform_is_classified():
    ids = [c.transform_id for c in OVID_TRANSFORM_CONTRACTS]
    assert len(ids) == len(set(ids)), "duplicate transform ids in catalog"
    for contract in OVID_TRANSFORM_CONTRACTS:
        assert isinstance(contract.exactness, Exactness)
        contract.validate()  # declared consistency holds at rest


def test_exact_contracts_declare_zero_error_and_reversibility():
    for contract in OVID_TRANSFORM_CONTRACTS:
        if contract.exactness is Exactness.EXACT:
            assert contract.reversible
            assert contract.error_bound in (None, 0.0)


def test_catalog_covers_the_owned_pipeline():
    ids = {c.transform_id for c in OVID_TRANSFORM_CONTRACTS}
    assert {
        "ovid.zeckendorf.fold",
        "ovid.phi_fold.numeric",
        "ovid.phi_fold.splice",
        "ovid.phi_fold.unfold_partial",
        "ovid.phi_memory.refold",
        "ovid.fold_store.checkpoint",
    } <= ids


def test_pulvini_entry_is_attributed_reference_not_execution():
    contract = transform_contract("pulvini.svd_fold")
    assert contract.owner == "pulvini"
    assert contract.execution == "external"
    # BOUNDED_LOSS with per-operation measured bound: declared via residuals
    assert contract.exactness is Exactness.BOUNDED_LOSS
    assert "reconstruction_error_bound" in contract.residuals
    local = {c.transform_id for c in OVID_TRANSFORM_CONTRACTS if c.execution == "local"}
    assert "pulvini.svd_fold" not in local


def test_unknown_transform_id_fails_closed():
    with pytest.raises(KeyError):
        transform_contract("ovid.does.not.exist")


def test_contracts_serialise_for_custody():
    for contract in OVID_TRANSFORM_CONTRACTS:
        doc = contract.to_dict()
        json.dumps(doc)
        assert doc["transform_id"] == contract.transform_id
        assert doc["exactness"] == contract.exactness.value
        assert doc["contract_version"] == CONTRACT_VERSION


def test_inconsistent_declarations_fail_closed():
    with pytest.raises(ValueError):
        TransformContract(
            transform_id="bad.exact",
            exactness=Exactness.EXACT,
            reversible=False,
        ).validate()
    with pytest.raises(ValueError):
        TransformContract(
            transform_id="bad.exact.bound",
            exactness=Exactness.EXACT,
            error_bound=0.5,
        ).validate()
    with pytest.raises(ValueError):
        TransformContract(
            transform_id="bad.bounded",
            exactness=Exactness.BOUNDED_LOSS,
            error_bound=None,
        ).validate()


# -- versioned registry contract gate -----------------------------------------


def test_registry_v1_contract_is_declared_exact():
    contract = DEFAULT_OVID_REGISTRY.contract(OVID_TRANSFORM_V1)
    assert contract.exactness is Exactness.EXACT
    assert contract.reversible
    assert contract.error_bound == 0.0
    assert contract.transform_id == ZECKENDORF_TRANSFORM_ID
    domain = dict(contract.domain)
    assert domain["payload_bytes_max"] == MAX_FOLD_LEN


def test_registry_unknown_version_fails_closed():
    reg = OvidRegistry()
    with pytest.raises(SchemaVersionError):
        reg.fold(b"payload", 999)
    with pytest.raises(SchemaVersionError):
        reg.unfold(b"{}", 999)
    with pytest.raises(SchemaVersionError):
        reg.contract(999)


def test_registry_undeclared_transform_refuses_classification():
    reg = OvidRegistry()
    reg.register(7, lambda b: b, lambda b: b)
    assert 7 in reg.supported()
    # executable for compatibility, but classification fails closed
    with pytest.raises(SchemaVersionError):
        reg.contract(7)


def test_registry_unsupported_transform_fails_closed():
    reg = OvidRegistry()
    contract = TransformContract(
        transform_id="ovid.experimental.fold",
        version=77,
        exactness=Exactness.UNSUPPORTED,
        reversible=False,
        support="declared for audit only — not executable",
    )
    reg.register(77, lambda b: b, lambda b: b, contract=contract)
    with pytest.raises(SchemaVersionError):
        reg.fold(b"payload", 77)
    with pytest.raises(SchemaVersionError):
        reg.unfold(b"payload", 77)


def test_registry_rejects_inconsistent_contract():
    reg = OvidRegistry()
    with pytest.raises(SchemaVersionError):
        reg.register(
            8,
            lambda b: b,
            lambda b: b,
            contract=TransformContract(
                transform_id="bad", version=8, exactness=Exactness.EXACT, error_bound=1e-3
            ),
        )
    with pytest.raises(SchemaVersionError):
        reg.register(9, lambda b: b, lambda b: b, contract={"not": "a contract"})


def test_registry_contracts_surface_is_serializable():
    docs = transform_contracts()
    assert OVID_TRANSFORM_V1 in docs
    json.dumps(docs)
    assert docs[OVID_TRANSFORM_V1]["exactness"] == "EXACT"


def test_registry_registered_exact_transform_round_trips():
    reg = OvidRegistry()
    contract = TransformContract(
        transform_id="ovid.test.identity",
        version=42,
        exactness=Exactness.EXACT,
        error_bound=0.0,
    )
    reg.register(42, lambda b: b[::-1], lambda b: b[::-1], contract=contract)
    payload = b"registered-exact-transform"
    assert reg.unfold(reg.fold(payload, 42), 42) == payload
    assert reg.contract(42).exactness is Exactness.EXACT


# -- semantic / equivalence validation ----------------------------------------


def test_verify_equivalence_pass_on_honest_round_trip():
    ovid = open_ovid()
    payload = b"equivalence-evidence-payload" * 17
    form = ovid.metamorphose(payload)
    verdict = ovid.verify_equivalence(payload, form)
    assert verdict.state == EvidenceState.PASS.value
    assert verdict.equivalent
    assert verdict.input_sha256 == hashlib.sha256(payload).hexdigest()
    assert verdict.output_sha256 == verdict.input_sha256
    assert verdict.transform_id == ZECKENDORF_TRANSFORM_ID


def test_verify_equivalence_fail_on_tampered_form():
    ovid = open_ovid()
    payload = b"tamper-me" * 32
    form = ovid.metamorphose(payload)
    # Forge a form whose declared digest does not match the vector payload.
    forged = FoldedWorkingForm(
        vector=form.vector,
        sparse=form.sparse,
        digest=hashlib.sha256(b"different-payload").hexdigest(),
        raw_len=form.raw_len,
        folded_units=form.folded_units,
        lineage=form.lineage,
    )
    verdict = ovid.verify_equivalence(payload, forged)
    assert verdict.state == EvidenceState.FAIL.value
    assert not verdict.equivalent
    # and the fail-closed materialise path still refuses it outright
    with pytest.raises(ZeckendorfInvariantError):
        ovid.materialise(forged)


def test_verify_equivalence_fail_on_wrong_source():
    ovid = open_ovid()
    form = ovid.metamorphose(b"original-source")
    verdict = ovid.verify_equivalence(b"different-source", form)
    assert verdict.state == EvidenceState.FAIL.value
    assert not verdict.equivalent


def test_verify_equivalence_fail_on_non_bytes_source():
    ovid = open_ovid()
    form = ovid.metamorphose(b"payload")
    verdict = ovid.verify_equivalence("not-bytes", form)  # type: ignore[arg-type]
    assert verdict.state == EvidenceState.FAIL.value
    assert not verdict.equivalent


def test_verify_equivalence_fail_on_corrupt_vector():
    ovid = open_ovid()
    payload = b"corrupt-me" * 8
    form = ovid.metamorphose(payload)
    # Adjacent mask violates the Zeckendorf invariant -> verify() fails.
    bad_vector = ZeckendorfVector(blocks=((0, 0b11),), total_bytes=len(payload))
    corrupt = FoldedWorkingForm(
        vector=bad_vector,
        sparse=form.sparse,
        digest=form.digest,
        raw_len=form.raw_len,
        folded_units=1,
    )
    verdict = ovid.verify_equivalence(payload, corrupt)
    assert verdict.state == EvidenceState.FAIL.value
    assert not verdict.equivalent


# -- round-trip property + differential coverage -------------------------------


@pytest.mark.parametrize("size", [0, 1, 7, 8, 9, 63, 64, 65, 255, 1024, 4096])
def test_metamorphose_materialise_byte_exact(size):
    import os

    payload = os.urandom(size)
    ovid = open_ovid()
    form, out = ovid.round_trip(payload)
    assert out == payload
    assert form.digest == hashlib.sha256(payload).hexdigest()
    assert form.verify()
    assert ovid.verify_equivalence(payload, form).equivalent


def test_registry_vs_direct_codec_differential():
    """fold_versioned working form decodes to the same vector as encoding.fold."""
    payload = bytes(range(256)) * 4
    working = fold_versioned(payload)
    doc = json.loads(working.decode("utf-8"))
    assert doc["kind"] == "zeckendorf_vector_v1"
    direct = fold(payload)
    assert doc["blocks"] == [[int(o), int(m)] for o, m in direct.blocks]
    assert doc["total_bytes"] == direct.total_bytes
    assert doc["folded_units"] == direct.folded_units
    assert unfold_versioned(working) == payload


def test_working_form_digest_matches_registry_encoding():
    from aethel.ovid import working_form_digest

    payload = b"digest-equivalence" * 5
    assert working_form_digest(fold(payload)) == hashlib.sha256(
        fold_versioned(payload)
    ).hexdigest()


# -- failure modes -------------------------------------------------------------


def test_domain_overflow_fails_closed():
    ovid = open_ovid(max_fold_len=64)
    with pytest.raises(FoldDomainOverflow):
        ovid.metamorphose(b"x" * 65)


def test_non_bytes_payload_rejected():
    ovid = open_ovid()
    with pytest.raises(TypeError):
        ovid.metamorphose("text-payload")  # type: ignore[arg-type]


def test_materialise_rejects_foreign_object():
    ovid = open_ovid()
    with pytest.raises(TypeError):
        ovid.materialise(b"not-a-form")  # type: ignore[arg-type]


def test_metrics_track_outcomes():
    ovid = open_ovid()
    payload = b"metric-payload"
    form = ovid.metamorphose(payload)
    ovid.materialise(form)
    ovid.verify_equivalence(payload, form)
    ovid.verify_equivalence(b"wrong", form)
    m = ovid.metrics()
    # verify_equivalence materialises internally: 1 explicit + 2 inside verdicts
    assert m["fold_ok"] == 1 and m["unfold_ok"] == 3
    assert m["equivalence_pass"] == 1 and m["equivalence_fail"] == 1


# -- transform lineage / provenance --------------------------------------------


def test_lineage_emitted_with_shared_provenance_fields():
    ovid = open_ovid()
    payload = b"lineage-payload" * 11
    form = ovid.metamorphose(payload, parents=("custody:theseus-1",))
    lineage = form.lineage
    assert isinstance(lineage, TransformLineage)
    assert lineage.transform_id == ZECKENDORF_TRANSFORM_ID
    assert lineage.exactness == Exactness.EXACT.value
    assert lineage.producer == "ovid"
    assert lineage.producer_version
    assert lineage.contract_version == CONTRACT_VERSION
    assert lineage.input_sha256 == hashlib.sha256(payload).hexdigest()
    assert lineage.output_digest
    assert lineage.input_bytes == len(payload)
    assert lineage.folded_units == form.folded_units
    assert lineage.transform_ns > 0
    assert lineage.parent_ids == ("custody:theseus-1",)
    assert lineage.evidence_state == EvidenceState.PASS.value
    # shared provenance keys the custody contract requires
    doc = lineage.to_dict()
    for key in (
        "lineage_id",
        "transform_id",
        "transform_version",
        "contract_version",
        "exactness",
        "producer",
        "producer_version",
        "input_sha256",
        "output_digest",
        "input_bytes",
        "transform_ns",
        "parent_ids",
        "evidence_state",
    ):
        assert key in doc


def test_lineage_survives_custody_serialisation():
    ovid = open_ovid()
    form = ovid.metamorphose(b"custody-replay" * 9)
    doc = form.lineage.to_dict()
    revived = TransformLineage.from_dict(json.loads(json.dumps(doc)))
    assert revived == form.lineage


def test_lineage_ids_are_execution_unique():
    ovid = open_ovid()
    a = ovid.metamorphose(b"same-payload")
    b = ovid.metamorphose(b"same-payload")
    # same transform on same input still gets a distinct lineage id
    # (transform_ns differentiates executions)
    assert a.lineage.lineage_id != b.lineage.lineage_id
    # but the transformed representation digest is content-deterministic
    assert a.lineage.output_digest == b.lineage.output_digest
