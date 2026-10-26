# Compatibility and migration

## A precise promise

`TuringPipeline`, `QuantumPipeline` and `AdvancedQuantumPipeline` refer to the
same additive facade. Existing `VQCPipeline` and `VQCRequest` remain unchanged.
This is **not** a claim that every legacy wrapper can be renamed without changes.
The facade returns `JobResult`/`Estimate`/`OptimizationResult`, not the legacy
`PipelineReport` shape. Review side effects, exception handling and storage
ownership before migrating an application.

| Concern | Canonical path | Typed facade |
| --- | --- | --- |
| Execution | `VQCPipeline().run(VQCRequest(...))` | `with TuringPipeline(config) as p: p.run(program)` |
| Report | `PipelineReport` | `JobResult.report()['pipeline_report']` |
| Representation | Broader canonical selection surface | Currently `auto`, `exact_algebraic`, `stabilizer` bindings |
| Parameters | Existing native interfaces | Named finite family only; changed binding requires compilation |
| Optimization | Algorithm-specific existing APIs | Exhaustive finite-domain minimization, not general continuous VQE |
| Jobs | Caller-specific orchestration | Single-worker, bounded process-local registry; no durable recovery |
| Custody | Existing adapters/composition roots | Explicit configuration; local custody is not enterprise acceptance |

## Migration in five steps

1. Inventory the old wrapper: admitted inputs, defaults, seed, readout ordering,
   representation, result fields, exceptions and any persistence side effects.
2. Keep a small fixture set with analytical expectations and real consumer checks.
   Compare equivalent canonical mathematical payloads, not run IDs/timing/notes.
3. Select explicit `PipelineConfig` settings. Do not silently map arbitrary
   continuous angles into finite identifiers or approximate unsupported gates.
4. Change result parsing deliberately; catch typed validation/capability errors
   separately from operational failures. A timeout means “wait expired”, not
   “compute failed”: recover the original job, do not submit another blindly.
5. Use a context manager. Run the consumer suite against the exact candidate
   wheel and sdist-derived wheel before replacing the pinned dependency.

## Supported environment evidence

| Dimension | Declared / target | Evidence status |
| --- | --- | --- |
| Python | Existing package >=3.11; focused matrix 3.11/3.12/3.13 | Local 3.13 tested; remote matrix must be verified |
| OS | Platform-independent Python interfaces | Linux local/CI target; macOS/Windows qualification pending |
| Core dependencies | Existing declared NumPy/SymPy/Kellogg ranges | Locked current resolution tested; minimum-version sweep pending |
| Concurrency | Multiple independent facades, one worker per native backend | Bounded controlled regression tests, not unbounded service capacity |
| Integrations | Existing canonical APIs retained | Enterprise shared-root/downstream approval separate |

Public: documented facade/config/contracts/exceptions; native `Program` and
existing canonical entry points. Extension: protocols, adapter implementations
and explicitly documented capabilities. Internal: private attributes and JSON
implementation details not promoted to stable APIs. A field in an envelope is
not automatically a permanent compatibility promise.

The existing 1.0.0 metadata has not been republished by this PR. Before the first
release containing these changes, maintainers must choose an appropriate new
version and update package metadata, source version, citation and release gates
together. Never overwrite an existing registry version.
