# Installed-artifact and runtime qualification plan

**Current status: NOT YET PRODUCTION-READY.** This is an executable release plan,
not an authorization to deploy or publish. Library hardening and package gates do
not substitute for external identity, recovery, independent model governance or
operational qualification.

## Baseline and first patch set

Main is pinned at `39c2f3b755e65e48b02e39a26acc8a996e0e3fc2` (PR #131).
PR #132's first patch was `22aa518ce1ed0b177fe4fd4233f8bb4319edd98c`.
The follow-up reconciles PR #131's tenant routing, role revocation, receipt tenant
binding and public exports without removing PR #132's integrity/model/status fixes.

The existing TOE gate already builds a wheel/sdist, installs the wheel outside the
checkout and rebuilds/reinstalls from the sdist. The patch strengthens that gate;
it does not present a duplicate workflow as a new capability.

Changes in this pass:

- Both release and unified test invocations use isolated installed-package imports,
  scrub source/snapshot/pytest overrides and avoid repository conftest/plugins.
- Require passing, nonempty JUnit collection from **each** named module, zero
  failures/errors/skips, and a zero subprocess exit. Reject contradictory XML.
- Bind installed-test records to input artifact and copied-test SHA-256 values;
  retain origin probe logs, pytest logs and JUnit XML.
- Bound subprocess/test execution; retain stage, exception and failed/incomplete
  attempt evidence if the ordinary build/install/test path fails.
- Upload qualification evidence with `if: always()`; the release verdict still
  depends on the installed matrix and source gate. This does NOT configure a
  protected-branch required status check; repository administrators must do that.
- Keep tenant and checkpoint/integrity regressions in installed qualification.
  Add tests proving completed revocation is checked before dispatch for **every**
  operation in the tenant allowlist and that tenant admins cannot dispatch host controls.
- Correct package/build/workflow repository provenance to the actual target.

## Exact files and execution paths to inspect

| Boundary | Files | Required evidence |
| --- | --- | --- |
| Package staging/import | `packaging/toe/pyproject.toml`, `packaging/toe/build_and_verify.py`, `packaging/kellogg-tensor/build_and_verify.py`, `toe/__init__.py`, `kellogg/__init__.py` | Complete source inputs, wheel/sdist manifests, exact archive hashes, every shipped module import and real top-level public API |
| Installed facade/tenancy | `toe/unified/__init__.py`, `platform.py`, `tenancy.py`, `security.py`; authority/tenancy/tenant-qualification suites | Imports resolve inside the qualification interpreter's site-packages; real facade execution; tenant separation and completed-revocation checks |
| Ingest/recovery | `data_layer.py`, `checkpoint.py`; atomic and production-guardrail suites | Failed import leaves state unchanged; new-process checkpoint restore, corruption failure, replace failure preserving prior checkpoint |
| Model safety/rollback | `intelligence.py`, platform train/retrain/watch/background paths; promotion suite | Fresh held-out/floor/non-regression/stale-CAS results; separately implement/qualify authorized durable rollback and independent promotion |
| Required release checks | `.github/workflows/toe-release.yml`; enterprise clean-install workflow | Commit-bound successful matrix and release verdict, retained failure/success artifacts, branch/ruleset enforcement confirmed by administrator |
| Runtime security/operations | Actual host IdP, tenant/session entry points, runtime orchestration and deployment configuration | Authenticated endpoint adversarial tests, load/failover/crash evidence, measured health and agreed SLO windows |

## Exact runnable commands

Use a **complete clean checkout of the review candidate**, not this partial source
snapshot. Review the diff before executing it. Do not publish or deploy as part of
qualification.

```sh
git rev-parse HEAD
git status --porcelain
# Expected: the reviewed candidate SHA and no unreviewed source changes.
python -m venv /tmp/euclid-toe-qualification
. /tmp/euclid-toe-qualification/bin/activate
python -m pip install --disable-pip-version-check \
  'numpy>=1.26,<3' 'pytest>=7.4,<10' sympy 'PyYAML>=6,<7'

# Small gate-unit checks first; these do not qualify product artifacts.
python -m pytest --noconftest -q tests/test_toe_package_qualification.py

# Actual build: exact local KELLOGG dependency, TOE wheel + sdist, clean installs,
# top-level/all-module/public API probes, real facade and tenant/regression tests,
# then sdist-rebuilt wheel subjected to the same installed checks.
python packaging/toe/build_and_verify.py

# Separate source/integration checks, not substitutes for the installed gate.
python -m pytest -q tests/test_toe_unified_*.py
# Provision the repository's required broader dependencies/services, then:
python -m pytest -q
```

Run the gate independently on Python 3.11/3.12/3.13 using the existing CI matrix.
Its current matrix rebuilds artifacts per interpreter; matching deterministic
fixtures does NOT mean one identical wheel was tested across all interpreters.
If releasing a single canonical wheel across versions is required, additionally
install **that exact archive SHA** on every supported interpreter and retain the
results. Do not label the present rebuild matrix as that stronger evidence.

Read `packaging/toe/dist/qualification-attempt.json`, the artifact verdict,
`installed-unified/**/evidence.json`, `installed-release/**/evidence.json`, their
logs/JUnit and the archive manifests. An attempt marked failed/incomplete, missing
file, nonzero exit, missing suite or skip is not a pass. A green artifact verdict
means **artifact verification only**, never live production certification.

## Current measured evidence and exclusions

See `evidence/package-qualification/verification.json` for the final executed
commands/counts/hashes. Gate unit fixtures simulate child outcomes only to test
failure handling; no simulated outcome is counted as product-artifact success.

The actual build command was attempted and failed at the declared-source preflight:
this computer does not have the complete retrieved release closure (including
`toe.bridge`, machine/problem, package resources/release tests and LICENSE).
The failure receipt lists exact missing paths. These are **snapshot omissions**,
not claims that these files are absent from GitHub. No wheel/sdist was built or
installed in this pass.

Source regression execution still uses namespace parents for `toe` and `kellogg`.
Three actual-tomography tests fail when included because `toe.bridge` was not
retrieved. Their failures are retained. The separately selected passing run
explicitly deselects those tests; it is not a clean full suite or artifact run.
The installed gate never inherits that namespace flag.

The source connection can read/write review commits; computer clone authentication
and an Actions run/artifact reader remain unavailable. No CI-token denial or CI
success is asserted. Provide a complete source archive or authenticated approved
qualification checkout to close the immediate build-input limitation.

## Blocker list and acceptance criteria

| Gate | Current evidence class | Close only when |
| --- | --- | --- |
| Gate failure/isolation logic | measured within unit scope | Negative regressions pass; ordinary failures retain honest receipts; required suite collection cannot silently disappear |
| Installed wheel/sdist and top-level API | implemented / unproven execution | Full clean build, installed probes, all selected suites and sdist-rebuilt wheel pass on exact artifacts and supported environments |
| CI + protected branch policy | partial / unproven execution | Real run/artifacts available; all required checks pass on candidate SHA; administrator confirms ruleset cannot be bypassed in ordinary merges |
| Tenant authority | measured in-process / partial production | Every real endpoint validates host-authenticated actor/tenant/session, revocation and downgrade before side effects; tenant callers cannot access host controls; external adversarial evidence retained |
| Data checkpoint and atomic import | measured locally / partial durability | Integrate approved live durability; kill/restart actual runtime at commit boundaries, validate RPO/RTO, corruption and concurrent writers on supported filesystem |
| Durable model rollback | unproven | Authorized rollback restores an approved prior model after real process loss, preserves dataset/model lineage, cannot overwrite newer state, and has independent evidence/approval |
| Cross data/model atomicity | unproven | Define the actual joint mutation contract and coordinator; inject failure before/after each boundary and prove all-or-nothing durable outcomes, or deny unsupported joint production operations before side effects |
| Independent model governance | partial | Govern initial training as well as replacements; separate training/validation/promotion/execution authority and persist evidence-bound approvals |
| Deployment/SLO/failover | unproven | Agree service targets and observation windows; execute real health/failure/latency/load/failover/rollback tests with timestamped runtime evidence and alerts |

**READY** requires every production-critical gate to have fresh passing evidence
bound to the candidate, artifacts and intended runtime. Unknown/missing/expired
critical evidence means **NOT READY**, not success or a waiver. Ordinary failure
receipts do not cover hard process termination, power loss or unavailable runners.
Those require the independent failure qualification above.
