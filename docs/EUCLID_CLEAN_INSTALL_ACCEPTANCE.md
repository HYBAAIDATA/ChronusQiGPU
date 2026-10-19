# EUCLID installed-artifact acceptance

## Scope and repository/history findings

The requested build script and empirical bridge were absent at PR #74 head
`4226a3c93ca2e045976e0e648ec4a66db064d5a4`. Path history identifies their addition
at `c74c160db55fb6f84d54d68b03905b8c58937bb3`. They are present in current main;
this change hardens those owners, rather than inventing replacement names.

Repository-wide indexed searches covered EmpiricalStateBridge,
EmpiricalStateController, empirical_state, build_standalone_wheel and
HashChainAudit, including returned legacy/archive matches. Related current
runtime, native registration, custody, packaging, tests and workflows were read.
This is a task-scoped repository-wide symbol/path scan and relevant-path history
review, not a claim to have read every file, historical branch or deleted symbol.

Existing owners retained:

- `euclid.runtime.EuclidRuntime`: supported general composition and dispatch.
- `euclid.intelligence_bridge`: existing registry -> Guardian -> creator-rights path.
- `Intelligence.proof_capability` and `repository_review_capability`: real native registrations.
- `al_haras.audit.HashChainAudit`: durable pre-effect admission/completion.
- `CompositionRoot.data_port("euclid")`: one shared persistent custody fabric.
- Existing adaptive-learning custody and cross-process restart contracts: no new learner.
- `Intelligence.empirical_state_controller.CommissionedSCM`: separate existing mining
  evidence/actuation owner, not the operational reliability-weight compatibility API.
- `packaging/euclid-engine/build_and_verify.py`: retained research-product gate.
- `scripts/installed_wheel_e2e_gate.py`: retained historical mining-umbrella gate;
  it does not qualify the dedicated `euclid-engine` enterprise artifact.

## Changes and security migration

`EmpiricalStateBridge()` now denies mutation without an explicit host authorizer,
a durable AL HARAS audit ledger and a shared data port. A token's length is never
authorization. Compatibility callers must supply those controls; there is no
public/default operator credential or insecure opt-in.

Production requests use `bind_empirical_state(runtime, data_port=existing_port)`
from `euclid.capabilities.empirical_runtime`, then
`runtime.dispatch_specialist("empirical-state", ...)`. Binding creates no rights,
subscription entitlement, guardian, learner, private store or prior-memory identity.
The host must configure AL HARAS and explicitly grant the creator-scoped
`empirical-state.request` dispatch right. The supported operation is
`UPDATE_RELIABILITY`, with arguments `state_payload`, `deadline_epoch`, `max_budget`.
The equivalent canonical convenience method is
`runtime.bind_empirical_state(data_port=existing_port)`. One successful transition
costs one budget unit. Budgets are per-request envelopes,
not a cumulative tenant billing/quota service.

The facade `UnifiedIntelligenceGatekeeper` is a trusted-host compatibility API,
not a replacement for canonical runtime authorization. Durable state receipts
remain visible after restart; an empty audit trail is not a fresh identity test.
A different owner cannot adopt another owner's operational custody envelope.

Admission is durable before the controller is called. Execution failures restore
and verify the complete operational snapshot. Publication uses the existing shared
port and verifies readback. If custody or completion persistence fails after an
attempted publication, `StateCommitUncertain` blocks retry. On reopen, a persisted
state without its matching durable completion also refuses. Operators must
reconcile retained custody and audit evidence before resuming; this change does
not supply an automatic recovery procedure or promise distributed/crash atomicity.
The host must retain **both** custody and audit directories across restart and
provide one writer for this operational state stream. Thread calls on that writer
are serialized; stale local writers are refused. Cross-process multiwriter
linearizability, hostile-host isolation, WORM storage and hard deadline preemption
are not claimed. Deadline overrun during custody publication is uncertain failure,
not a successful rollback.

## Reproduce

Start from a clean committed checkout containing the consolidated review head.
Changes must be committed before the provenance gate can pass. Build-tool setup:

```bash
python -m pip install 'build>=1.2,<2' 'setuptools>=77,<81' wheel
python scripts/run_clean_install.py \
  --expected-commit "$(git rev-parse HEAD)" \
  --output-dir /absolute/path/outside/repository/euclid-evidence
```

PowerShell (propagates every failure):

```powershell
python -m pip install "build>=1.2,<2" "setuptools>=77,<81" wheel
.\scripts\verify_clean_install.ps1 -ExpectedCommit (git rev-parse HEAD)
```

The build resolves dependency wheels for the **current Python/platform** into the
output directory. It does not call a wheel with unbundled dependencies an offline
bundle. To build without index access, supply a complete compatible dependency
wheelhouse via `--offline --wheelhouse PATH` (`-Offline -Wheelhouse PATH` in PS).
Build tools must also already exist in that environment. The acceptance install
always uses `--no-index --find-links`, regardless of build-time mode.

Choose a fresh output directory for each run; existing wheels are never deleted.

Artifacts: `euclid_engine-*.whl`, dependency wheels, `build-manifest.json`,
`verification.json`, `terminal.log`. The manifest binds the actual source commit,
enterprise wheel, every wheel member, dependency wheels and verifier. Wheel
selection is invocation-specific, never "newest file in dist". Staging uses only
Git-tracked source files and verifies all staged Python hashes against the wheel;
ignored local source/state files cannot leak into the artifact. Actual imports
must lie inside this venv's purelib/platlib, never a path merely containing the
text `site-packages`. The copied verifier runs from an empty external directory
under `python -I`, both normally and with `-O`.

Native installed checks cover Conjecture, source-bound Review, operational State,
explicit profiles/catalog, invalid entitlements, missing/revoked rights, exhausted
budget, expired deadline, unapproved operation, durable admission, rollback,
learning/state/audit restoration in an independent process and fresh rights.
Existing canonical bridge regressions, updated compatibility regressions and new
bridge regressions also execute against the installed wheel in both modes.
Dynamic/optional imports and arbitrary capabilities are not qualified merely by
static staging, `pip check`, or success on these selected paths.

## Evidence status at implementation

Locally executed on the connector-fetched selective source set:

- Original bridge accepted an arbitrary long token with no durable audit configured.
- 20 bridge regressions passed normally and under `python -O`.
- 8 packaging regressions passed normally and under `python -O`.
- Changed Python compiled successfully.

The local bridge tests load the actual bridge and unchanged AL HARAS audit as
standalone modules; DiskPort is an explicit test double. They do not qualify the
full canonical composition or installed wheel. Packaging unit tests use synthetic
fixtures, never a fabricated release artifact. No complete checkout or GitHub
execution API is available through the exposed connector.

Black formatting and Ruff F/E9 diagnostics passed on the nine fully revised Python
files. The runtime entry-point addition is a targeted insertion; surrounding
legacy runtime formatting is preserved, not presented as a whole-file lint pass.
A real build/pip pipeline also passed on a clearly labelled synthetic committed
fixture; it is not an EUCLID release artifact.

The new CI matrix performs full-checkout installed-artifact acceptance on Linux
and Windows, Python 3.12 and 3.13, retaining success **and failure** output. Its
results remain pending until actually executed and inspected. No full-repository
pytest/lint/security pass, independent assurance, production readiness, release,
package publication, merge or deployment is asserted by this implementation.
