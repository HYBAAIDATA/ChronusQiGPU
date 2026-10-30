"""Drop-in contract gates. Native integration tests use real shipped engines.

Lifecycle race tests use controlled Events/futures (unit evidence only).
"""

from concurrent.futures import Future
from dataclasses import replace
from fractions import Fraction
from threading import Event
from types import SimpleNamespace
import json
import pytest
from turing_universal_quantum_computer import (
    QuantumPipeline,
    AdvancedQuantumPipeline,
    PipelineConfig,
    ParameterBindings,
    ParameterSpec,
    FiniteAnsatz,
    PauliZ,
    JobStatus,
)
from turing_universal_quantum_computer.backends.base import Program, Operation
from turing_universal_quantum_computer.contracts import CircuitIR, ExecutionRequest
from turing_universal_quantum_computer.exceptions import (
    CapabilityError,
    CompilationError,
    ConfigurationError,
    IdempotencyConflictError,
    JobExecutionError,
    JobTimeoutError,
    ParameterValidationError,
    ResultValidationError,
)
from turing_universal_quantum_computer.native_adapter import (
    NativeBackend,
    NativeJob,
    NativeCompiler,
    exact_z,
)
from turing_universal_quantum_computer.optimizer import exact_less


def family():
    return FiniteAnsatz.from_builder(
        (ParameterSpec("choice", (0, 1, 2)),),
        lambda p: [Program(1), Program(1).then("h", 0), Program(1).then("x", 0)][int(p.values[0])],
    )


@pytest.mark.parametrize("backend", ["exact_algebraic", "stabilizer"])
@pytest.mark.parametrize("gate,value", [(None, 1.0), ("h", 0.0), ("x", -1.0)])
def test_real_native_z(backend, gate, value):
    program = Program(1) if gate is None else Program(1).then(gate, 0)
    with QuantumPipeline(PipelineConfig(backend=backend)) as pipeline:
        estimate = pipeline.estimate(program, observable=PauliZ(0))
        assert estimate.value == value
        assert estimate.standard_error == 0
        assert estimate.shots is None
        envelope = estimate.job_result.report()
        report = envelope["pipeline_report"]
        assert report["verdict"] == "PASS"
        assert report["result"]["truth_class"] == "exact"
        assert report["result"]["measured_qpu"] is False
        assert report["certificate"] and report["witness"]
        assert envelope["implementation_hash"]
        assert envelope["runtime_versions"]["python"]
        assert pipeline.get_job(estimate.job_result.job_id).status() == JobStatus.SUCCEEDED


def test_real_radical_z():
    with QuantumPipeline() as p:
        e = p.estimate(Program(1).then("h", 0).then("t", 0).then("h", 0), observable=PauliZ(0))
        assert e.exact_coefficients == ("0", "1/2")
        assert e.value == pytest.approx(2**-0.5)


@pytest.mark.parametrize("backend", ["exact_algebraic", "stabilizer"])
def test_real_sampling(backend):
    with QuantumPipeline(PipelineConfig(backend=backend, shots=500, seed=13)) as p:
        a = p.estimate(Program(2).then("h", 1), observable=PauliZ(1))
        b = p.estimate(Program(2).then("h", 1), observable=PauliZ(1))
        assert a.value == b.value
        assert abs(a.value) < 0.15
        assert a.standard_error == pytest.approx(((1 - a.value * a.value) / 499) ** 0.5)
        assert "not_confidence_bound" in a.uncertainty_method
        assert a.exact_coefficients == ("0", "0")


@pytest.mark.parametrize("backend", ["exact_algebraic", "stabilizer"])
def test_real_readout_semantics(backend):
    with QuantumPipeline(PipelineConfig(backend=backend, shots=10)) as p:
        counts = p.run(Program(2).then("x", 0), readout=(0, 1)).report()["pipeline_report"][
            "result"
        ]["payload"]["counts"]
        assert counts == {"10": 10}


def test_wide_tableau_no_dense_fallback():
    with QuantumPipeline(PipelineConfig(max_amplitudes=4)) as p:
        a = p.compile(Program(24).then("h", 0).then("cx", 0, 23))
        assert a.backend_id == "stabilizer"
        e = p.estimate(a.ir, observable=PauliZ(23))
        assert e.value == 0
        assert e.job_result.report()["pipeline_report"]["result"]["materialised"] is False


