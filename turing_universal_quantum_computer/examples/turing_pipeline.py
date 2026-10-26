"""Run after installing the TURING distribution; no cloud credentials."""

from turing_universal_quantum_computer import (
    TuringPipeline,
    PipelineConfig,
    PauliZ,
    FiniteAnsatz,
    ParameterSpec,
    ParameterBindings,
)
from turing_universal_quantum_computer.backends.base import Program

# This is an exact finite family, not continuous-angle ansatz synthesis.
ansatz = FiniteAnsatz.from_builder(
    (ParameterSpec("choice", values=(0, 1, 2)),),
    lambda bound: (
        Program(1),
        Program(1).then("h", 0),
        Program(1).then("x", 0),
    )[int(bound.values[0])],
)

with TuringPipeline(PipelineConfig(backend="auto")) as pipeline:
    bell = Program(2).then("h", 0).then("cx", 0, 1)
    artifact = pipeline.compile(bell)  # admission/provenance only; no job
    estimate = pipeline.estimate(bell, observable=PauliZ(0))
    print("Bell <Z0>:", estimate.value, estimate.exact_value)
    result = pipeline.run_vqe(
        ansatz,
        ParameterBindings.from_mapping(ansatz.parameters, {"choice": 0}),
        observable=PauliZ(0),
        max_iterations=3,
    )
    print("Finite energy:", result.objective_value)
    print("Converged:", result.converged, result.termination_reason)
    print("Parameters:", result.parameters)
    job = pipeline.submit(bell, idempotency_key="bell-demonstration-1")
    print("Job:", job.job_id, job.result().report()["pipeline_report"]["verdict"])
