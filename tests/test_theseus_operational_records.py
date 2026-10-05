"""THESEUS operational-record contract — admission, evidence, roundtrip."""

from __future__ import annotations

from pathlib import Path

import pytest

from aethel.enterprise import AuthorityBoundaryError, DenyingHook, compose
from aethel.enterprise.records import (
    CANONICAL_PRODUCERS,
    DEPENDENCY_OVID_TRANSFORM,
    DEPENDENCY_THESEUS_FORMAT,
    EVIDENCE_STATES,
    ContractValidationError,
    DependencyMismatchError,
    OperationalRecord,
    ProducerAdmissionError,
    ProducerContract,
    ProducerRegistry,
    default_dependency_policy,
    default_producer_registry,
)
from aethel.enterprise.retention import RetentionPolicy
from aethel.enterprise.schema import OVID_TRANSFORM_V1, THESEUS_FORMAT_VERSION


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path / "custody_root"


@pytest.fixture()
def key() -> bytes:
    return b"unit-test-hmac-key-32b!!!!!!!!"


def _record(rid: str = "r1", producer: str = "chronus", **kw) -> OperationalRecord:
    kw.setdefault("payload", b"payload-bytes")
    kw.setdefault("schema_version", 1)
    kw.setdefault("kind", "execution_evidence")
    return OperationalRecord(
        record_id=rid,
        producer=producer,
        producer_version="1.0.0",
        **kw,
    )


# -- contract shape --------------------------------------------------------


def test_record_manifest_and_digest_are_stable() -> None:
    r = _record(timestamp=1700000000.0)
    r2 = _record(timestamp=1700000000.0)
    assert r.manifest() == r2.manifest()
    assert r.manifest_digest() == r2.manifest_digest()
    assert set(r.manifest()) >= {
        "record_id",
        "producer",
        "producer_version",
        "schema_version",
        "kind",
        "evidence_state",
        "timestamp",
        "sequence",
        "epoch",
        "lineage",
        "correlation_ids",
        "dependencies",
        "content_digest",
    }


def test_record_dict_roundtrip() -> None:
    r = _record(lineage=("p1", "p2"), correlation_ids={"run": "abc"})
    back = OperationalRecord.from_dict(r.to_dict())
    assert back.manifest() == r.manifest()
    assert back.payload == r.payload


def test_every_evidence_state_is_storable_verbatim() -> None:
    for state in sorted(EVIDENCE_STATES):
        r = _record(evidence_state=state)
        r.validate(default_producer_registry(), {})
        assert r.evidence_state == state


def test_canonical_producers_all_admitted() -> None:
    registry = default_producer_registry()
    for name in CANONICAL_PRODUCERS:
        assert name in {
            "chronus",
            "turing",
            "ovid",
            "tensor",
            "pythia",
            "salamander",
            "al_haras",
            "euclid",
            "toe",
        }
        _record(producer=name).validate(registry, {})


# -- admission failures (fail closed) ---------------------------------------


def test_unknown_producer_rejected() -> None:
    with pytest.raises(ProducerAdmissionError):
        _record(producer="rogue_subsystem").validate(default_producer_registry(), {})


def test_schema_version_below_window_rejected() -> None:
    registry = ProducerRegistry([ProducerContract("chronus", min_schema_version=2)])
    with pytest.raises(ProducerAdmissionError):
        _record(schema_version=1).validate(registry, {})


def test_schema_version_above_window_rejected() -> None:
    registry = ProducerRegistry(
        [ProducerContract("chronus", min_schema_version=1, max_schema_version=3)]
    )
    with pytest.raises(ProducerAdmissionError):
        _record(schema_version=4).validate(registry, {})
    _record(schema_version=3).validate(registry, {})


def test_invalid_evidence_state_rejected() -> None:
    with pytest.raises(ContractValidationError):
        _record(evidence_state="PROBABLY_FINE").validate(default_producer_registry(), {})


def test_declared_digest_mismatch_rejected() -> None:
    r = _record(content_digest="0" * 64)
    with pytest.raises(ContractValidationError):
        r.validate(default_producer_registry(), {})


def test_empty_record_id_rejected() -> None:
    with pytest.raises(ContractValidationError):
        _record(rid="").validate(default_producer_registry(), {})


def test_dependency_mismatch_rejected() -> None:
    policy = default_dependency_policy(
        theseus_format_version=THESEUS_FORMAT_VERSION,
        ovid_transform_versions=(OVID_TRANSFORM_V1,),
    )
    with pytest.raises(DependencyMismatchError):
        _record(dependencies={DEPENDENCY_OVID_TRANSFORM: 99}).validate(
            default_producer_registry(), policy
        )
    # satisfied dependency admitted
    _record(dependencies={DEPENDENCY_OVID_TRANSFORM: OVID_TRANSFORM_V1}).validate(
        default_producer_registry(), policy
    )


def test_unverifiable_dependency_namespace_rejected() -> None:
    # A dependency THESEUS cannot verify is refused — fail closed.
    with pytest.raises(DependencyMismatchError):
        _record(dependencies={"some_foreign_contract": 1}).validate(default_producer_registry(), {})


def test_theseus_format_dependency_checked_against_envelope_version() -> None:
    policy = default_dependency_policy(
        theseus_format_version=THESEUS_FORMAT_VERSION,
        ovid_transform_versions=(OVID_TRANSFORM_V1,),
    )
    with pytest.raises(DependencyMismatchError):
        _record(dependencies={DEPENDENCY_THESEUS_FORMAT: 999}).validate(
            default_producer_registry(), policy
        )