def test_finite_vqe_real_minimum_and_limit():
    f = family()
    start = ParameterBindings(("choice",), (0,))
    with QuantumPipeline() as p:
        r = p.run_vqe(f, start, observable=PauliZ(0))
        assert r.converged and r.termination_reason == "finite_domain_exhausted"
        assert r.parameters.values == (2.0,) and r.objective_value == -1
        assert r.iterations == 3 and len(r.history) == 3
        limited = p.run_vqe(f, start, observable=PauliZ(0), max_iterations=1)
        assert not limited.converged and limited.termination_reason == "iteration_limit"
        assert limited.parameters == start


def test_initial_candidate_first():
    with QuantumPipeline() as p:
        r = p.run_vqe(
            family(), ParameterBindings(("choice",), (2,)), observable=PauliZ(0), max_iterations=1
        )
        assert r.history[0].parameters.values == (2.0,)


def test_whole_family_admitted_before_execution(monkeypatch):
    f = FiniteAnsatz.from_builder(
        (ParameterSpec("choice", (0, 1)),),
        lambda p: Program(1) if p.values == (0,) else Program(1).then("rx", 0),
    )
    with QuantumPipeline() as p:
        monkeypatch.setattr(p.estimator, "estimate", lambda r: pytest.fail("must not execute"))
        with pytest.raises(CapabilityError):
            p.run_vqe(f, ParameterBindings(("choice",), (0,)), observable=PauliZ(0))


def test_compile_never_executes(monkeypatch):
    from turing_universal_quantum_computer.pipeline import VQCPipeline

    monkeypatch.setattr(VQCPipeline, "run", lambda *a: pytest.fail("compile submitted a job"))
    from turing_universal_quantum_computer.backends.algebraic import ExactFieldBackend

    monkeypatch.setattr(
        ExactFieldBackend, "execute", lambda *a, **k: pytest.fail("compile evolved a state")
    )
    with QuantumPipeline() as p:
        assert p.compile(Program(1).then("h", 0)).source_hash


@pytest.mark.parametrize(
    "kwargs",
    [
        {"shots": 0},
        {"shots": True},
        {"shots": 2.5},
        {"max_amplitudes": False},
        {"max_amplitudes": -1},
        {"job_timeout_seconds": float("nan")},
        {"job_timeout_seconds": float("inf")},
        {"job_timeout_seconds": 0},
        {"seed": True},
        {"seed": -1},
        {"seed": 2**32},
        {"replay": True},
        {"differential": 1},
    ],
)
def test_config_validation(kwargs):
    with pytest.raises(ConfigurationError):
        PipelineConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"backend": "qpu"},
        {"backend": "statevector"},
        {"error_management": "qec"},
        {"error_management": "mitigation"},
        {"execution_mode": "fault_tolerant"},
        {"execution_mode": "nisq"},
        {"execution_mode": "simulation"},
    ],
)
def test_fail_closed_configuration(kwargs):
    with pytest.raises(CapabilityError):
        PipelineConfig(**kwargs)


@pytest.mark.parametrize("values", [(float("nan"),), (float("inf"),), (True,), ("1",)])
def test_nonfinite_or_nonreal_bindings(values):
    with pytest.raises(ParameterValidationError):
        ParameterBindings(("x",), values)


def test_parameter_identity():
    schema = (ParameterSpec("a", (0, 1)), ParameterSpec("b", (0, 1)))
    with pytest.raises(ParameterValidationError):
        ParameterBindings(("b", "a"), (0, 0)).validate(schema)
    assert ParameterBindings.from_mapping(schema, {"b": 1, "a": 0}) == ParameterBindings(
        ("a", "b"), (0, 1)
    )
    with pytest.raises(ParameterValidationError):
        ParameterBindings.from_mapping(schema, {"a": 0})
    with pytest.raises(ParameterValidationError):
        ParameterBindings(("a", "b"), (2, 0)).validate(schema)


