# TURING read-only promotion preflight — qualified startup correction

## Source and changes

Repository: PhiEnterprise1/EuclidPhiEnterprise. Implementation commit tested:
`a5aae0f450913bd933779ccb279233ec40f783aa` on
`fix/turing-readonly-promotion-preflight`, parent `5e00ee1d04bfc6ab9cd36d89dbaad1096354203a`.
Initial recovered source was main `fedf91ac7b327929a67bc0e5bc167de22080f1b7`;
the later main coordination commit changed only certification_status.md and
docs/LOCAL_AGENT_HANDOFF.md. Its added work was preserved, not overwritten.
PR139 is verified merged, not still awaiting merge.

Source/test Git blob hashes were checked against the implementation commit
before the final run: 22 files matched. This is isolated partial-source
qualification, not a claim of a clean complete checkout or full-repository test.
See source-binding.json for exact hashes and built artifact digests.

Reproduced defect: the CLI initialized subscription authorities and the customer
SQLite schema before promotion approval, even for the supposedly read-only
release-check. A refused startup could therefore write state, and inspecting
signed acceptance evidence unnecessarily required access to runtime signing keys.

Fix in services/turing-enterprise/src/hyba_turing_service/main.py:
- Separate policy/config loading from runtime authority/state initialization.
- Explicit release-check verifies image identity and signed evidence, then returns
  without opening runtime secrets, database or custody.
- Production serve/worker verify promotion admission before initializing state.
- Billing still refuses under deferred scope, without requiring financial/runtime
  secrets merely to report that refusal.
- Preserve current signed-risk-acceptance policy, strict default, source binding,
  freshness, all existing authorization, disjoint identities/keys and readiness
  rechecks. No approval is minted for deployment; no release gate is marked PASS.
- Keep explicit controlled-pilot semantics; it is not implicit production approval.
  Backup/restore behavior is unchanged by this correction.

Added 16 regressions in tests/test_startup_preflight.py. They use actual local
signature/file validation with ephemeral TEST authority. They cover keyless
read-only checks, absent approval, wrong image identity, publication gate,
rejected startup with valid keys, accepted startup still requiring keys,
explicit pilot checks, and deferred billing refusal. OPERATIONS.md explains
that evidence preflight is not credential, IdP, runtime or deployment acceptance.

## Executed commands and outcomes

From the recovered repository directory unless otherwise noted:

| Gate | Command | Result |
|---|---|---|
| Unchanged main service baseline | `/data/completion/venv/bin/python -m pytest services/turing-enterprise/tests -q --junitxml=/data/completion/baseline.xml` | 113 passed + 10 subtests; 0 failed/errors/skips; 1 dependency deprecation warning |
| Reproduce added regressions on original main.py | `.../venv/bin/python -m pytest services/turing-enterprise/tests/test_startup_preflight.py -q --junitxml=/data/completion/preflight-before.xml` | Exit 1: 14 failed, 2 passed; retained, not suppressed |
| Exact committed source after fix | `.../venv/bin/python -m pytest services/turing-enterprise/tests -q --junitxml=/data/completion/exact-commit.xml` | 129 passed + 10 subtests; 0 failed/errors/skips; 1 warning |
| Service wheel and sdist | `.../venv/bin/python -m build services/turing-enterprise --outdir /data/completion/dist` | Exit 0; both built |
| Separate installed-service-wheel suite | `.../wheel-venv/bin/python -m pytest services/turing-enterprise/tests -q --junitxml=/data/completion/wheel-tests.xml` | Same overlapping 129 passed + 10 subtests; 0 failed/errors/skips; 1 warning |
| Rebuild sdist | `.../venv/bin/pip wheel --no-deps /data/completion/dist/hyba_turing_service_control-0.2.0.tar.gz -w /data/completion/rebuilt` | Exit 0; 17 source/static files match original source |
| Formatting changed Python files | `.../venv/bin/black --line-length 100 --check services/turing-enterprise/src/hyba_turing_service/main.py services/turing-enterprise/tests/test_startup_preflight.py` | Exit 0; 2 unchanged |
| Dependency consistency | `.../venv/bin/python -m pip check` | No broken requirements |
| Only available deployment config | `.../venv/bin/python -m hyba_turing_service.main release-check --config services/turing-enterprise/deploy/service.example.json` | Exit 1: missing `/opt/service-source-commit`; no production image identity/approval supplied |

Do not add overlapping source/wheel counts. JUnit may include subtests separately.
The wheel import path was verified inside wheel-venv, not the editable service.
Real AL HARAS entitlements are source-owned in this partial tree, not a claim
that the complete AL HARAS distribution was built/installed. Both built wheel
and rebuilt sdist wheel match all 17 packaged service source/static files.

## Evidence boundaries and release disposition

PASS is scoped only to the tested startup behavior and package-content checks.
This does not promote the enterprise requirements matrix to PASS. The existing
23-section/17-deliverable/A-G acceptance register and the newer J01-J08 integrated
journeys still need their own required evidence.

This run includes real local file/signature/SQLite behavior. Existing service
HTTP, identity and runtime doubles remain labeled in their tests. No live IdP,
approved external sandbox, customer deployment, container, network actuation,
full native VQC suite, whole-repository suite, frontend accessibility run,
load/soak or target-host recovery was executed in this slice. Earlier native and
portal evidence is historical, not a fresh result for this implementation commit.

Commercial scope is unchanged: Hermitten avoided-cost data billing is separate;
future TURING/VQC contractual usage-based financial billing is deferred. Neither
is a production blocker. Current contract/membership/capacity gates stay mandatory.

Production: NOT DEPLOYED / NOT READY FOR CERTIFICATION. This branch is reviewable
functional correction, not a substitute for composed-system acceptance. No merge,
registry/image publication, production workflow dispatch or traffic switch occurred.
GitHub check-run access was previously unavailable; it was not polled again to
manufacture green evidence. The current coordination record reports CI billing
unavailability and assigns full local execution to the developer-side checkout;
this remote environment cannot execute on that machine or attest its results.

Exact remaining external inputs: an approved production target/deployment
connection and service origin; real IdP/client/callback/audience and secret-manager
bindings; returned exact-head full local/J01-J08/container/recovery evidence;
independent deployment-authority source-bound acceptance and named operational
owners. Newer local migration commit 21543c95 remains an unverified report, not
something this partial remote recovery can integrate or certify. No requested
device-bound claim is silently converted into hardware acceptance.
