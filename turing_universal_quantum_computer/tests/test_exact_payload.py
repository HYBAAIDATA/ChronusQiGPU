"""Exact-only payloads preserve default display compatibility and certificate replay."""

import pytest

from turing_universal_quantum_computer.backends import ExactStatevector, Program, execute_certified
from turing_universal_quantum_computer.certificates import replay_computation_certificate
from turing_universal_quantum_computer.backends import execute


def test_default_table_retains_display_fields_and_exact_table_omits_them():
    state = ExactStatevector(1)
    default = state.amplitude_table()
    exact = state.amplitude_table(include_approximation=False)
    assert "probability_approx" in default[0]
    assert "amplitude_approx" in default[0]
    assert {k: v for k, v in default[0].items() if not k.endswith("_approx")} == exact[0]
    with pytest.raises(ValueError, match="boolean"):
        state.amplitude_table(include_approximation=1)


def test_exact_payload_is_certificate_bound_and_replays():
    program = Program(2).then("h", 0).then("cx", 0, 1).then("t", 1)
    run = execute_certified(program, exact_payload=True)
    assert all("probability_approx" not in row for row in run.result.payload["amplitudes"])
    replayed = replay_computation_certificate(
        program, run.certificate, execute, options={"exact_payload": True}
    )
    assert replayed.certificate == run.result.certificate
    assert execute_certified(program).certificate != run.certificate
    with pytest.raises(ValueError, match="boolean"):
        execute_certified(program, exact_payload="true")
