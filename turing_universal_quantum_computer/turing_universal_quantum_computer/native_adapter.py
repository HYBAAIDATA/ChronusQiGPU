"""Public native adapter; execution stays on the canonical VQCPipeline.

This adapter does not bypass admission, generate hardware evidence, or create
private custody. Enterprise callers must inject a backend that invokes their
CompositionRoot shared binding; local custody is not enterprise acceptance.
"""

from __future__ import annotations
from concurrent.futures import (
    ThreadPoolExecutor,
    Future,
    TimeoutError as FutureTimeout,
    CancelledError,
)
from dataclasses import asdict
from fractions import Fraction
from math import isfinite, sqrt
from threading import Lock
import json
from uuid import uuid4
from pathlib import Path
from hashlib import sha256
from importlib.metadata import version, PackageNotFoundError
import platform
from .backends import select_backend
from .backends.algebraic import SUPPORTED_GATES
from .config import PipelineConfig
from .interfaces import Backend
from .contracts import (
    BackendCapabilities,
    CircuitIR,
    CompiledArtifact,
    Estimate,
    ExecutionRequest,
    JobResult,
    JobStatus,
    canonical_json,
)
from .exceptions import (
    CapabilityError,
    CompilationError,
    ConfigurationError,
    IdempotencyConflictError,
    JobExecutionError,
    JobTimeoutError,
    ResultValidationError,
)
from .pipeline import VQCPipeline, VQCRequest


def validate_timeout(timeout):
    if timeout is not None and (
        type(timeout) not in (int, float) or not isfinite(timeout) or timeout < 0
    ):
        raise ConfigurationError("wait timeout must be finite and nonnegative or None")


def select_native(ir: CircuitIR, config: PipelineConfig):
    if ir.program.n_qubits > config.max_qubits:
        raise CapabilityError("logical width exceeds configured API resource budget")
    for operation in ir.program.operations:
        if operation.gate not in SUPPORTED_GATES:
            raise CapabilityError(
                f"Unsupported native gate: {operation.gate}; no angle rounding or lowering is configured"
            )
        arity = 2 if operation.gate in {"cx", "cnot", "cz", "swap"} else 1
        if len(operation.qubits) != arity or len(set(operation.qubits)) != arity:
            raise CompilationError(f"invalid arity or repeated qubit for {operation.gate}")
    target = config.backend
    if target == "auto":
        target = (
            "exact_algebraic"
            if ir.program.n_qubits <= config.max_amplitudes.bit_length() - 1
            else "stabilizer"
        )
    backend, admission = select_backend(
        ir.program, prefer=target, max_amplitudes=config.max_amplitudes
    )
    if backend is None or not admission.admitted:
        raise CapabilityError(f"Native admission refused: {admission.reason}")
    available, reason = backend.available()
    if not available:
        raise CapabilityError(reason)
    return backend