@pytest.mark.parametrize(
    "spec",
    [
        ("x", ()),
        ("x", (0, 0)),
        ("x", (float("nan"),)),
        ("", (0,)),
        ("x", (0,), 2, 1),
        ("x", (0,), 1, None),
        ("x", (0,), float("nan"), None),
    ],
)
def test_invalid_domains(spec):
    with pytest.raises(ParameterValidationError):
        ParameterSpec(*spec)


def test_defensive_copy_no_mutable_numpy():
    values = [0, 1]
    s = ParameterSpec("x", values)
    values.append(2)
    assert s.values == (0.0, 1.0)
    operations = [Operation("h", [0])]
    ir = CircuitIR(Program(1, operations))
    operations.clear()
    assert ir.program.operations == (Operation("h", (0,)),)
    bindings = ParameterBindings(["x"], [0])
    assert isinstance(bindings.values, tuple)


@pytest.mark.parametrize(
    "program",
    [
        Program(1).then("rx", 0),
        Program(2).then("cx", 0, 0),
        Program(2).then("x", 0, 1),
        Program(1).then("cx", 0),
    ],
)
def test_invalid_or_unsupported_gates(program):
    with QuantumPipeline() as p:
        with pytest.raises((CompilationError, CapabilityError)):
            p.compile(program)


def test_backend_target_mismatch_before_submit():
    config = PipelineConfig(backend="exact_algebraic")
    a = NativeCompiler(config).compile(CircuitIR(Program(1)))
    b = NativeBackend(PipelineConfig(backend="stabilizer"))
    try:
        with pytest.raises(CompilationError):
            b.submit(ExecutionRequest(a))
        assert not b._jobs
    finally:
        b.close()


def test_artifact_tamper_and_layout():
    with QuantumPipeline() as p:
        a = p.compile(Program(2))
        with pytest.raises(ParameterValidationError):
            replace(a, source_hash="bad")
        with pytest.raises(ParameterValidationError):
            replace(a, layout=((0, 1), (1, 0)))
        with pytest.raises(CompilationError):
            p.backend.submit(ExecutionRequest(replace(a, implementation_hash="bad")))


def test_bound_artifact_cannot_be_reused_for_other_values():
    with QuantumPipeline() as p:
        a = p.compile(family(), ParameterBindings(("choice",), (0,)))
        with pytest.raises(ParameterValidationError):
            ExecutionRequest(a, ParameterBindings(("choice",), (1,)))


def test_sampling_requires_readout_and_rejects_reordering():
    with QuantumPipeline(PipelineConfig(backend="stabilizer", shots=10)) as p:
        with pytest.raises(CapabilityError):
            p.run(Program(2))
        with pytest.raises(CapabilityError):
            p.run(Program(2), readout=(1, 0))


def test_idempotency_real_job():
    with QuantumPipeline() as p:
        a = p.submit(Program(1), idempotency_key="same")
        b = p.submit(Program(1), idempotency_key="same")
        assert a is b and a.result().job_id == a.job_id
        with pytest.raises(IdempotencyConflictError):
            p.submit(Program(1).then("x", 0), idempotency_key="same")
        assert p.submit(Program(1)).job_id != a.job_id


def test_registry_bound_unknown_job_and_close():
    b = NativeBackend(PipelineConfig(), max_jobs=1)
    req = ExecutionRequest(NativeCompiler(b.config).compile(CircuitIR(Program(1))))
    b.submit(req).result()
    with pytest.raises(CapabilityError):
        b.submit(req)
    with pytest.raises(JobExecutionError):
        b.get_job("missing")
    b.close()
    with pytest.raises(JobExecutionError):
        b.submit(req)


def test_timeout_running_cancelled_and_failed_unit():
    f = Future()
    job = NativeJob("unit", f)
    assert job.status() == JobStatus.QUEUED
    with pytest.raises(JobTimeoutError) as exc:
        job.result(0)
    assert exc.value.job_id == "unit" and job.status() == JobStatus.QUEUED
    assert job.cancel() and job.status() == JobStatus.CANCELLED
    with pytest.raises(JobExecutionError):
        job.result()
    f = Future()
    job = NativeJob("unit-running", f)
    f.set_running_or_notify_cancel()
    assert job.status() == JobStatus.RUNNING and not job.cancel()
    f.set_result(None)
    assert job.status() == JobStatus.SUCCEEDED
    f = Future()
    job = NativeJob("unit-failed", f)
    f.set_exception(JobExecutionError("diagnostic", job_id="unit-failed"))
    assert job.status() == JobStatus.FAILED
    with pytest.raises(JobExecutionError):
        job.result()


