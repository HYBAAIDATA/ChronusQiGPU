# TURING package architecture

TURING is the existing `hyba-turing-vqc` distribution and
`turing_universal_quantum_computer` import namespace. It executes the exact
quantum mathematics admitted by its representations. Its package organization
does not make a separate external device a prerequisite for those operations.

## Governed capability delivery

AL HARAS (security), Salamander (self-healing/optimisation) and EUCLID
(intelligence) have intended dependency responsibilities in TURING's capability
architecture, not unrelated optional product features. The mathematical engine
remains intact. Actual local bindings, incomplete integration and deployment
assumptions are separated in the [verified dependency map](capability-architecture.md),
[dependency contracts](dependency-contracts.md) and
[trust-boundary record](security-boundaries.md). A library call is not implicitly
an authorised customer service operation.

## Three maintained surfaces

| Surface | Location | What belongs here |
| --- | --- | --- |
| Reusable software | `turing_universal_quantum_computer/` inner package | Native IR, exact engines, representation/admission, compiler/API contracts, execution, verification, certificates, custody adapters |
| Research evidence | `experiments/`, `results/` | Versioned configurations, executable runners, validated machine-readable manifests, derived summaries; no manually invented results |
| Publication | `paper/` | Draft manuscript, methodology, bibliography, generated tables, limitations and supplementary/reproduction instructions |

`docs/` explains the implementation and its evidence; `tests/` verifies it;
`examples/` demonstrates real admitted workloads. Build output, environments,
credentials and bulk runtime evidence are not Python implementation modules.

## Implementation map

| Responsibility | Owning modules |
| --- | --- |
| Public convenience API | `public_api.TuringPipeline` (`QuantumPipeline` is the same facade) |
| Canonical orchestration | existing `pipeline.VQCPipeline`, unchanged |
| Configuration / failures | `config`, `exceptions` |
| Typed IR, parameters, artifact and result contracts | `contracts`; existing `backends.base.Program` remains native IR |
| Extension protocols | `interfaces` |
| Native admission/compiler and execution/job adapter | `native_adapter` |
| Finite exact variational minimization | `optimizer`; the rest of TURING's algorithm library retains its existing owners |
| Backend selection / exact execution | existing `backends/`, `representation`, exact engines |
| Verification / observability / provenance | existing `certificates`, `verify`, `taxonomy`; immutable API envelopes |
| Storage integration | existing `custody`, `transform`; enterprise shared ownership is not replaced |
| Operator console | existing `console` and `turing-vqc` entry point |

The new facade does not replace or relabel the algorithms in `quantum_library`,
`hilbert`, the tableau, MPS or exact field modules. A feature absent from this
facade is not therefore absent from TURING. Bind an existing implementation
through its real interface and test it before advertising it on the facade.

## Boundaries are correctness checks, not a different thesis

Parameter identity, gate arity, representation admission, source bindings,
measurement definitions and exact result verification are executable contracts.
They prevent answering a different problem or attaching the wrong provenance.
They do not condition TURING's exact mathematics on external device access.
The existing witness schema is preserved for compatibility; no external-device
experiment or result is introduced by this package-organization change.

Only implemented APIs have modules. Pulse/control and new error-management
methods are documented extensions, not empty directories or claimed features.
The existing `ErrorManager`/`ExecutionPlan` contract is small and explicit; a
no-error-management plan is provided, not a pretend correction workflow.

## Layout compatibility

The project already has a valid distribution directory containing its named
Python package. Moving every engine into a new `src/` tree in the same change
would churn imports, registry paths, packaging scripts and existing release
contracts without improving execution semantics. We retain that layout and
separate software/evidence/publication now. See ADR 0001. There is no second
`advanced_quantum_pipeline` distribution and no duplicated engine.
