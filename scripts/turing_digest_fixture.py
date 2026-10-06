"""Emit the deterministic cross-version Turing certificate fixture."""

from turing_universal_quantum_computer.turing_core.specification import (
    Direction,
    ExactField,
    MachineDescription,
    MachineType,
    Transition,
    execute,
)


machine = MachineDescription(
    name="ci-unary-increment",
    machine_type=MachineType.CLASSICAL_DETERMINISTIC,
    field=ExactField.GF2,
    states=("scan", "accept"),
    alphabet=("1", "_"),
    blank="_",
    start_state="scan",
    accept_states=("accept",),
    reject_states=(),
    transitions=(
        Transition("scan", "1", "scan", "1", Direction.RIGHT),
        Transition("scan", "_", "accept", "1", Direction.STAY),
    ),
)

print(execute(machine, tuple("11111"), max_steps=16).certificate.certificate_digest)
