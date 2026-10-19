# EUCLID canonical runtime integrity and contextual-learning work

This changes the existing runtime and specialists, not the immutable EUCLID v16.4 comparison baseline. It neither replaces the integrated intelligence architecture nor certifies AGI/ASI, production deployment or package publication.

## Implemented changes

- `EuclidRuntime.solve_task` revokes temporary dispatch permission in `finally`, including `BaseException` cancellation; failed episodes do not enter success persistence/reachability paths.
- Closed adaptive/repository/specialist entry points reject further work; shutdown revokes existing delegation rights without removing registered capabilities.
- `dispatch_specialist` denies actuation when AL HARAS is absent. Existing creator rights do not substitute for governance. Configured AL HARAS continues to own policy decisions.
- Fail-soft `close()` remains compatible, while `shutdown_report()` distinguishes store-save/database-close outcomes and exposes failures without leaking exception messages. `durability_verified` remains false: resource closure is not independent restart evidence.
- `EvidenceChain` detaches input/returned/view records and serialises append/snapshot/verification with a reentrant lock. Existing hash domains and serialized schemas remain unchanged. This does not make the entire runtime thread-safe.
- `CognitiveState` detaches transition inputs/views and payload snapshots while preserving timestamp-independent scientific digests.
- `CognitionProblem` rejects metadata overrides of validated identity, objectives, constraints and reward fields at dispatch. Legitimate extension fields remain supported. Callers relying on metadata authority spoofing must migrate to typed validated fields, not regain a bypass.
- Both cognition public packages lazily resolve all their original public names to the same canonical implementations. Missing optional components still raise actual resolution errors; no fallback or mocked engine is introduced.
- Adaptive recomposition keeps unique organ identity. File presence/same-process recomposition no longer manufactures restart credit. Episode-phase evidence supports USE only; independent executed/outcome/feedback/persistence/restart proofs are not inferred for every specialist.
- `ContextualStrategyLearner` detects harmful imported-prior/context disagreement without requiring an already-tested rival. The comparison excludes target observations from source evidence, retains explicit MODELED classification, uses configurable versions of existing trial/probability thresholds, and suppresses implicated strategies only in the affected context. Suppression affects selection and survives serialization/restart; globally registered capabilities remain intact. If every available strategy is suppressed, selection fails explicitly instead of repeating the known bad path. Frozen evaluation does not learn; nonfinite utility is rejected.

The modeled comparison is a Beta fractional-utility/normal approximation, not a calibrated causal-effect probability or a safety certificate. Contextual suppression is conservative; evidence-driven requalification of historically suppressed strategies remains further work, not automatic permission expansion.

## Executed local evidence scope

Run from repository root with pytest available:

```bash
python -m pytest -q euclid/tests/test_runtime_integrity.py --junitxml=components.xml
python scripts/test_euclid_integrity_mutations.py --output mutations.json
```

The suite includes real EvidenceChain/CognitiveState/MemoryDatabase/LearningService/RightsLedger/Delegator/AL HARAS/ContextualStrategyLearner components and fresh Python processes. Local unit failure doubles and controlled software effects are explicitly labelled. These results do not certify the full API, installed distribution, real mining/VQC/execution fabric, THESEUS/OVID production composition or external research validation.

Mutation checks require named assertion failures for evidence aliasing, cognitive-transition aliasing, problem-field spoofing, missing permission cleanup, post-close actuation, missing governance, shutdown-rights leakage and ignored negative-transfer selection. Import/collection/harness failures do not count as killed mutants.

The existing `euclid-v17-integration.yml` workflow is extended, not replaced. It installs declared canonical runtime/test dependencies, runs component/mutation checks and retains artifacts bound to `git rev-parse HEAD`; existing production integration gates/tests remain mandatory. No successful CI run is claimed merely because a workflow was edited.

## Production verdict and remaining repository-controlled work

**NOT PRODUCTION READY.** Local integrity and specialist-learning evidence does not satisfy all mandatory production gates.

Remaining work includes:

1. Normal API construction with authenticated actor/tenant context and governed canonical intelligence dispatch; durable scoped request/effect idempotency and bounded concurrency.
2. Adaptive knowledge/episode custody binding through canonical THESEUS/OVID and independently verified fresh-process readback. The existing production-integration tests expect `bind_adaptive_data_port`, `adaptive_restart_receipt`, `verify_adaptive_restart_receipt` and `ADAPTIVE_KNOWLEDGE_KIND`; the inspected runtime does not yet implement these methods/contracts.
3. Full real-component adaptive/integrated voyages, independent outcome verification, rollback and recovery-budget persistence—not unit substitutes.
4. Complete component/caller inventory and truthful historical reachability correction. This patch prevents new unsupported adaptive credit but does not erase or independently requalify older overcredited ledgers.
5. Dependency/package ownership closure, wheel/sdist builds, clean installed-artifact tests and supported platform/interpreter matrix.
6. Full regression/scientific comparisons against immutable v16.4, API/direct-runtime parity and held-out coupled-mechanism evidence.
7. Independently executed CI and deployment qualification, plus approved release boundary/policy/registry ownership. Confirmed zero-step jobs are UNAVAILABLE; absence of accessible logs is not proof of zero steps.

Items 1–6 are implementation/test obligations, not external blockers. Policy/deployment/registry decisions and independent runner access may be external dependencies. Do not conflate them.

Machine readiness remains the conjunction of the mandate's required gates. PASS for this component suite cannot set the overall result true. Unknown coverage is UNKNOWN, never a fabricated zero defect count.
