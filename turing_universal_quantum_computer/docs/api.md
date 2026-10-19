# Public API

```python
from turing_universal_quantum_computer import TuringPipeline, PipelineConfig, PauliZ
from turing_universal_quantum_computer.backends.base import Program

with TuringPipeline(PipelineConfig()) as turing:
    bell = Program(2).then("h", 0).then("cx", 0, 1)
    artifact = turing.compile(bell)  # admission only; does not execute
    estimate = turing.estimate(bell, observable=PauliZ(0))
    assert estimate.exact_coefficients == ("0", "0")
```

`compile`, `submit`, `run`, `estimate`, `get_job`, `cancel_job` and `capabilities`
are explicit operations. The facade's `run_vqe` minimizes an explicitly finite
family of exact native programs. It is not a continuous-angle optimizer. This
boundary describes this API, not the entirety of TURING's algorithm library.

ParameterBindings name and order every parameter; immutable artifacts include
configuration, source, compiler, representation target and implementation
fingerprints. A changed binding requires recompile. Native layouts are identity;
there is no claim of newly implemented routing or optimization passes.

Local jobs have typed status and bounded waiting. A wait timeout does not fail or
resubmit a job. Queued jobs can be cancelled; running computations drain on
`close()`. Idempotency and job recovery are scoped to one live backend instance,
not a durable scheduler. Errors retain the job ID and diagnostic report where
available. Operational errors are not returned as optimizer convergence.

The existing canonical pipeline, console, native algorithm library and registry
remain supported entry points. The module registry records every new module.

For generated signatures and typed fields, see [reference](reference.md).
For preconditions, exactness and uncertainty semantics, see
[mathematical contracts](mathematical-contracts.md). For migration differences,
see [compatibility](compatibility.md).
