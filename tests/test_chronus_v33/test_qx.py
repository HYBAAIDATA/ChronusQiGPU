from __future__ import annotations

import numpy as np
import pytest

from chronus.v33.qx import (
    QXCommandBuffer,
    QXMemoryDomain,
    QXReferenceExecutor,
    QXValidationError,
)


def _pauli_x() -> np.ndarray:
    return np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)


def _pauli_z() -> np.ndarray:
    return np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)


@pytest.mark.unit
def test_qx_reference_executor_preserves_norm_and_records_provenance():
    buffer = QXCommandBuffer()
    buffer.allocate_cavity_region(2)
    buffer.bind_descriptor_set("scene", {"scene_id": "bell-probe", "revision": 1})
    buffer.set_hamiltonian(_pauli_x())
    buffer.evolve(np.pi / 2.0)
    buffer.memory_barrier(QXMemoryDomain.CAVITY)
    buffer.weak_measure(_pauli_z(), epsilon=0.005, probe_id="z-weak")
    buffer.read_expectation(_pauli_z(), result_id="z-final")
    buffer.synchronize("frame-complete")
    digest = buffer.seal()

    report = QXReferenceExecutor().execute(buffer)

    assert report.command_digest == digest
    assert report.backend == "chronus.qx.reference"
    assert report.precision == "complex128/float64"
    assert report.dimension == 2
    assert report.commands_executed == 8
    assert report.barrier_epoch == 1
    assert report.event_ids == ("frame-complete",)
    assert report.descriptor_sets["scene"]["scene_id"] == "bell-probe"
    assert report.expectations["z-final"] == pytest.approx(-1.0, abs=1e-10)
    assert report.weak_measurements["z-weak"] == pytest.approx(-1.0, abs=1e-10)
    assert report.norm_error <= 1e-10
    assert len(report.final_state_sha256) == 64


@pytest.mark.unit
def test_qx_digest_is_deterministic_for_equivalent_buffers():
    def build() -> QXCommandBuffer:
        command_buffer = QXCommandBuffer()
        command_buffer.allocate_cavity_region(2, region_id="r0")
        command_buffer.set_hamiltonian(_pauli_z())
        command_buffer.evolve(0.25)
        command_buffer.read_expectation(_pauli_x(), result_id="x")
        command_buffer.seal()
        return command_buffer

    assert build().digest == build().digest


@pytest.mark.unit
def test_qx_rejects_non_hermitian_hamiltonian():
    non_hermitian = np.array([[0.0, 1.0], [0.0, 0.0]], dtype=np.complex128)
    with pytest.raises(QXValidationError, match="Hermitian"):
        QXCommandBuffer().set_hamiltonian(non_hermitian)


@pytest.mark.unit
def test_qx_rejects_strong_measurement_at_contract_boundary():
    with pytest.raises(QXValidationError, match="0 < epsilon <= 0.01"):
        QXCommandBuffer().weak_measure(_pauli_z(), epsilon=0.02, probe_id="invalid")


@pytest.mark.unit
def test_qx_fails_closed_when_evolution_precedes_hamiltonian():
    buffer = QXCommandBuffer()
    buffer.allocate_cavity_region(2)
    buffer.evolve(0.1)
    buffer.seal()
    with pytest.raises(QXValidationError, match="requires a Hamiltonian"):
        QXReferenceExecutor().execute(buffer)


@pytest.mark.unit
def test_qx_fails_closed_on_dimension_mismatch():
    buffer = QXCommandBuffer()
    buffer.allocate_cavity_region(4)
    buffer.set_hamiltonian(_pauli_z())
    buffer.seal()
    with pytest.raises(QXValidationError, match="does not match cavity dimension"):
        QXReferenceExecutor().execute(buffer)


@pytest.mark.unit
def test_qx_requires_seal_and_prevents_post_seal_mutation():
    buffer = QXCommandBuffer().allocate_cavity_region(2)
    with pytest.raises(QXValidationError, match="sealed"):
        QXReferenceExecutor().execute(buffer)
    buffer.seal()
    with pytest.raises(QXValidationError, match="immutable"):
        buffer.synchronize("late-event")
