"""Executable software qualification: exact oracles, real lifecycle, controlled faults.

Bounded concurrent tests are regression evidence, not proof of absence of races.
Test doubles only control failures/scheduling; successful paths use native TURING.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction
import os
import subprocess
import sys
from threading import Event, enumerate as threads
from types import SimpleNamespace

from hypothesis import given, settings, strategies as st
import pytest
from turing_universal_quantum_computer import (
    TuringPipeline,
    PipelineConfig,
    PauliZ,
    ParameterSpec,
    ParameterBindings,
    JobStatus,
)
from turing_universal_quantum_computer.backends.base import Program
from turing_universal_quantum_computer.exceptions import (
    CapabilityError,
    JobExecutionError,
    JobTimeoutError,
    ParameterValidationError,
    ResultValidationError,
)
from turing_universal_quantum_computer.pipeline import VQCPipeline, VQCRequest
from turing_universal_quantum_computer.optimizer import exact_less

GENERATIVE = settings(max_examples=20, derandomize=True, database=None, deadline=None)


@GENERATIVE
@given(st.lists(st.sampled_from(["i", "x", "y", "z", "s", "sdg"]), max_size=10))
def test_generated_basis_parity_independent_oracle(gates):
    # X and Y flip a basis bit; diagonal gates change phase but not Z.
    expected = "-1" if sum(g in {"x", "y"} for g in gates) % 2 else "1"
    program = Program(1)
    for gate in gates:
        program = program.then(gate, 0)
    for backend in ("exact_algebraic", "stabilizer"):
        with TuringPipeline(PipelineConfig(backend=backend)) as pipeline:
            estimate = pipeline.estimate(program, observable=PauliZ(0))
            assert estimate.exact_coefficients == (expected, "0")
            assert estimate.standard_error == 0.0
            assert estimate.uncertainty_method == "analytic_exact_no_sampling"


@GENERATIVE
@given(st.lists(st.sampled_from(["h", "x", "y", "z", "s", "sdg", "t", "tdg"]), max_size=8))
def test_generated_gate_inverse_is_exact_identity(gates):
    inverse = {"s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}
    program = Program(1)
    for gate in gates:
        program = program.then(gate, 0)
    for gate in reversed(gates):
        program = program.then(inverse.get(gate, gate), 0)
    with TuringPipeline(PipelineConfig(backend="exact_algebraic")) as pipeline:
        result = pipeline.run(program).report()["pipeline_report"]["result"]["payload"]
    amplitudes = result["state"]["amplitudes"]
    assert [Fraction(a["re_p"]) for a in amplitudes] == [1, 0]
    assert all(Fraction(a[k]) == 0 for a in amplitudes for k in ("re_q", "im_p", "im_q"))


@GENERATIVE
@given(
    st.integers(-100, 100), st.integers(-100, 100), st.integers(-100, 100), st.integers(-100, 100)
)
def test_exact_comparison_agrees_with_independent_symbolic_order(a, b, c, d):
    # SymPy is an independent symbolic oracle, not the comparator under test.
    from sympy import Rational, sqrt

    left = SimpleNamespace(exact_coefficients=(str(a), str(b)))
    right = SimpleNamespace(exact_coefficients=(str(c), str(d)))
    expected = bool(Rational(a - c) + Rational(b - d) * sqrt(2) < 0)
    assert exact_less(left, right) is expected
    if (a, b) == (c, d):
        assert not exact_less(right, left)


@GENERATIVE
@given(st.integers(min_value=-1000, max_value=1000))
def test_generated_out_of_domain_values_are_rejected(value):
    spec = (ParameterSpec("choice", (0, 1)),)
    binding = ParameterBindings(("choice",), (value,))
    if value in (0, 1):
        binding.validate(spec)
    else:
        with pytest.raises(ParameterValidationError):
            binding.validate(spec)


@pytest.mark.parametrize("backend", ["exact_algebraic", "stabilizer"])
@pytest.mark.parametrize(
    "program", [Program(1), Program(1).then("x", 0), Program(2).then("h", 0).then("cx", 0, 1)]
)
def test_canonical_vs_facade_payload_parity(backend, program):
    # Additive facade compatibility, not a promise of identical wrapper types.
    direct = VQCPipeline().run(VQCRequest(program=program, prefer_backend=backend, seed=1234))
    with TuringPipeline(PipelineConfig(backend=backend)) as facade:
        wrapped = facade.run(program).report()["pipeline_report"]
    assert direct.verdict == wrapped["verdict"] == "PASS"
    assert direct.result == wrapped["result"]
    assert direct.certificate == wrapped["certificate"]


def test_concurrent_idempotent_submission_executes_once(monkeypatch):
    entered, release = Event(), Event()
    original = VQCPipeline.run
    executions = []

    def controlled(self, request):
        executions.append(request.program.digest())
        entered.set()
        assert release.wait(10)
        return original(self, request)

    monkeypatch.setattr(VQCPipeline, "run", controlled)
    with TuringPipeline() as pipeline:
        try:
            with ThreadPoolExecutor(max_workers=8) as callers:
                jobs = list(
                    callers.map(
                        lambda _: pipeline.submit(Program(1), idempotency_key="shared-request"),
                        range(24),
                    )
                )
            assert entered.wait(10)
            assert len({job.job_id for job in jobs}) == 1
            assert len(executions) == 1
        finally:
            release.set()
        assert jobs[0].result(10).job_id == jobs[0].job_id


def test_bounded_concurrent_instances_are_isolated():
    before = {t.ident for t in threads() if t.name.startswith("turing-vqc")}

    def consumer(index):
        with TuringPipeline() as pipeline:
            program = Program(1).then("x", 0) if index % 2 else Program(1)
            result = pipeline.estimate(program, observable=PauliZ(0))
            return result.exact_coefficients, result.job_result.job_id

    with ThreadPoolExecutor(max_workers=6) as callers:
        values = list(callers.map(consumer, range(24)))
    assert [v[0] for v in values] == [("-1" if i % 2 else "1", "0") for i in range(24)]
    assert len({v[1] for v in values}) == 24
    assert {t.ident for t in threads() if t.name.startswith("turing-vqc")} == before


def test_context_exception_drains_jobs_and_rejects_reuse():
    before = {t.ident for t in threads() if t.name.startswith("turing-vqc")}
    pipeline = TuringPipeline()
    with pytest.raises(RuntimeError, match="consumer-failure"):
        with pipeline:
            job = pipeline.submit(Program(1))
            raise RuntimeError("consumer-failure")
    assert job.status() == JobStatus.SUCCEEDED
    assert job.result(0).job_id == job.job_id
    with pytest.raises(JobExecutionError, match="closed"):
        pipeline.submit(Program(1))
    pipeline.close()  # repeated close is safe
    assert {t.ident for t in threads() if t.name.startswith("turing-vqc")} == before


def test_timeout_recovery_never_resubmits(monkeypatch):
    entered, release = Event(), Event()
    original = VQCPipeline.run
    calls = []

    def controlled(self, request):
        calls.append(1)
        entered.set()
        assert release.wait(10)
        return original(self, request)

    monkeypatch.setattr(VQCPipeline, "run", controlled)
    with TuringPipeline() as pipeline:
        try:
            job = pipeline.submit(Program(1), idempotency_key="recover")
            assert entered.wait(10)
            with pytest.raises(JobTimeoutError) as error:
                job.result(0)
            assert error.value.job_id == job.job_id
            assert not job.cancel()  # truthful non-interruptible running computation
            assert pipeline.submit(Program(1), idempotency_key="recover") is job
        finally:
            release.set()
        assert pipeline.get_job(job.job_id).result(10).job_id == job.job_id
        assert len(calls) == 1


def test_worker_failure_is_typed_and_next_job_recovers(monkeypatch):
    original = VQCPipeline.run
    count = 0

    def once(self, request):
        nonlocal count
        count += 1
        if count == 1:
            raise ArithmeticError("injected arithmetic failure")
        return original(self, request)

    monkeypatch.setattr(VQCPipeline, "run", once)
    with TuringPipeline() as pipeline:
        first = pipeline.submit(Program(1))
        with pytest.raises(JobExecutionError) as failure:
            first.result(10)
        assert failure.value.job_id == first.job_id
        assert first.status() == JobStatus.FAILED
        assert pipeline.estimate(Program(1), observable=PauliZ(0)).exact_coefficients == ("1", "0")


@pytest.mark.parametrize("mutation", ["source", "certificate", "witness"])
def test_malformed_execution_evidence_fails_closed(monkeypatch, mutation):
    original = VQCPipeline.run

    def corrupt(self, request):
        report = original(self, request)
        if mutation == "source":
            payload = dict(report.result)
            payload["program_digest"] = "wrong-source"
            return replace(report, result=payload)
        return replace(report, **{mutation: None})

    monkeypatch.setattr(VQCPipeline, "run", corrupt)
    with TuringPipeline() as pipeline:
        with pytest.raises(ResultValidationError) as failure:
            pipeline.run(Program(1))
        assert failure.value.job_id and failure.value.report_json


@pytest.mark.parametrize(
    "kwargs",
    [
        {"error_management": "qldpc"},
        {"backend": "unconfigured"},
        {"execution_mode": "fault_tolerant"},
    ],
)
def test_unsupported_configuration_allocates_no_worker(kwargs):
    before = {t.ident for t in threads()}
    with pytest.raises(CapabilityError):
        TuringPipeline(PipelineConfig(**kwargs))
    assert {t.ident for t in threads()} == before


def test_import_boundary_under_concurrent_initialization():
    import kellogg
    import turing_universal_quantum_computer as turing
    from pathlib import Path

    code = """
