# TURING — software release qualification

**Decision: candidate under qualification; not approved for production release.**

This is a decision record, not a maturity badge. TURING is an exact
quantum-mathematical software system. A physical device, calibration, coherence
window or cloud-provider subscription is not a release requirement. “Hybrid”
here describes orchestration and classical optimization around admitted quantum
mathematics, not an obligation to dispatch to external equipment.

## Release contract

One distribution: `hyba-turing-vqc`. One canonical engine: `VQCPipeline`.
`TuringPipeline` is an additive typed facade, not a universal replacement for all
legacy wrappers. Its finite-domain optimizer is a specific implementation, not
a restriction on every algorithm or representation in TURING.

The release candidate is the tuple **source commit + lock/resolution record +
wheel hash + sdist hash + qualification run + reviewed claims + approval**.
Changing any code, dependency resolution, artifact or supported claim requires
rerunning the affected qualification. Never approve a filename alone.

## Eight release gates

| Gate | Evidence required | Current disposition |
| --- | --- | --- |
| Mathematical validity | Exact independent reference cases, gate inverses, domain enforcement, exact ordering and canonical verification | Implemented focused/property tests; full engine qualification still required |
| Compatibility | Same admitted Program/settings yield equivalent canonical mathematical payload and certificate; legacy imports preserved; explicit differences documented | Differential fixtures implemented; downstream owners must validate their own wrappers |
| Integration | Canonical orchestration + estimator + finite optimization + result/provenance assembly | Focused end-to-end and real shared composition-root tests pass locally; deployed service approval remains separate |
| Reliability | Timeout/recovery, queued cancellation, failure isolation, bounded concurrent instances, cleanup and import initialization | Bounded controlled tests implemented; long-duration soak and resource baselines pending |
| Distribution integrity | Strict contract checks; locked dependencies; independent wheel and sdist installs; normalized payload parity; artifact hashes | Executable artifact qualifier and CI steps provided; remote matrix evidence must be reviewed |
| Security / provenance | Required SAST/SCA/credential/license checks, trusted source identity, reviewed release attestation/signing policy | Open: local pattern scan is not a substitute; GitHub scan permission previously unavailable |
| Operational readiness | Measured resource envelope, troubleshooting, rollback rehearsal, support/security owners | Runbooks provided; measurements, rehearsal and named accountable owners pending |
| Release approval | Full existing release workflow, unresolved-defect disposition, downstream candidate tests, maintainer approval and post-registry verification | Open; no tag, DOI, registry upload or approval is implied |

Passing a focused suite does not automatically close a gate. Evidence must state
interpreter/OS, dependencies, source state, commands, failures, artifact hashes
and limitations. A ZIP checkout cannot become commit-bound evidence by supplying
a fabricated SHA. Local development reports must retain their classification.

## Execution order

1. Review [mathematical contracts](docs/mathematical-contracts.md),
   [compatibility](docs/compatibility.md) and supported claim boundaries.
2. Run strict checks and source suites using the locked environment.
3. Build the dependency wheel and TURING wheel/sdist. Export locked requirements.
4. Run `experiments/qualify_artifacts.py` against those exact files. It rebuilds
   from sdist and runs independent installed consumer suites for both targets.
5. Review full-engine and enterprise integration gates, security findings,
   mutation/soak/resource reports and [open blockers](docs/validation.md).
6. Approve an immutable candidate; publish only through the existing controlled
   release workflow. Verify the registry download, then retain rollback evidence.

See [release policy](docs/release-policy.md) for decisions and the
[operator runbook](docs/operations.md) for recovery. The source and installed
consumer commands are in [installation](docs/installation.md).

## Accountability and exceptions

Before release, an authorized maintainer must fill in actual people and approval
references for: release owner, mathematical reviewer, compatibility/integration
owner, security owner and operational owner. Roles are not fictional sign-offs.
An exception records issue, impact, scope, evidence, compensating control, owner,
approver and expiry. Do not waive incorrect mathematics, forged provenance,
artifact/source mismatch, or exposure of credentials merely to meet a date.
Known unrelated defects remain visible; a narrower release scope must be
explicitly approved and accurately documented, never achieved by skipping tests.

