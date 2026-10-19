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

## EUCLID installed-artifact acceptance refresh (2026-10-19)

**Decision: not accepted; release remains blocked.** This refresh records live repository evidence and the access boundary encountered; it is not a substitute for the clean-install acceptance run.

### Repository state and ancestry

- `main` is at `5a4e120297d8106dfe1c1f8ba4d7e3baa913b43d`.
- PRs #96, #97, #98 and #110 are all open and unmerged. PR #96 is head `405414903301c7ff5dae56e40adedb029a4a141e` from `feat/turing-package-organization-20261019`, based on `main` at `af4e34a3c9463750dc32bcd1eae41f7310944833`. PR #97 is head `a61a9dd1e34e23d3bcd2533089a001d50bc07c0a`, also based on that older `main` commit. PR #98 is head `9f0e4bb89507be9e141a89f79f05493f7b397362`, based on the PR #96 branch at `356ab419dae197f407989da82feaa2f149da08e7`; that base is an earlier PR #96 commit, not its current head. PR #110 is head `87dce11dfc84de7d283300ea9921ecd558b9187e`, based on current `main` at `5a4e120297d8106dfe1c1f8ba4d7e3baa913b43d`; its live GitHub state is `open`, `draft=false`, `mergeable_state=blocked` (despite the task context calling it a draft).
- The PR #98 description claims a billing-scope correction at `cf56d0aaa7c427e7319c86af979cec1a5d808570`, but its live head and commit list contain only `d3d2366de27b788398f578b725f7dbd09d43b1dd` and `9f0e4bb89507be9e141a89f79f05493f7b397362`. The claimed correction is not present in that PR's current commit list. Treat the billing/Hermitten scope as unresolved until the branch and contract are reconciled. PR #97's proposed Hermitten receiver is not evidence of live Hermitten conformance.

### Acceptance execution and CI access

- Attempted `git clone --filter=blob:none https://github.com/PhiEnterprise1/EuclidPhiEnterprise.git EuclidPhiEnterprise`; it exited 128 with `fatal: could not read Username for 'https://github.com': No such device or address`. No complete checkout was obtained, so no product artifact was built or installed in this refresh and no repository test suite was rerun.
- GitHub `get_check_runs` for the four PR heads was denied with `403 Resource not accessible by personal access token`. For PR #110, combined status returned `pending`, `total_count=0`, `statuses=[]` at head `87dce11dfc84de7d283300ea9921ecd558b9187e`. This proves an access/visibility gap, not a CI failure or a pass. Workflow run details and required branch-protection checks remain unverified.
- Existing PR #110 `reports/euclid_clean_install/local_validation.json` records selective-source evidence only: 20 bridge tests and 8 packaging tests in normal and `-O` modes, focused Ruff and Black checks; the build/pip pipeline used synthetic fixture sources and the focused bridge used `DiskPort`. The report explicitly marks full enterprise-wheel install, canonical installed native paths, cross-process shared-custody acceptance, Linux/Windows CI, full-repository checks and independent assurance as pending. These are prior recorded results, not fresh acceptance results from this refresh.

### Release disposition and blockers

No installed-EUCLID acceptance result is established for canonical runtime/TURING dispatch, real empirical-state binding, host authorization, durable pre-mutation audit, shared-custody rollback/uncertain commit, restart, provenance, offline dependency closure, or normal/`-O` negative tests. No integrated test against approved AL HARAS/Salamander/identity/customer-entitlement/Hermitten sandboxes was run. Local bridge or packaging regressions do not close these gates. Mathematical evidence remains limited to the scopes and revisions recorded above; no blanket runtime or enterprise qualification is added.

To remove the blockers, provide a complete checkout path (or GitHub clone/read access), grant read access to Actions/check runs and required-check configuration, run the documented `scripts/run_clean_install.py` acceptance from the intended commit for Linux and Windows/Python 3.12 and 3.13, retain wheel/dependency/verifier hashes and both normal/`-O` outputs, and reconcile PR #98's body/commit mismatch. Then execute only those live enterprise integrations for which approved sandbox contracts and credentials exist, and obtain independent/security/operational/maintainer approvals. Do not merge, deploy, publish or claim production readiness beforehand.