def implementation_fingerprint() -> str:
    root = Path(__file__).parent
    h = sha256()
    for path in sorted(root.rglob("*.py")):
        name = path.relative_to(root).as_posix()
        h.update(name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def runtime_versions() -> dict:
    from . import __version__

    result = {"turing_source_version": __version__, "python": platform.python_version()}
    for name in ("hyba-turing-vqc", "hyba-kellogg-tensor", "numpy", "sympy"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "NOT_INSTALLED_AS_DISTRIBUTION"
    return result


class NativeCompiler:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def compile(self, circuit: CircuitIR) -> CompiledArtifact:
        if not isinstance(circuit, CircuitIR):
            raise CompilationError("expected CircuitIR")
        backend = select_native(circuit, self.config)
        return CompiledArtifact(
            circuit,
            backend.name,
            canonical_json(asdict(self.config)),
            circuit.program.digest(),
            tuple((q, q) for q in range(circuit.program.n_qubits)),
            implementation_fingerprint(),
        )


class NativeJob:
    def __init__(self, job_id: str, future: Future):
        self._job_id, self._future = job_id, future

    @property
    def job_id(self) -> str:
        return self._job_id

    def status(self) -> JobStatus:
        if self._future.cancelled():
            return JobStatus.CANCELLED
        if self._future.done():
            return JobStatus.FAILED if self._future.exception() else JobStatus.SUCCEEDED
        return JobStatus.RUNNING if self._future.running() else JobStatus.QUEUED

    def result(self, timeout: float | None = None) -> JobResult:
        validate_timeout(timeout)
        try:
            return self._future.result(timeout=timeout)
        except FutureTimeout as exc:
            raise JobTimeoutError(
                "Wait timed out; job may still be running", job_id=self.job_id
            ) from exc
        except CancelledError as exc:
            raise JobExecutionError("Job cancelled before execution", job_id=self.job_id) from exc

    def cancel(self) -> bool:
        return self._future.cancel()  # running local computations cannot be forcibly cancelled


class NativeBackend:
    def __init__(self, config: PipelineConfig, *, max_jobs: int = 1000):
        if type(max_jobs) is not int or max_jobs < 1:
            raise ConfigurationError("max_jobs must be positive")
        self.config = config
        self._max_jobs = max_jobs
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="turing-vqc")
        self._lock = Lock()
        self._jobs: dict[str, NativeJob] = {}
        self._keys: dict[str, tuple[str, str]] = {}
        self._closed = False

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            self.config.backend,
            max_qubits=self.config.max_qubits,
            max_amplitudes=self.config.max_amplitudes,
        )

    def _validate(self, request: ExecutionRequest):
        # Re-run admission, not evolution. CompiledArtifact is a value, not authority.
        expected = NativeCompiler(self.config).compile(request.artifact.ir)
        if expected != request.artifact:
            raise CompilationError(
                "artifact target/configuration/provenance mismatch; recompile explicitly"
            )
        if self.config.shots is not None and request.readout is None:
            raise CapabilityError(
                "sampled execution requires explicit readout; no silent truncation"
            )
        if request.readout is not None and request.artifact.backend_id == "stabilizer":
            from .backends.native import StabilizerBackend

            if len(request.readout) > StabilizerBackend.READOUT_LIMIT:
                raise CapabilityError("readout exceeds native tableau cost envelope")
            if request.readout != tuple(sorted(request.readout)):
                raise CapabilityError(
                    "v1 tableau adapter requires ascending readout; no silent bit reordering"
                )

    def submit(self, request: ExecutionRequest, *, idempotency_key: str | None = None) -> NativeJob:
        self._validate(request)
        if idempotency_key is not None and (
            not isinstance(idempotency_key, str) or not idempotency_key
        ):
            raise ConfigurationError("idempotency key must be a nonempty string")
        with self._lock:
            if self._closed:
                raise JobExecutionError("backend is closed")
            if idempotency_key is not None and idempotency_key in self._keys:
                fingerprint, job_id = self._keys[idempotency_key]
                if fingerprint != request.request_hash:
                    raise IdempotencyConflictError(
                        "idempotency key already identifies a different request"
                    )
                return self._jobs[job_id]
            if len(self._jobs) >= self._max_jobs:
                raise CapabilityError(
                    "process-local job registry is full; use a new backend or persistent adapter"
                )
            job_id = "turing-local-" + uuid4().hex
            job = NativeJob(job_id, self._executor.submit(self._execute, request, job_id))
            self._jobs[job_id] = job
            if idempotency_key is not None:
                self._keys[idempotency_key] = request.request_hash, job_id
            return job

    def _execute(self, request: ExecutionRequest, job_id: str) -> JobResult:
        try:
            # Marginal is supported by tableau; dense Z is derived algebraically
            # from the certified canonical amplitudes, not display probabilities.
            report = VQCPipeline().run(
                VQCRequest(
                    program=request.artifact.ir.program,
                    prefer_backend=request.artifact.backend_id,
                    max_amplitudes=self.config.max_amplitudes,
                    shots=self.config.shots,
                    seed=self.config.seed,
                    readout=request.readout,
                    marginal_of=None if request.observable is None else (request.observable.qubit,),
                    differential=self.config.differential,
                    custody=self.config.custody,
                    replay=self.config.replay,
                    custody_dir=self.config.custody_dir,
                    notes="public_api artifact=" + request.artifact.artifact_hash,
                )
            )
            encoded = canonical_json(report.as_dict())
            if report.verdict != "PASS":
                raise JobExecutionError(
                    f"Canonical pipeline returned {report.verdict}: {report.refusals}",
                    job_id=job_id,
                    report_json=encoded,
                )
            payload = report.result
            if (
                payload is None
                or payload.get("backend") != request.artifact.backend_id
                or payload.get("program_digest") != request.artifact.source_hash
            ):
                raise ResultValidationError(
                    "result target/source mismatch", job_id=job_id, report_json=encoded
                )
            if (
                payload.get("measured_qpu") is not False
                or payload.get("truth_class") != "exact"
                or not report.certificate
                or not report.witness
            ):
                raise ResultValidationError(
                    "native truth/certificate boundary failed", job_id=job_id, report_json=encoded
                )
            # Pin API context next to, not inside, the canonical pipeline report.
            envelope = {
                "api_schema": request.artifact.api_schema,
                "artifact_hash": request.artifact.artifact_hash,
                "request_hash": request.request_hash,
                "compiler": request.artifact.compiler_version,
                "implementation_hash": request.artifact.implementation_hash,
                "runtime_versions": runtime_versions(),
                "configuration": json.loads(request.artifact.config_json),
                "parameter_names": request.parameters.names,
                "parameter_values": request.parameters.values,
                "family_hash": request.artifact.ir.family_hash,
                "pipeline_report": report.as_dict(),
            }
            return JobResult(job_id, request.request_hash, canonical_json(envelope))
        except JobExecutionError:
            raise
        except Exception as exc:
            raise JobExecutionError(
                f"Native execution raised {type(exc).__name__}: {exc}", job_id=job_id
            ) from exc

    def get_job(self, job_id: str) -> NativeJob:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError as exc:
                raise JobExecutionError("unknown process-local job", job_id=job_id) from exc

    def close(self):
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=False)


