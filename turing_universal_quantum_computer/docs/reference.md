# Generated typed API reference

Generated from the actual public contracts and facade. Do not edit signatures manually.

Read [mathematical contracts](mathematical-contracts.md) and [migration](compatibility.md) for semantics.

## Facade

The exported `TuringPipeline` name aliases `QuantumPipeline`; `VQCPipeline` remains distinct.

### `__init__`

```python
__init__(self, config: turing_universal_quantum_computer.config.PipelineConfig | None = None, *, compiler: turing_universal_quantum_computer.interfaces.Compiler | None = None, backend: turing_universal_quantum_computer.interfaces.Backend | None = None, estimator: turing_universal_quantum_computer.interfaces.Estimator | None = None, optimizer: turing_universal_quantum_computer.interfaces.Optimizer | None = None)
```

### `capabilities`

```python
capabilities(self) -> turing_universal_quantum_computer.contracts.BackendCapabilities
```

### `compile`

```python
compile(self, problem: turing_universal_quantum_computer.backends.base.Program | turing_universal_quantum_computer.contracts.CircuitIR | turing_universal_quantum_computer.contracts.FiniteAnsatz, parameters: turing_universal_quantum_computer.contracts.ParameterBindings | None = None) -> turing_universal_quantum_computer.contracts.CompiledArtifact
```

Bind and admit a native circuit; never submit or evolve a state.

### `submit`

```python
submit(self, problem: turing_universal_quantum_computer.backends.base.Program | turing_universal_quantum_computer.contracts.CircuitIR | turing_universal_quantum_computer.contracts.FiniteAnsatz, parameters: turing_universal_quantum_computer.contracts.ParameterBindings | None = None, *, observable: turing_universal_quantum_computer.contracts.PauliZ | None = None, readout: tuple[int, ...] | None = None, idempotency_key: str | None = None) -> turing_universal_quantum_computer.interfaces.ExecutionJob
```

### `run`

```python
run(self, problem: turing_universal_quantum_computer.backends.base.Program | turing_universal_quantum_computer.contracts.CircuitIR | turing_universal_quantum_computer.contracts.FiniteAnsatz, parameters: turing_universal_quantum_computer.contracts.ParameterBindings | None = None, *, readout=None, idempotency_key: str | None = None) -> turing_universal_quantum_computer.contracts.JobResult
```

Execute one workload, not an optimization; return a typed job result.

### `estimate`

```python
estimate(self, problem: turing_universal_quantum_computer.backends.base.Program | turing_universal_quantum_computer.contracts.CircuitIR | turing_universal_quantum_computer.contracts.FiniteAnsatz, parameters: turing_universal_quantum_computer.contracts.ParameterBindings | None = None, *, observable: turing_universal_quantum_computer.contracts.PauliZ) -> turing_universal_quantum_computer.contracts.Estimate
```

### `run_vqe`

```python
run_vqe(self, problem: turing_universal_quantum_computer.contracts.FiniteAnsatz, initial_parameters: turing_universal_quantum_computer.contracts.ParameterBindings, *, observable: turing_universal_quantum_computer.contracts.PauliZ, max_iterations: int = 200) -> turing_universal_quantum_computer.contracts.OptimizationResult
```

Minimize a declared finite exact ansatz, NOT arbitrary-angle VQE.

Exhaustion identifies the exact minimum in this finite domain only.
All members are compiled before the first evaluation. Candidate ordering
uses exact rational/radical comparison; float values are display only.

### `get_job`

```python
get_job(self, job_id: str) -> turing_universal_quantum_computer.interfaces.ExecutionJob
```

### `cancel_job`

```python
cancel_job(self, job_id: str) -> bool
```

### `close`

```python
close(self)
```

## Typed values

### `PipelineConfig`

```python
PipelineConfig(backend: str = 'auto', execution_mode: str = 'exact_vqc', error_management: str = 'none', max_amplitudes: int = 1048576, max_qubits: int = 10000, shots: int | None = None, seed: int = 1234, job_timeout_seconds: float = 300.0, differential: bool = True, custody: bool = False, replay: bool = False, custody_dir: str | None = None) -> None
```

Fields: `backend`, `execution_mode`, `error_management`, `max_amplitudes`, `max_qubits`, `shots`, `seed`, `job_timeout_seconds`, `differential`, `custody`, `replay`, `custody_dir`.

### `ParameterSpec`

```python
ParameterSpec(name: 'str', values: 'tuple[float, ...]', lower_bound: 'float | None' = None, upper_bound: 'float | None' = None) -> None
```

Fields: `name`, `values`, `lower_bound`, `upper_bound`.

### `ParameterBindings`

```python
ParameterBindings(names: 'tuple[str, ...]' = (), values: 'tuple[float, ...]' = ()) -> None
```

Fields: `names`, `values`.

### `CircuitIR`

```python
CircuitIR(program: 'Program', parameters: 'tuple[ParameterSpec, ...]' = (), bindings: 'ParameterBindings' = ParameterBindings(names=(), values=()), family_hash: 'str | None' = None, ir_version: 'str' = 'turing.native_program.v1') -> None
```

Fields: `program`, `parameters`, `bindings`, `family_hash`, `ir_version`.

### `FiniteAnsatz`

```python
FiniteAnsatz(parameters: 'tuple[ParameterSpec, ...]', programs: 'tuple[Program, ...]') -> None
```

Fields: `parameters`, `programs`.

### `BackendCapabilities`