import importlib.abc, sys
from concurrent.futures import ThreadPoolExecutor
class DenyMining(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'chronus' or fullname.startswith('chronus.'):
            raise AssertionError('mining dependency entered exact import boundary')
sys.meta_path.insert(0, DenyMining())
def load(_):
    from kellogg.exact_tensor import F4
    from kellogg.exact_field import sqrt_f
    from turing_universal_quantum_computer import TuringPipeline
    return (F4, sqrt_f, TuringPipeline)
with ThreadPoolExecutor(max_workers=8) as pool:
    values = list(pool.map(load, range(32)))
assert all(all(a is b for a,b in zip(values[0], item)) for item in values)
assert not any(k == 'chronus' or k.startswith('chronus.') for k in sys.modules)
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(turing.__file__).parent.parent), str(Path(kellogg.__file__).parent.parent)]
    )
    for _ in range(3):
        done = subprocess.run(
            [sys.executable, "-c", code],
            cwd="/tmp",
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert done.returncode == 0, done.stderr


def test_non_normalized_exact_state_is_rejected():
    from turing_universal_quantum_computer.native_adapter import exact_z

    amplitude = {"re_p": "0", "re_q": "0", "im_p": "0", "im_q": "0"}
    payload = {
        "state": {
            "schema": "turing.vqc.exact_statevector.v1",
            "n_qubits": 1,
            "amplitudes": [dict(amplitude), dict(amplitude)],
        }
    }
    with pytest.raises(ResultValidationError, match="not normalized"):
        exact_z(payload, "exact_algebraic", 0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"backend": []},
        {"execution_mode": {}},
        {"error_management": None},
        {"custody_dir": 123},
        {"custody_dir": ""},
    ],
)
def test_malformed_configuration_is_typed_before_allocating_workers(kwargs):
    from turing_universal_quantum_computer.exceptions import ConfigurationError

    before = {t.ident for t in threads()}
    with pytest.raises(ConfigurationError):
        PipelineConfig(**kwargs)
    assert {t.ident for t in threads()} == before


@pytest.mark.parametrize("configuration", [{}, "auto", object()])
def test_facade_rejects_non_config_objects(configuration):
    from turing_universal_quantum_computer.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        TuringPipeline(configuration)


@pytest.mark.parametrize("names,values", [(None, ()), ((), None), ((["unhashable"],), (0,))])
def test_malformed_bindings_raise_typed_validation(names, values):
    with pytest.raises(ParameterValidationError):
        ParameterBindings(names, values)


def test_noniterable_finite_domain_raises_typed_validation():
    with pytest.raises(ParameterValidationError):
        ParameterSpec("choice", None)