def test_operational_failure_retains_job_id(monkeypatch):
    from turing_universal_quantum_computer.pipeline import VQCPipeline

    monkeypatch.setattr(
        VQCPipeline, "run", lambda *a: (_ for _ in ()).throw(RuntimeError("unit-failure"))
    )
    with QuantumPipeline() as p:
        j = p.submit(Program(1))
        with pytest.raises(JobExecutionError) as exc:
            j.result()
        assert exc.value.job_id == j.job_id and "unit-failure" in str(exc.value)
        assert j.status() == JobStatus.FAILED


def test_refusal_is_not_promoted(monkeypatch):
    from turing_universal_quantum_computer.pipeline import VQCPipeline

    r = SimpleNamespace(
        verdict="GATED", refusals=("unit-no-evidence",), as_dict=lambda: {"verdict": "GATED"}
    )
    monkeypatch.setattr(VQCPipeline, "run", lambda *a: r)
    with QuantumPipeline() as p:
        with pytest.raises(JobExecutionError) as exc:
            p.run(Program(1))
        assert json.loads(exc.value.report_json)["verdict"] == "GATED"


def test_result_is_fresh_copy():
    with QuantumPipeline() as p:
        r = p.run(Program(1))
        data = r.report()
        data["pipeline_report"]["verdict"] = "FAKE"
        assert r.report()["pipeline_report"]["verdict"] == "PASS"


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -1, True])
def test_bad_wait_timeout(timeout):
    with pytest.raises(ConfigurationError):
        NativeJob("unit", Future()).result(timeout)


def test_finite_family_budget():
    with pytest.raises(ParameterValidationError):
        FiniteAnsatz.from_builder(
            (ParameterSpec("x", tuple(range(10))),), lambda p: Program(1), max_candidates=2
        )
    with pytest.raises(ParameterValidationError):
        FiniteAnsatz((ParameterSpec("x", (0, 1)),), (Program(1),))


def test_continuous_vqe_shots_and_unknown_observable_refused():
    with QuantumPipeline() as p:
        with pytest.raises(CapabilityError):
            p.run_vqe(object(), ParameterBindings(), observable=PauliZ(0))
        with pytest.raises(CapabilityError):
            p.estimate(Program(1), observable=object())
        with pytest.raises(ParameterValidationError):
            p.estimate(Program(1), observable=PauliZ(1))
    with QuantumPipeline(PipelineConfig(shots=1)) as p:
        with pytest.raises(CapabilityError):
            p.estimate(Program(1), observable=PauliZ(0))
    with QuantumPipeline(PipelineConfig(shots=10)) as p:
        with pytest.raises(CapabilityError):
            p.run_vqe(family(), ParameterBindings(("choice",), (0,)), observable=PauliZ(0))


def test_exact_comparison_near_float_tie():
    # Pell convergent 886731088897/627013566048 is above sqrt(2).
    a = SimpleNamespace(exact_coefficients=("886731088897/627013566048", "0"))
    b = SimpleNamespace(exact_coefficients=("0", "1"))
    assert float(Fraction(a.exact_coefficients[0])) == 2**0.5
    assert exact_less(b, a) and not exact_less(a, b)


def test_exact_extractor_rejects_malformed_payload():
    with pytest.raises(ResultValidationError):
        exact_z({}, "exact_algebraic", 0)
    with pytest.raises(ResultValidationError):
        exact_z({}, "stabilizer", 0)


def test_alias_preserves_old_pipeline():
    from turing_universal_quantum_computer.pipeline import VQCPipeline

    assert QuantumPipeline is AdvancedQuantumPipeline
    assert VQCPipeline is not QuantumPipeline