# -- custody integration -----------------------------------------------------


def test_put_record_get_record_roundtrip(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    r = _record(
        evidence_state="MEASURED",
        lineage=("parent-1",),
        correlation_ids={"run_id": "run-9", "workload": "matmul"},
        epoch="e3",
        sequence=7,
    )
    env = c.put_record(r)
    assert env.record_id == "r1"
    assert env.content_digest == r.content_digest
    back = c.get_record("r1")
    assert back.producer == "chronus"
    assert back.payload == r.payload
    assert back.evidence_state == "MEASURED"
    assert back.lineage == ("parent-1",)
    assert back.correlation_ids["run_id"] == "run-9"
    assert back.sequence == 7


def test_put_record_rejects_invalid_before_write(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    bad = _record(producer="not_a_producer")
    with pytest.raises(ProducerAdmissionError):
        c.put_record(bad)
    # nothing was written — no primary file exists
    assert c.list_records() == []


def test_put_record_fail_states_stored_verbatim(root: Path, key: bytes) -> None:
    # Custody preserves meaning; it does not judge it. FAIL/GATED/UNAVAILABLE
    # records are stored with their declared state intact.
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    for i, state in enumerate(("FAIL", "GATED", "UNAVAILABLE", "REFUTED")):
        c.put_record(_record(rid=f"r{i}", evidence_state=state))
    states = {r["record_id"]: r["evidence_state"] for r in c.list_records()}
    assert states == {
        "r0": "FAIL",
        "r1": "GATED",
        "r2": "UNAVAILABLE",
        "r3": "REFUTED",
    }


def test_get_record_without_manifest_raises(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"raw bytes no manifest", record_id="plain")
    with pytest.raises(KeyError):
        c.get_record("plain")


def test_list_records_exposes_producer_metadata(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put_record(_record(rid="a", producer="turing", kind="vqc_checkpoint"))
    c.put(b"non-record payload", record_id="b")
    recs = {r["record_id"]: r for r in c.list_records()}
    assert recs["a"]["producer"] == "turing"
    assert recs["a"]["kind"] == "vqc_checkpoint"
    assert recs["b"]["producer"] == "unknown"


# -- access enforcement (a stored record does not create authority) -----------


def test_get_denied_by_hook_fails_closed(root: Path, key: bytes) -> None:
    # Write the record under a permissive custody first
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"secret bytes", record_id="guarded")
    denying = compose(root, hmac_key=key, allow_insecure_dev_key=True, hook=DenyingHook())
    with pytest.raises(AuthorityBoundaryError):
        denying.get("guarded")
    assert denying.telemetry.get("access_deny:get") == 1


def test_delete_denied_by_hook(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"data", record_id="victim")
    denying = compose(root, hmac_key=key, allow_insecure_dev_key=True, hook=DenyingHook())
    with pytest.raises(AuthorityBoundaryError):
        denying.delete("victim")
    # record still exists and is readable under the permissive custody
    assert c.get("victim") == b"data"


def test_access_contract_callable_gates_reads(root: Path, key: bytes) -> None:
    allowed: set[str] = set()
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"a", record_id="open")
    c.put(b"b", record_id="closed")
    allowed.add("open")

    def contract(tenant, action, record_id, meta) -> bool:
        return action == "get" and record_id in allowed

    gated = compose(
        root,
        hmac_key=key,
        allow_insecure_dev_key=True,
        access_contract=contract,
    )
    assert gated.get("open") == b"a"
    with pytest.raises(AuthorityBoundaryError):
        gated.get("closed")
    with pytest.raises(AuthorityBoundaryError):
        gated.delete("open")


def test_require_access_contract_closes_unsupplied_hook(root: Path, key: bytes) -> None:
    """Strict mode: no supplied contract means NO access (fail closed)."""
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"x", record_id="r")

    class PutOnlyHook:
        def before_put(self, tenant, record_id, payload, meta):
            return True

        def after_put(self, tenant, record_id, envelope, meta):
            return None

        def after_heal(self, tenant, record_id, detail):
            return None

    strict = compose(
        root,
        hmac_key=key,
        allow_insecure_dev_key=True,
        hook=PutOnlyHook(),
        require_access_contract=True,
    )
    with pytest.raises(AuthorityBoundaryError):
        strict.get("r")
    with pytest.raises(AuthorityBoundaryError):
        strict.delete("r")


def test_health_declares_access_contract_state(root: Path, key: bytes) -> None:
    open_c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert open_c.health()["access_contract"] == "hook"  # AllowAllHook impls
    strict = compose(
        root,
        hmac_key=key,
        allow_insecure_dev_key=True,
        hook=None,
        access_contract=lambda t, a, r, m: True,
    )
    assert strict.health()["access_contract"] == "callable"


# -- retention -----------------------------------------------------------------


def test_retention_evicts_oldest_records(root: Path, key: bytes) -> None:
    c = compose(
        root,
        hmac_key=key,
        allow_insecure_dev_key=True,
        retention=RetentionPolicy(max_records=2),
    )
    for i in range(4):
        c.put(f"payload {i}".encode(), record_id=f"r{i}")
    report = c.enforce_retention()
    assert report["kept"] == 2
    assert sorted(report["evict"]) == ["r0", "r1"]
    assert {r["record_id"] for r in c.list_records()} == {"r2", "r3"}


def test_retention_unbounded_is_noop(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"x", record_id="r")
    report = c.enforce_retention()
    assert report["evict"] == [] and report["kept"] == 1
