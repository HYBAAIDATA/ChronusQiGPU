"""Falsification tests for public VQC computation certificates."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from turing_universal_quantum_computer.backends import (
    Program,
    execute,
    execute_certified,
)
from turing_universal_quantum_computer.certificates import (
    RunWitness,
    VQCComputationCertificate,
    WITNESS_SCHEMA_V1,
    WITNESS_SCHEMA_V2,
    WitnessError,
    issue_computation_certificate,
    issue_witness,
    replay_computation_certificate,
    verify_computation_certificate,
)
from turing_universal_quantum_computer.pipeline import VQCRequest, run_pipeline


def bell_program() -> Program:
    return Program(2).then("h", 0).then("cx", 0, 1)


def test_public_execute_always_attaches_a_certificate() -> None:
    program = bell_program()
    result = execute(program)
    assert result.certificate is not None
    certificate = VQCComputationCertificate.from_dict(result.certificate)
    assert certificate.halted
    assert certificate.steps == len(program.operations)
    assert certificate.replayable
    assert verify_computation_certificate(program, result, certificate)


def test_certified_execution_binds_witness_to_certificate() -> None:
    execution = execute_certified(bell_program())
    assert (
        execution.witness.computation_certificate_digest
        == execution.certificate.certificate_digest
    )
    assert execution.result.certificate == execution.certificate.to_dict()
    assert execution.witness.schema == WITNESS_SCHEMA_V2
    assert execution.witness.issued_at


def test_identical_exact_runs_have_identical_digests() -> None:
    first = execute_certified(bell_program())
    second = execute_certified(bell_program())
    assert first.certificate.certificate_digest == second.certificate.certificate_digest
    assert first.certificate.attestation == second.certificate.attestation
    assert first.witness.digest() == second.witness.digest()


def test_unseeded_sampling_is_normalized_to_replayable_seed_zero() -> None:
    program = bell_program()
    first = execute_certified(program, shots=64)
    second = execute_certified(program, shots=64, seed=0)
    assert first.certificate.replayable
    assert first.certificate == second.certificate
    replayed = replay_computation_certificate(
        program,
        first.certificate,
        execute,
        options={"shots": 64, "seed": 0},
    )
    assert replayed.certificate == first.certificate.to_dict()


def test_output_and_trace_tampering_fail_closed() -> None:
    execution = execute_certified(bell_program())
    bad_output = replace(execution.certificate, output="0" * 64)
    with pytest.raises(WitnessError, match="digest"):
        bad_output.verify_integrity()
    bad_trace = replace(
        execution.certificate,
        trace=tuple(reversed(execution.certificate.trace)),
    )
    with pytest.raises(WitnessError, match="Merkle"):
        bad_trace.verify_integrity()


def test_unordered_certificate_values_fail_closed() -> None:
    program = bell_program()
    result = execute(program)
    result.payload["unordered"] = {"a", "b"}
    with pytest.raises(WitnessError, match="unordered"):
        issue_computation_certificate(program, result)


def test_v1_witness_digest_remains_backward_compatible() -> None:
    program = bell_program()
    result = execute(program)
    current = issue_witness(program, result)
    payload = current.to_dict()
    payload["schema"] = WITNESS_SCHEMA_V1
    payload.pop("computation_certificate_digest")
    legacy = RunWitness.from_dict(payload)
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert legacy.digest() == expected


def test_v2_witness_timestamp_does_not_change_content_identity() -> None:
    execution = execute_certified(bell_program())
    later = replace(execution.witness, issued_at="2099-01-01T00:00:00+00:00")
    assert execution.witness.digest() == later.digest()


def test_pipeline_exposes_and_verifies_certificate() -> None:
    report = run_pipeline(VQCRequest(program=bell_program()))
    assert report.verdict == "PASS"
    assert report.certificate is not None
    certificate = VQCComputationCertificate.from_dict(report.certificate)
    assert certificate.verify_integrity()
    assert report.witness is not None
    assert (
        report.witness["computation_certificate_digest"]
        == certificate.certificate_digest
    )