## Capability architecture qualification delta (PR #96)

The [verified map](docs/capability-architecture.md),
[actual contracts](docs/dependency-contracts.md) and
[trust boundaries](docs/security-boundaries.md) separate architectural intent,
implemented local bindings and unresolved service/deployment contracts. These
requirements extend the ledger; they do not reset completed mathematical work.

| ID / requirement and rationale | Implementation | Verification / evidence | Status / outstanding decision | Release impact |
| --- | --- | --- | --- | --- |
| CAP-01: Keep security, self-healing/optimisation and intelligence ownership explicit; do not confuse presence with integration | ProductionOrganism/SystemRelations; capability map | Inspect actual calls, manifests and source; existing shared-custody tests | Map completed. Named peers/historical redirects are not authority | Required description of supported capability; no mathematical change |
| CAP-02: Real credential-provider compatibility and safe refusal before effects | `euclid/runtime.py`; `ProductionOrganism` explicit provider and tenant | Real guardian + canonical Salamander + TURING probe; provider outage, invalid/cross-tenant credentials, distinct creator/tenant and default closure tests | Implemented and locally verified. Provider invoked once; absent provider remains closed. Deployment credentials/policy require owner approval | Local wiring complete; no automatic entitlement or recovery-policy approval |
| CAP-03: Security-critical dispatch remains guarded and responses are bound | EUCLID dispatch, AL HARAS, bound service tenant | Exact execution; missing/expired/foreign-tenant/one-use credentials; malformed verdict type/boolean/tenant/operation/payload/evidence tests | Local checks pass before effects. Remote identity/transport and durable cluster replay remain unqualified | Supported local boundary verified; do not infer a remote perimeter |
| CAP-04: Governed computation invokes the existing canonical owner | `TuringQuantumOrgan(pipeline=SharedTuring)` in ProductionOrganism; owner locks | Real Program, certificate/witness/report, shared readback/replay, guarded handoff, substitution refusals and concurrent per-program identity tests | Shared production path implemented and locally verified; standalone direct adapter remains explicitly distinct | No engine replacement; a handoff alone is not canonical execution evidence |
| CAP-05: Real intelligence consumption and selected distribution closure | EUCLID routing/delegation; platform/TURING/Kellogg wheels; installed qualifier | Actual router invokes canonical specialist; independent environment checks imports, dependencies and real consumers | Local composition verified. No invented reverse intelligence client; independently deployed distributions/services need their own compatibility agreement | Supported local capability claim only; remote deployment/owner approval remain open |
| CAP-06: Replace obsolete actuation authority fixtures, not production authority | `euclid/tests/test_actuation_authority.py`; legacy proposal expectation | All six original authority cases now exercise actual authorization/control plane; diagnosis remains unapplied without its separate actuator | Closed locally. Earlier four module-replacement ImportErrors are historical and superseded, not current blockers | Does not waive other existing engine/release findings |
| CAP-07: One installed file owner per dependency | Root `pyproject.toml`; `qualify_capability_installation.py`; packaging regression tests | Reproduced 38 shared Kellogg file paths; removed root vendoring, retained dependency; qualifier rejects duplicate owners before install | Corrected selected three-wheel set is independently installed and tested; clean build required | Prevents installation/uninstallation ownership collisions; not supply-chain approval |

Evidence for this delta is recorded in [validation](docs/validation.md). Existing
mathematical, import-isolation, concurrency and artifact evidence is retained for
its original source/artifact scope. No blanket rerun or blanket requalification
is implied. Affected final artifacts are rebuilt and independently requalified for the local
revision recorded in validation; any subsequent change requires affected checks. Required remote CI, security,
owner approvals and the earlier release blockers remain open. No merge, tag,
publication or production approval is granted by these additions.
