"""HYBA production-readiness integration tests — cross-agent seams.

Exercises the wired contracts between the four workstreams on the merged
integration branch:

- OVID transformation lineage enters THESEUS durable custody (C -> B).
- THESEUS admission consults OvidRegistry declared contracts so a
  registered-but-undeclared transform version fails closed (B <- C wiring).
- CHRONUS execution evidence enters THESEUS custody (A -> B).
- TURING pipeline reports enter THESEUS custody (D -> B).
- Recovery groups pending semantic revalidation by producer across all
  three producers; replay reconstructs a second custody byte-exactly.
- AL HARAS boundary: a stored record creates no access authority.
- The aethel.enterprise package re-exports the THESEUS record/checkpoint/
  recovery/retention surface (integration wiring, B's declared dependency).

All evidence states are asserted as honest outcomes on this CPU-only host;
nothing here claims device-bound execution.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aethel.ovid import Ovid, EvidenceState as OvidEvidenceState
from aethel.enterprise import (
    AuthorityBoundaryError,
    DependencyMismatchError,
    OperationalRecord,
    compose,
)
from aethel.enterprise.ovid_registry import OvidRegistry
from aethel.enterprise.schema import OVID_TRANSFORM_V1
from chronus.virtual_igpu.abi import ExecutionPolicy, Workload, WorkloadKind
from chronus.virtual_igpu.runtime import RuntimeDaemon
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter

from turing_universal_quantum_computer import Program, run_pipeline
from turing_universal_quantum_computer.pipeline import VQCRequest


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path / "custody_root"


@pytest.fixture()
def key() -> bytes:
    return b"integration-hmac-key-32b!!!!!"


def _record(rid: str, producer: str, payload: bytes, **kw) -> OperationalRecord:
    kw.setdefault("schema_version", 1)
    kw.setdefault("kind", "execution_evidence")
    return OperationalRecord(
        record_id=rid,
        producer=producer,
        producer_version="integration",
        payload=payload,
        **kw,
    )


# -- package wiring ----------------------------------------------------------


def test_enterprise_package_reexports_theseus_surface() -> None:
    import aethel.enterprise as ent

    for name in (
        "OperationalRecord",
        "ProducerRegistry",
        "ProducerContract",
        "ProducerAdmissionError",
        "ContractValidationError",
        "DependencyMismatchError",
        "EVIDENCE_STATES",
        "CANONICAL_PRODUCERS",
        "default_producer_registry",
        "default_dependency_policy",
        "CheckpointManager",
        "CheckpointIntegrityError",
        "CheckpointUnavailableError",
        "RecoveryReport",
        "RetentionPolicy",
    ):
        assert hasattr(ent, name), f"aethel.enterprise.{name} not re-exported"


def test_canonical_producers_cover_triad_and_tensor() -> None:
    from aethel.enterprise import CANONICAL_PRODUCERS

    assert {"chronus", "turing", "ovid", "tensor"} <= set(CANONICAL_PRODUCERS)


# -- C -> B: OVID lineage into THESEUS custody --------------------------------


def test_ovid_lineage_enters_theseus_custody(root: Path, key: bytes) -> None:
    ovid = Ovid()
    payload = b"cross-agent custody payload" * 7
    form = ovid.metamorphose(payload)
    assert form.lineage is not None
    lineage_bytes = json.dumps(form.lineage.to_dict(), sort_keys=True).encode()

    custody = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    record = _record(
        "ovid-lineage-1",
        "ovid",
        lineage_bytes,
        kind="transform_lineage",
        evidence_state="PASS",
        dependencies={"ovid_transform": OVID_TRANSFORM_V1},
        correlation_ids={"transform_id": form.lineage.transform_id},
    )
    custody.put_record(record)

    back = custody.get_record("ovid-lineage-1")
    assert back.producer == "ovid"
    stored = json.loads(back.payload.decode())
    assert stored["lineage_id"] == form.lineage.lineage_id
    assert stored["input_sha256"] == form.lineage.input_sha256
    assert stored["evidence_state"] == "PASS"

    # OVID still owns equivalence; THESEUS only preserved the lineage.
    verdict = ovid.verify_equivalence(payload, form)
    assert verdict.equivalent is True
    assert verdict.state == OvidEvidenceState.PASS.value


def test_uncontracted_ovid_version_fails_closed_at_admission(root: Path, key: bytes) -> None:
    """Registered-but-undeclared transform versions are refused at admission."""
    registry = OvidRegistry()
    registry.register(9, lambda b: b, lambda b: b)  # no TransformContract
    custody = compose(root, hmac_key=key, allow_insecure_dev_key=True, ovid=registry)

    stale = _record(
        "stale-dep",
        "ovid",
        b"x",
        dependencies={"ovid_transform": 9},
    )
    with pytest.raises(DependencyMismatchError):
        custody.put_record(stale)

    # The contracted v1 path still admits.
    custody.put_record(
        _record("ok-dep", "ovid", b"x", dependencies={"ovid_transform": OVID_TRANSFORM_V1})
    )


def test_unknown_dependency_namespace_fails_closed(root: Path, key: bytes) -> None:
    custody = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    record = _record("bad-dep", "chronus", b"x", dependencies={"nonexistent_dep": 1})
    with pytest.raises(DependencyMismatchError):
        custody.put_record(record)


# -- A -> B: CHRONUS execution evidence into THESEUS custody -------------------


def test_chronus_execution_receipt_enters_custody(root: Path, key: bytes) -> None:
    daemon = RuntimeDaemon(adapters=[CPUEmulatorAdapter()], store_dir=str(root / "rt"))
    workload = Workload(
        id="w-int",
        kind=WorkloadKind.PROBE,
        tenant="integration",
        input={"op": "probe"},
        execution_policy=ExecutionPolicy.PREFERRED_ACCELERATOR.value,
    )
    result = daemon.submit(workload)
    receipt = json.dumps(result.receipt or {}, sort_keys=True, default=str).encode()

    custody = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    state = "PASS" if result.status == "ok" else "FAIL"
    record = _record(
        "chronus-exec-1",
        "chronus",
        receipt,
        kind="execution_evidence",
        evidence_state=state,
        correlation_ids={"workload_id": "w-int"},
    )
    custody.put_record(record)

    back = custody.get_record("chronus-exec-1")
    assert back.producer == "chronus"
    assert back.payload == receipt
    assert back.correlation_ids["workload_id"] == "w-int"


# -- D -> B: TURING pipeline report into THESEUS custody ------------------------


def test_turing_pipeline_report_enters_custody(root: Path, key: bytes) -> None:
    program = Program(n_qubits=2).then("h", 0).then("cx", 0, 1)
    report = run_pipeline(VQCRequest(program=program, shots=8, seed=1))
    assert report.verdict == "PASS"

    custody = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    record = _record(
        "turing-report-1",
        "turing",
        report.to_json().encode(),
        kind="vqc_pipeline_report",
        evidence_state="PASS",
        correlation_ids={"program_digest": report.program_digest or ""},
    )
    custody.put_record(record)

    back = custody.get_record("turing-report-1")
    stored = json.loads(back.payload.decode())
    assert stored["schema"] == report.schema
    assert stored["verdict"] == "PASS"
    assert stored["execution_kind"]["measured_qpu"] is False


# -- recovery / replay across producers ----------------------------------------


def test_recovery_groups_pending_revalidation_by_producer(root: Path, key: bytes) -> None:
    custody = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    custody.put_record(_record("r-chronus", "chronus", b"c"))
    custody.put_record(_record("r-ovid", "ovid", b"o"))
    custody.put_record(_record("r-turing", "turing", b"t"))

    # Reopen: recover() runs at open on the same root.
    recovered = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    pending = recovered.pending_revalidation()
    assert set(pending) >= {"chronus", "ovid", "turing"}
    assert "r-chronus" in pending["chronus"]
    assert "r-ovid" in pending["ovid"]
    assert "r-turing" in pending["turing"]

    for rid, producer in (
        ("r-chronus", "chronus"),
        ("r-ovid", "ovid"),
        ("r-turing", "turing"),
    ):
        recovered.semantic_revalidated(rid, verdict="ok", producer=producer)
    assert recovered.pending_revalidation() == {}


def test_replay_reconstructs_second_custody(root: Path, key: bytes, tmp_path: Path) -> None:
    custody = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    custody.put_record(_record("r-ovid", "ovid", b"lineage-bytes"))
    custody.put_record(_record("r-chronus", "chronus", b"receipt-bytes"))

    report = custody.verify_replay()
    assert report["match"] is True
    assert report["divergences"] == []

    dest = compose(tmp_path / "custody_dest", hmac_key=key, allow_insecure_dev_key=True)
    out = custody.replay(dest)
    assert out["match"] is True
    assert out["digest_mismatches"] == []
    # replay() re-executes put ops (payloads/digests verified); operational
    # manifests are not replayed — recorded as an integration gap.
    assert dest.get("r-ovid") == b"lineage-bytes"
    assert dest.get("r-chronus") == b"receipt-bytes"


# -- AL HARAS boundary ----------------------------------------------------------


def test_stored_record_grants_no_access_authority(root: Path, key: bytes) -> None:
    writer = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    writer.put_record(_record("r-sec", "al_haras", b"policy-evidence"))

    class _PutOnlyHook:
        def before_put(self, tenant, record_id, payload, meta):
            return True

        def after_put(self, tenant, record_id, envelope, meta):
            return None

    strict = compose(
        root,
        hmac_key=key,
        allow_insecure_dev_key=True,
        hook=_PutOnlyHook(),
        require_access_contract=True,
    )
    with pytest.raises(AuthorityBoundaryError):
        strict.get("r-sec")