def _fraction(value) -> Fraction:
    if isinstance(value, dict) and value.get("$type") == "fractions.Fraction":
        return Fraction(value["$value"])
    raise ResultValidationError("expected canonical exact Fraction")


def exact_z(payload: dict, backend_id: str, qubit: int) -> tuple[Fraction, Fraction]:
    """Return coefficients a,b of a+b*sqrt(2), without parsing executable text."""
    if backend_id == "stabilizer":
        marginal = payload.get("marginal", {})
        if marginal.get("subset") != [qubit] or not marginal.get("enumerated"):
            raise ResultValidationError("missing exact single-qubit marginal")
        distribution = marginal["distribution"]
        if not set(distribution) <= {"0", "1"}:
            raise ResultValidationError("invalid single-qubit outcomes")
        probs = {bit: _fraction(v) for bit, v in distribution.items()}
        if sum(probs.values()) != 1 or any(v < 0 for v in probs.values()):
            raise ResultValidationError("invalid exact probability normalization")
        return probs.get("0", Fraction(0)) - probs.get("1", Fraction(0)), Fraction(0)
    if backend_id != "exact_algebraic":
        raise CapabilityError("no exact Z extractor for this backend")
    state = payload.get("state", {})
    if state.get("schema") != "turing.vqc.exact_statevector.v1":
        raise ResultValidationError("missing certified exact state")
    amplitudes = state.get("amplitudes", [])
    if len(amplitudes) != 1 << state["n_qubits"]:
        raise ResultValidationError("invalid exact state length")
    rational, radical = Fraction(0), Fraction(0)
    norm_a, norm_b = Fraction(0), Fraction(0)
    for index, amplitude in enumerate(amplitudes):
        a, b, c, d = (Fraction(amplitude[k]) for k in ("re_p", "re_q", "im_p", "im_q"))
        p_a, p_b = a * a + 2 * b * b + c * c + 2 * d * d, 2 * (a * b + c * d)
        norm_a, norm_b = norm_a + p_a, norm_b + p_b
        sign = -1 if (index >> qubit) & 1 else 1
        rational, radical = rational + sign * p_a, radical + sign * p_b
    if (norm_a, norm_b) != (Fraction(1), Fraction(0)):
        raise ResultValidationError("exact state not normalized")
    return rational, radical


class NativeEstimator:
    def __init__(self, backend: Backend, config: PipelineConfig):
        self.backend, self.config = backend, config

    def estimate(self, request: ExecutionRequest) -> Estimate:
        if request.observable is None:
            raise CapabilityError("an explicit single-qubit PauliZ is required")
        if self.config.shots is not None and self.config.shots < 2:
            raise CapabilityError("sample standard error requires at least two shots")
        job = self.backend.submit(request)
        result = job.result(self.config.job_timeout_seconds)
        try:
            if result.request_hash != request.request_hash:
                raise ResultValidationError("estimate request binding mismatch", job_id=job.job_id)
            envelope = result.report()
            report = envelope["pipeline_report"]
            payload = report["result"]["payload"]
            a, b = exact_z(payload, request.artifact.backend_id, request.observable.qubit)
            exact = f"({a}) + ({b})*sqrt(2)"
            if self.config.shots is None:
                value, error, method = (
                    float(a) + float(b) * sqrt(2),
                    0.0,
                    "analytic_exact_no_sampling",
                )
            else:
                readout = request.readout
                if readout is None or request.observable.qubit not in readout:
                    raise ResultValidationError("observable absent from readout", job_id=job.job_id)
                index = readout.index(request.observable.qubit)
                counts = payload.get("counts", {})
                n = self.config.shots
                if (
                    not counts
                    or any(
                        type(c) is not int or c < 0 or len(k) != len(readout) or set(k) - {"0", "1"}
                        for k, c in counts.items()
                    )
                    or sum(counts.values()) != n
                ):
                    raise ResultValidationError("invalid sample counts", job_id=job.job_id)
                value = (
                    sum(
                        (1 if bitstring[index] == "0" else -1) * count
                        for bitstring, count in counts.items()
                    )
                    / n
                )
                error = sqrt(max(0.0, 1 - value * value) / (n - 1))
                method = "iid_empirical_standard_error_ddof1_not_confidence_bound"
            return Estimate(
                value,
                error,
                self.config.shots,
                request.observable,
                method,
                exact,
                (str(a), str(b)),
                result,
            )
        except JobExecutionError:
            raise
        except Exception as exc:
            raise ResultValidationError(
                f"invalid exact estimate: {exc}", job_id=job.job_id, report_json=result.report_json
            ) from exc
