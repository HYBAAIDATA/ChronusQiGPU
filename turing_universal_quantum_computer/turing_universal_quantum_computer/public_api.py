"""Stable additive facade. Existing pipeline.py and VQCPipeline stay unchanged."""

from .config import PipelineConfig
from .contracts import (
    CircuitIR,
    ExecutionRequest,
    FiniteAnsatz,
    ParameterBindings,
    PauliZ,
    CompiledArtifact,
    Estimate,
    JobResult,
    OptimizationResult,
    BackendCapabilities,
)
from .backends.base import Program
from .exceptions import CapabilityError, ParameterValidationError
from .interfaces import Backend, Compiler, Estimator, Optimizer, ExecutionJob
from .native_adapter import NativeBackend, NativeCompiler, NativeEstimator
from .optimizer import FiniteGridOptimizer


class QuantumPipeline:
    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        compiler: Compiler | None = None,
        backend: Backend | None = None,
        estimator: Estimator | None = None,
        optimizer: Optimizer | None = None
    ):
        self.config = config if config is not None else PipelineConfig()
        self.compiler = compiler if compiler is not None else NativeCompiler(self.config)
        self.backend = backend if backend is not None else NativeBackend(self.config)
        self.estimator = (
            estimator if estimator is not None else NativeEstimator(self.backend, self.config)
        )
        self.optimizer = optimizer if optimizer is not None else FiniteGridOptimizer()

    def capabilities(self) -> BackendCapabilities:
        return self.backend.capabilities()

    def compile(
        self,
        problem: Program | CircuitIR | FiniteAnsatz,
        parameters: ParameterBindings | None = None,
    ) -> CompiledArtifact:
        """Bind and admit a native circuit; never submit or evolve a state."""
        if isinstance(problem, FiniteAnsatz):
            if parameters is None:
                raise ParameterValidationError("finite ansatz requires explicit named parameters")
            ir = problem.bind(parameters)
        elif isinstance(problem, CircuitIR):
            if parameters is not None and parameters != problem.bindings:
                raise ParameterValidationError("IR is already bound")
            ir = problem
        elif isinstance(problem, Program):
            if parameters is not None and parameters != ParameterBindings():
                raise ParameterValidationError("fixed native Program has no parameters")
            ir = CircuitIR(problem)
        else:
            raise CapabilityError(
                "native adapter requires Program, CircuitIR or FiniteAnsatz; continuous SDK circuits require an explicit adapter"
            )
        return self.compiler.compile(ir)

    def submit(
        self,
        problem: Program | CircuitIR | FiniteAnsatz,
        parameters: ParameterBindings | None = None,
        *,
        observable: PauliZ | None = None,
        readout: tuple[int, ...] | None = None,
        idempotency_key: str | None = None
    ) -> ExecutionJob:
        artifact = self.compile(problem, parameters)
        request = ExecutionRequest(artifact, artifact.ir.bindings, observable, readout)
        return self.backend.submit(request, idempotency_key=idempotency_key)

    def run(
        self,
        problem: Program | CircuitIR | FiniteAnsatz,
        parameters: ParameterBindings | None = None,
        *,
        readout=None,
        idempotency_key: str | None = None
    ) -> JobResult:
        """Execute one workload, not an optimization; return a typed job result."""
        return self.submit(
            problem, parameters, readout=readout, idempotency_key=idempotency_key
        ).result(self.config.job_timeout_seconds)

    def estimate(
        self,
        problem: Program | CircuitIR | FiniteAnsatz,
        parameters: ParameterBindings | None = None,
        *,
        observable: PauliZ
    ) -> Estimate:
        if not isinstance(observable, PauliZ):
            raise CapabilityError("native estimator supports single-qubit PauliZ only")
        artifact = self.compile(problem, parameters)
        readout = None if self.config.shots is None else (observable.qubit,)
        return self.estimator.estimate(
            ExecutionRequest(artifact, artifact.ir.bindings, observable, readout)
        )

    def run_vqe(
        self,
        problem: FiniteAnsatz,
        initial_parameters: ParameterBindings,
        *,
        observable: PauliZ,
        max_iterations: int = 200
    ) -> OptimizationResult:
        """Minimize a declared finite exact ansatz, NOT arbitrary-angle VQE.

        Exhaustion identifies the exact minimum in this finite domain only.
        All members are compiled before the first evaluation. Candidate ordering
        uses exact rational/radical comparison; float values are display only.
        """
        if not isinstance(problem, FiniteAnsatz):
            raise CapabilityError(
                "native VQE requires an explicit FiniteAnsatz; no continuous-angle claim"
            )
        if type(max_iterations) is not int or max_iterations < 1:
            raise ParameterValidationError("max_iterations must be a positive integer")
        if self.config.shots is not None:
            raise CapabilityError(
                "native finite VQE uses analytic exact estimates, not noisy convergence"
            )
        initial_parameters.validate(problem.parameters)
        candidates = (initial_parameters,) + tuple(
            p for p in problem.candidates() if p != initial_parameters
        )
        artifacts = {p: self.compile(problem, p) for p in candidates}
        requests = {p: ExecutionRequest(a, p, observable) for p, a in artifacts.items()}
        return self.optimizer.minimize(
            lambda p: self.estimator.estimate(requests[p]),
            candidates,
            max_iterations=max_iterations,
        )

    def get_job(self, job_id: str) -> ExecutionJob:
        return self.backend.get_job(job_id)

    def cancel_job(self, job_id: str) -> bool:
        return self.get_job(job_id).cancel()

    def close(self):
        self.backend.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


TuringPipeline = QuantumPipeline
# Compatibility name from the original API proposal; no separate product.
AdvancedQuantumPipeline = QuantumPipeline
