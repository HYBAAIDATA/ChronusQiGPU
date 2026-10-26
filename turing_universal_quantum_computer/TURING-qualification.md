# TURING — software release qualification

**Decision: outstanding qualification waived by operator; deployment not executed.**

**Current installed-EUCLID acceptance: HOLD.** The newest recovery/artifact
addendum below records unverified mandatory acceptance. Historical operator
risk acceptance remains scoped to its original decision, not passing evidence.

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

The table retains the pre-waiver evidence state. The superseding operator
disposition below closes outstanding qualification requirements by risk
acceptance, not by converting them into passing test results.

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
- PRs #96, #97, #98 and #110 are all open and unmerged. At the start of this review, PR #96 was head `405414903301c7ff5dae56e40adedb029a4a141e` from `feat/turing-package-organization-20261019`, based on `main` at `af4e34a3c9463750dc32bcd1eae41f7310944833`. The acceptance addendum first landed as commit `71c2ea3d28c636e68aa203bc2930208d7d8679ca`; this follow-up is also ledger-only, so consult the live PR page for its current head. PR #97 is head `a61a9dd1e34e23d3bcd2533089a001d50bc07c0a`, also based on that older `main` commit. PR #98 is head `9f0e4bb89507be9e141a89f79f05493f7b397362`, based on the PR #96 branch at `356ab419dae197f407989da82feaa2f149da08e7`; that base is an earlier PR #96 commit, not its current head. PR #110 is head `87dce11dfc84de7d283300ea9921ecd558b9187e`, based on current `main` at `5a4e120297d8106dfe1c1f8ba4d7e3baa913b43d`; its live GitHub state is `open`, `draft=false`, `mergeable_state=blocked` (despite the task context calling it a draft).
- The PR #98 description claims a billing-scope correction at `cf56d0aaa7c427e7319c86af979cec1a5d808570`, but its live head and commit list contain only `d3d2366de27b788398f578b725f7dbd09d43b1dd` and `9f0e4bb89507be9e141a89f79f05493f7b397362`. The claimed correction is not present in that PR's current commit list. Treat the billing/Hermitten scope as unresolved until the branch and contract are reconciled. PR #97's proposed Hermitten receiver is not evidence of live Hermitten conformance.

### Acceptance execution and CI access

- Attempted `git clone --filter=blob:none https://github.com/PhiEnterprise1/EuclidPhiEnterprise.git EuclidPhiEnterprise`; it exited 128 with `fatal: could not read Username for 'https://github.com': No such device or address`. No complete checkout was obtained, so no product artifact was built or installed in this refresh and no repository test suite was rerun.
- GitHub `get_check_runs` for the four PR heads was denied with `403 Resource not accessible by personal access token`. For PR #110, combined status returned `pending`, `total_count=0`, `statuses=[]` at head `87dce11dfc84de7d283300ea9921ecd558b9187e`. This proves an access/visibility gap, not a CI failure or a pass. Workflow run details and required branch-protection checks remain unverified.
- Existing PR #110 `reports/euclid_clean_install/local_validation.json` records selective-source evidence only: 20 bridge tests and 8 packaging tests in normal and `-O` modes, focused Ruff and Black checks; the build/pip pipeline used synthetic fixture sources and the focused bridge used `DiskPort`. The report explicitly marks full enterprise-wheel install, canonical installed native paths, cross-process shared-custody acceptance, Linux/Windows CI, full-repository checks and independent assurance as pending. These are prior recorded results, not fresh acceptance results from this refresh.

### Release disposition and blockers

No installed-EUCLID acceptance result is established for canonical runtime/TURING dispatch, real empirical-state binding, host authorization, durable pre-mutation audit, shared-custody rollback/uncertain commit, restart, provenance, offline dependency closure, or normal/`-O` negative tests. No integrated test against approved AL HARAS/Salamander/identity/customer-entitlement/Hermitten sandboxes was run. Local bridge or packaging regressions do not close these gates. Mathematical evidence remains limited to the scopes and revisions recorded above; no blanket runtime or enterprise qualification is added.