def test_operational_failure_not_returned_as_nonconvergence(monkeypatch):
    with QuantumPipeline() as p:

        def fail(request):
            raise JobExecutionError("unit-evaluation-failure", job_id="known-job")

        monkeypatch.setattr(p.estimator, "estimate", fail)
        with pytest.raises(JobExecutionError) as exc:
            p.run_vqe(family(), ParameterBindings(("choice",), (0,)), observable=PauliZ(0))
        assert exc.value.job_id == "known-job"


def test_injected_components_are_used():
    class RecordingCompiler:
        def __init__(self):
            self.calls = []

        def compile(self, ir):
            self.calls.append(ir)
            return NativeCompiler(PipelineConfig()).compile(ir)

    compiler = RecordingCompiler()
    with QuantumPipeline(compiler=compiler) as p:
        p.estimate(Program(1), observable=PauliZ(0))
        assert len(compiler.calls) == 1


def test_no_error_plan_is_explicit():
    from turing_universal_quantum_computer.interfaces import NoErrorManagement

    request = ExecutionRequest(NativeCompiler(PipelineConfig()).compile(CircuitIR(Program(1))))
    plan = NoErrorManagement().prepare(request)
    assert plan.method == "none" and plan.requests == (request,)


def test_real_job_timeout_and_queued_cancel(monkeypatch):
    # Controlled scheduling; the first job still executes the real canonical engine.
    from turing_universal_quantum_computer.pipeline import VQCPipeline

    original = VQCPipeline.run
    entered = Event()
    release = Event()

    def controlled(self, request):
        entered.set()
        assert release.wait(5), "unit scheduling guard expired"
        return original(self, request)

    monkeypatch.setattr(VQCPipeline, "run", controlled)
    with QuantumPipeline() as p:
        try:
            first = p.submit(Program(1), idempotency_key="controlled-first")
            assert entered.wait(5)
            assert first.status() == JobStatus.RUNNING
            with pytest.raises(JobTimeoutError):
                first.result(0)
            assert not first.cancel()
            queued = p.submit(Program(1).then("x", 0))
            assert queued.status() == JobStatus.QUEUED
            assert p.cancel_job(queued.job_id) and queued.status() == JobStatus.CANCELLED
            assert p.submit(Program(1), idempotency_key="controlled-first") is first
        finally:
            release.set()
        assert first.result(5).job_id == first.job_id
        assert first.status() == JobStatus.SUCCEEDED


def test_bad_result_target_rejected(monkeypatch):
    from turing_universal_quantum_computer.pipeline import VQCPipeline

    original = VQCPipeline.run

    def tamper(self, request):
        report = original(self, request)
        data = dict(report.result)
        data["backend"] = "not-the-target"
        return replace(report, result=data)

    monkeypatch.setattr(VQCPipeline, "run", tamper)
    with QuantumPipeline() as p:
        with pytest.raises(ResultValidationError) as exc:
            p.run(Program(1))
        assert exc.value.job_id and exc.value.report_json


def test_explicit_width_resource_limit_before_submission():
    with QuantumPipeline(PipelineConfig(max_qubits=4)) as p:
        with pytest.raises(CapabilityError):
            p.compile(Program(5))
        assert not p.backend._jobs


def test_exact_dependency_import_does_not_require_chronus():
    import os
    import subprocess
    import sys

    code = """
import importlib.abc
import sys
class NoChronus(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'chronus' or fullname.startswith('chronus.'):
            raise AssertionError('unexpected mining dependency: '+fullname)
sys.meta_path.insert(0, NoChronus())
from kellogg.exact_field import sqrt_f
from turing_universal_quantum_computer import QuantumPipeline, PauliZ
from turing_universal_quantum_computer.backends.base import Program
with QuantumPipeline() as p:
    assert p.estimate(Program(1), observable=PauliZ(0)).value == 1.0
"""
    env = dict(os.environ)
    # Reuse the actual package origins, not a fake module or namespace shim.
    import kellogg
    import tempfile
    from pathlib import Path
    import turing_universal_quantum_computer as t

    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(t.__file__).parent.parent), str(Path(kellogg.__file__).parent.parent)]
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