```python
BackendCapabilities(backend_id: 'str', max_qubits: 'int' = 10000, max_amplitudes: 'int' = 1048576, execution_kind: 'str' = 'turing_vqc', supported_backends: 'tuple[str, ...]' = ('exact_algebraic', 'stabilizer'), supports_finite_parameters: 'bool' = True, supports_continuous_angles: 'bool' = False, supports_dynamic_control: 'bool' = False, supports_pulse_control: 'bool' = False, supports_fault_tolerant_execution: 'bool' = False, supports_physical_qpu: 'bool' = False, supports_parameter_batches: 'bool' = False, observable_kinds: 'tuple[str, ...]' = ('single_qubit_z',), job_persistence: 'str' = 'in_memory_process_local') -> None
```

Fields: `backend_id`, `max_qubits`, `max_amplitudes`, `execution_kind`, `supported_backends`, `supports_finite_parameters`, `supports_continuous_angles`, `supports_dynamic_control`, `supports_pulse_control`, `supports_fault_tolerant_execution`, `supports_physical_qpu`, `supports_parameter_batches`, `observable_kinds`, `job_persistence`.

### `CompiledArtifact`

```python
CompiledArtifact(ir: 'CircuitIR', backend_id: 'str', config_json: 'str', source_hash: 'str', layout: 'tuple[tuple[int, int], ...]', implementation_hash: 'str', compiler_version: 'str' = 'turing.native_admission.v1', api_schema: 'str' = 'turing.public_api.v1') -> None
```

Fields: `ir`, `backend_id`, `config_json`, `source_hash`, `layout`, `implementation_hash`, `compiler_version`, `api_schema`.

### `ExecutionRequest`

```python
ExecutionRequest(artifact: 'CompiledArtifact', parameters: 'ParameterBindings' = ParameterBindings(names=(), values=()), observable: 'PauliZ | None' = None, readout: 'tuple[int, ...] | None' = None) -> None
```

Fields: `artifact`, `parameters`, `observable`, `readout`.

### `PauliZ`

```python
PauliZ(qubit: 'int') -> None
```

Fields: `qubit`.

### `JobResult`

```python
JobResult(job_id: 'str', request_hash: 'str', report_json: 'str') -> None
```

Fields: `job_id`, `request_hash`, `report_json`.

### `Estimate`

```python
Estimate(value: 'float', standard_error: 'float', shots: 'int | None', observable: 'PauliZ', uncertainty_method: 'str', exact_value: 'str', exact_coefficients: 'tuple[str, str]', job_result: 'JobResult') -> None
```

Fields: `value`, `standard_error`, `shots`, `observable`, `uncertainty_method`, `exact_value`, `exact_coefficients`, `job_result`.

### `OptimizationResult`

```python
OptimizationResult(parameters: 'ParameterBindings', objective_value: 'float', converged: 'bool', iterations: 'int', termination_reason: 'str', history: 'tuple[Evaluation, ...]', search_domain: 'str' = 'declared_finite_ansatz_only') -> None
```

Fields: `parameters`, `objective_value`, `converged`, `iterations`, `termination_reason`, `history`, `search_domain`.

## Extension protocols

### `Compiler`

```python
compile(self, circuit: turing_universal_quantum_computer.contracts.CircuitIR) -> turing_universal_quantum_computer.contracts.CompiledArtifact
```

### `ExecutionJob`

`job_id`: read-only property.

```python
status(self) -> turing_universal_quantum_computer.contracts.JobStatus
```

```python
result(self, timeout: float | None = None) -> turing_universal_quantum_computer.contracts.JobResult
```

```python
cancel(self) -> bool
```

### `Backend`

```python
capabilities(self) -> turing_universal_quantum_computer.contracts.BackendCapabilities
```

```python
submit(self, request: turing_universal_quantum_computer.contracts.ExecutionRequest, *, idempotency_key: str | None = None) -> turing_universal_quantum_computer.interfaces.ExecutionJob
```

```python
get_job(self, job_id: str) -> turing_universal_quantum_computer.interfaces.ExecutionJob
```

```python
close(self) -> None
```

### `Estimator`

```python
estimate(self, request: turing_universal_quantum_computer.contracts.ExecutionRequest) -> turing_universal_quantum_computer.contracts.Estimate
```

### `Optimizer`

```python
minimize(self, evaluate: Callable[[turing_universal_quantum_computer.contracts.ParameterBindings], turing_universal_quantum_computer.contracts.Estimate], candidates: tuple[turing_universal_quantum_computer.contracts.ParameterBindings, ...], *, max_iterations: int) -> turing_universal_quantum_computer.contracts.OptimizationResult
```

### `ErrorManager`

```python
prepare(self, request: turing_universal_quantum_computer.contracts.ExecutionRequest) -> turing_universal_quantum_computer.interfaces.ExecutionPlan
```

## Exceptions

- `QuantumPipelineError` → Exception: Base public API exception.
- `ConfigurationError` → QuantumPipelineError, ValueError: Invalid configuration.
- `CapabilityError` → QuantumPipelineError: Unsupported operation; no implicit downgrade.
- `CompilationError` → QuantumPipelineError: Invalid or unadmitted circuit; no execution performed.
- `ParameterValidationError` → QuantumPipelineError, ValueError: Named values violate a schema.
- `JobExecutionError` → QuantumPipelineError: Base public API exception.
- `JobTimeoutError` → JobExecutionError, TimeoutError: The wait expired; the job may still be running. Do not resubmit blindly.
- `ResultValidationError` → JobExecutionError: Result or provenance failed validation.
- `IdempotencyConflictError` → QuantumPipelineError: An idempotency key was reused for a different request.