To remove the blockers, provide a complete checkout path (or GitHub clone/read access), grant read access to Actions/check runs and required-check configuration, run the documented `scripts/run_clean_install.py` acceptance from the intended commit for Linux and Windows/Python 3.12 and 3.13, retain wheel/dependency/verifier hashes and both normal/`-O` outputs, and reconcile PR #98's body/commit mismatch. Then execute only those live enterprise integrations for which approved sandbox contracts and credentials exist, and obtain independent/security/operational/maintainer approvals. Do not merge, deploy, publish or claim production readiness beforehand.

## Superseding operator disposition — explicit risk acceptance

The operator explicitly authorized qualification waivers and committing the
result to `hyba-data-evolution`. The historical baseline is
`4b75ace56712501f7d091e33d386df64ade9ba1b`; the actual branch base is
`d5baa2e89806a1b25ca33db746fc284c6d4793f0`, retaining merged PR #139.
The earlier sections remain historical evidence, not current PR-state claims.

Outstanding qualification requirements are **WAIVED BY OPERATOR**, not PASS.
The named architectural bypass, incomplete orphan recovery and outstanding
regression selection are accepted risks, not repaired defects. CI visibility
remains UNVERIFIED; the 403 is not converted into a CI verdict. The supplied ZIP
has content identity, not fabricated Git checkout identity. No blanket claim of
mathematical validity, artifact parity or enterprise acceptance is added.

The service now supports explicit, signed, source-bound risk acceptance under an
opt-in qualification policy while keeping strict promotion as the default.
Runtime authorization, identity, custody integrity and readiness stay active.
Deployment remains NOT EXECUTED: no target connection, actual IdP configuration,
production secret bindings or deployment-authority signed bundle was supplied.
The operator waiver removes qualification sign-off as a policy blocker; it does
not manufacture these execution inputs or imply publication rights.

Machine-readable scope and the focused verifier test results are retained at
`../services/turing-enterprise/evidence/operator-risk-acceptance/`.


## Installed-EUCLID recovery and artifact-ownership follow-up (current mandate)

**Decision: HOLD / NOT PRODUCTION-QUALIFIED.** No merge, deployment, publication,
permission change, or required-check bypass was performed. This addendum does
not reclassify historical waived gates as passes or cancel the historical risk
acceptance policy. The current acceptance request requires explicit verification.

### Actual reconciliation, not reopening old PRs

Reviewed baseline: `fedf91ac7b327929a67bc0e5bc167de22080f1b7`. Main advanced by
one documentation-only commit to `5e00ee1d04bfc6ab9cd36d89dbaad1096354203a`;
that is this follow-up branch's actual base. Newer service/console/risk-acceptance
implementations are preserved.

