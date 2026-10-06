"""Emit deterministic public-VQC certificate and witness digests."""

from turing_universal_quantum_computer.backends import Program, execute_certified


program = Program(3).then("h", 0).then("cx", 0, 1).then("t", 2)
execution = execute_certified(program, shots=128, seed=17)
print(execution.certificate.certificate_digest)
print(execution.certificate.attestation)
print(execution.witness.digest())
