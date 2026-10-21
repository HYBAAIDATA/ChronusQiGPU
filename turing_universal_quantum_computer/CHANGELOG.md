# Changelog

## Unreleased

- Organize TURING software, reproducible experiments, results and publication
  materials as separate maintained surfaces, without a second product namespace.
- Add typed API contracts, named finite parameters, native facade/compiler/job
  adapters, exact-derived Z estimates and bounded finite-domain optimization.
- Expose `TuringPipeline` while retaining canonical `VQCPipeline` and compatible
  convenience aliases.
- Record all API modules and the existing Lucas-metallic walk in the registry.
- Defer Kellogg's mining-specific exports until requested so exact consumers
  do not eagerly require Chronus mining modules at import time.
- Add contract tests, experiment/analysis checks, research environment lock,
  provenance manifests, citation metadata and reviewable CI validation.

No new publication, DOI, external-device execution, mathematical advantage,
continuous-angle synthesis or general error-management implementation is claimed.

### Software release qualification

- Explicit mathematical/compatibility contracts, migration, support and rollback
  guidance, qualification/approval policy and finite-domain/Kellogg ADRs.
- Generated API reference with drift checking; strict checks for five typed
  contract/config/protocol/exception/optimizer modules and source lint.
- Deterministic property-based exact/reference tests, canonical differential
  fixtures, bounded concurrency/import stress and lifecycle/fault-injection tests.
- Disposable targeted mutation checks and independent wheel/sdist-installed
  consumer qualification, artifact hashes, normalized content parity and JUnit
  evidence. These do not imply release approval or completion of open gates.