- #96, #97 and #110 are closed **merged**; #110 is no longer a draft/open task.
- #98 is closed **unmerged as a PR**, but that does not mean its code is absent.
  GitHub's commit listing from the pinned main revision includes the exact heads
  `754e46449c89f5f6741032469f364bb59d5c40b6` (#96),
  `a61a9dd1e34e23d3bcd2533089a001d50bc07c0a` (#97),
  `9f0e4bb89507be9e141a89f79f05493f7b397362` (#98), and
  `87dce11dfc84de7d283300ea9921ecd558b9187e` (#110), as well as scope correction
  `cf56d0aaa7c427e7319c86af979cec1a5d808570`. They must not be blindly reapplied.
- Later scope reconciliation and the 2026-10-22 completion report retain financial
  billing/Hermitten as DEFERRED, not mandatory current nonbilling acceptance.
  No live financial conformance is claimed or fabricated as a release blocker.
- Repository-wide qualification is **not complete**. MCP source/history searches,
  owner contracts and targeted source blobs were reviewed; the executable local
  tree remains selective, not a complete checkout or exhaustive test inventory.

### Repository-side changes in this follow-up

1. Durable PREPARED intent binds a candidate to its receipt, owner, prior state,
   prior binding and exact envelope hash before custody publication.
2. Explicit host-authorized recovery validates durable admission/preparation and
   committed ancestry before recording recovered completion. Missing authority,
   stale/tampered/legacy-ambiguous state, corrupt audit and conflicting evidence
   remain closed. No automatic rollback or recovery permission is invented.
3. Restore now binds completion to the actual custody binding, not merely to a
   copied receipt. Receipt schema and durable restore requirements are checked.
4. The enterprise candidate builder preserves CAP-07 ownership: builds the actual
   TURING and Kellogg project manifests, declares separate owner dependencies,
   excludes their roots from the EUCLID import closure, rejects wheel overlaps,
   and records original members of each of the three owner artifacts. Pydantic
   is declared consistently with the current root runtime dependency contract.
5. The installed verifier checks member bytes and now includes canonical TURING
   dispatch/shared replay and actual shared-port uncertain-publication recovery.
   These expanded native gates are **implemented but not executed here**.

### Fresh executed evidence and precise limits

Retained at `reports/euclid_clean_install/recovery_refresh/`: reproducible runner,
source SHA-256s, normal/optimized logs, access/preflight failures and JSON summary.

- Linux / Python 3.13: **39 bridge/recovery unit tests normal; 39 under -O**.
  Real unchanged AL HARAS HashChainAudit; DiskPort custody double. Includes a
  process deliberately terminated immediately after publication and recovery
  in a separate fresh process. This is not actual OVID restart qualification.
- **12 packaging/provenance tests normal; 12 under -O**. Real setuptools/build/pip
  exercise three explicitly synthetic owner fixtures; not product wheel installs.
  Negative checks include installed member tampering, wrong source revision,
  missing owners, vendored owner paths, overlap and dirty/uncommitted source.
- Focused Black/Ruff/compilation results are retained. No full engine, blanket
  mathematical, full-repository or cross-platform pass is asserted.
- A fresh sandbox Git access probe exits 128: `could not read Username` with
  terminal prompts disabled. MCP read/write access does not authenticate git.
  The actual clean-install runner exits 1 at ancestry preflight because the
  selective tree is not a Git checkout. No product wheel is built or installed.
  Git identity has not been fabricated to defeat that check.
- GitHub Checks still returns **403 Resource not accessible by personal access
  token** on #110's head; combined status is pending with zero statuses. This is
  a permission/visibility denial, not a workflow failure or success. Actions logs,
  mandatory check names/protection and the remote matrix remain UNVERIFIED.

The prior completion report's 556 VQC tests + 111 subtests and 3 native integration
passes remain historical results for its recorded source/snapshot. They were
not rerun here and do not qualify this changed artifact set.

### Outstanding actions / acceptance decision

| Gate | Present status | Action to remove blocker |
| --- | --- | --- |
| Full source and installed package | BLOCKED at authentic-checkout preflight | Run the follow-up commit from a complete authenticated checkout with the documented external-environment command; retain exact source, all three wheels, dependency closure, member hashes and normal/-O results |
| Canonical runtime/math | Expanded native gate NOT RUN; historical evidence retained | Run actual EUCLID/TURING/Kellogg consumer and affected full mathematical suites against final artifacts, including wheel/sdist parity where required |
| Recovery/security | Focused local regressions PASS only | Run native shared-custody interruption/tamper/stale/failed-recovery gates; review real independent recovery policy, single-writer maintenance and legacy orphan disposition; obtain security/SCA/signing review |
| CI/platform | Remote UNVERIFIED; Linux Python 3.13 unit evidence only | Authorized CI reader/repository maintainer supplies required-check configuration and actual Actions outputs; execute supported Linux/Windows Python 3.12/3.13 matrix; do not change permissions or bypass checks |
| Enterprise integration | NOT live-qualified | Approved identity/tenant/entitlement and AL HARAS/Salamander/custody serving composition must run actual sandbox acceptance; host fault/rollback/load/restore drills and accountable owner approvals remain required |
| Financial integration | DEFERRED in recorded nonbilling scope | Do not resurrect Hermitten requirements without an effective contract/scope change |

Source-only implementation uncertainty and unexecuted affected native gates remain;
this is not a finding that all repository-side work is complete. Production
readiness is **NOT ESTABLISHED**. No deployment or publication was attempted.
