# Production-readiness assessment and remediation backlog

## Verdict

**NOT YET PRODUCTION-READY.** Targeted hardening is implemented and measured, but
this is not sufficient evidence to authorize enterprise live deployment.
The runtime exposes failed readiness and refuses explicit production startup.
No deployment, publication or merge to `main` was performed by this change.

## Fresh verification

After reconciling the concurrent PR #130 merge at
`da432bbe4e59855f7c8a6ec3028217e57ca59f25`:

- The 48-test guardrail suite produced **31 failures / 17 passes** against the
  rebased baseline, then **48 passes / zero failures / zero skips** with the patch.
- The complete **retrieved** local suite produced **94 passes / zero failures /
  zero skips**, including merged atomic-import and promotion tests.
- Six concurrency-focused tests passed on each of three additional runs.
- Python compilation and focused Ruff F/E9 lint passed. The existing package-gate
  help entry point ran.
- Normal package import in this partial source snapshot fails at missing
  `toe.bridge`. That module was not retrieved: this is an environment limitation,
  not a finding that the repository itself lacks it.

The machine-readable [verification log](../../evidence/production-hardening/verification.json)
contains commands, timestamps, interpreter/dependency versions, outcomes, source hashes
and explicit exclusions. Raw logs and JUnit XML are retained next to it.

### What the tests actually execute

The retrieved source closure uses real `toe.unified`, real `toe.operator_compilers`,
real `toe.receipts`, real `kellogg.tensor_ml` and real `kellogg.exact_tensor` code.
Model fitting is not replaced with a fake predictor; race tests only intercept
scheduling around the real fit. The redirect attack test uses real loopback HTTP
servers. Recovery loads a real checkpoint in a fresh Python process.

The snapshot runner **intentionally bypasses `toe` and `kellogg` parent package
initializers**, since their full import closure is not available locally. It does
not bypass the unified facade initializer or replace its implementation. These
results cannot qualify real top-level imports, installed wheels or the whole repo.
The installed-artifact harness removes `EUCLID_FOCUSED_SNAPSHOT` and rejects namespace
package origins, so this runner cannot substitute for release verification.

### Exact access limitation

The connected GitHub tool can read source and create review-branch commits.
The computer has no authenticated Git clone credential: `git ls-remote` returned
exit 128, `could not read Username for 'https://github.com'`.
No Actions-run/artifact-reading tool is exposed by the available GitHub connection.
No CI run status, permission denial from an Actions token, or CI success is claimed.
The readable workflow definitions and successful local tests are not CI evidence.

## Targeted implementation changes

- Rollback-safe **single ingest** as well as existing grouped atomic imports.
- Strict, detached JSON payloads; detached indexed/scanned records and policies;
  source lineage retained and published with quarantine state.
- Existing merged authorization, service-actor and analysis APIs preserved;
  retraining adds a promotion capability and user-specific feedback/dashboard checks.
- Existing model validation becomes mandatory for every retrain, including legacy
  bypass flags. Existing names cannot be overwritten through initial `train`.
  Registry floors cannot be weakened per call; training history fingerprints are
  accumulated; returned records detach from live state.
- Offline, versioned data checkpoint/recovery with checksum and state-consistency
  checks, POSIX fsync/atomic replacement and deterministic batch continuation.
- Unknown availability, measured-vs-configuration probe distinction, freshness
  status, explicit readiness blockers and production-start refusal.
- REST scheme/origin and redirect checks prevent cross-origin bearer forwarding.
- Existing artifact gates extended rather than replaced with a snapshot workaround.

Two existing tests intentionally migrate to the stricter contract: the model
regression fixture now uses actually held-out feature values, and the stale-model
race replaces the intervening model through validated retrain rather than the newly
forbidden `train` overwrite. Neither migration weakens its asserted safety outcome.

## Blocking remediation backlog

Every item below is a **release blocker**, not optional deferred work. The partial
consumer must remain out of production-critical deployment until closure.

| Priority / owner role | Open risk | Minimal next step and required evidence |
| --- | --- | --- |
| P0 / security + platform | No verified tenant principal/IdP boundary; in-process actor selection and public components remain trusted | Wire host-validated tenant/actor contexts through every exposed mutation and background job; test forgery, tenant crossover, role revocation, missing dependencies and deny-before-side-effect behavior against actual service endpoints |
| P0 / ML governance | Initial `train` directly bootstraps a live development model; admin can combine training/promotion; held-out independence is not externally attested | Split staged training, validation, independent approval and execution; require immutable dataset/model/evidence digests, approvals, freshness limits, representative validation and durable CAS promotion receipts, including negative tests |
| P0 / storage + SRE | Checkpoints are offline data snapshots, not durable live acknowledgements or complete platform recovery | Integrate a durable transaction/WAL and approved model/role/receipt/configuration recovery; kill/restart the actual runtime, verify committed/uncommitted outcomes, corruption handling, concurrent writers, rollback authorization and measured RPO/RTO |
| P0 / release engineering | No full checkout, wheel/sdist installed run, or complete repo/remote CI result in this session | Provide a complete source archive or authenticated test checkout; run the existing TOE build-and-verify and enterprise clean-install gates on exact artifacts, plus the complete required repository suites; retain commit/artifact hashes, logs and results |
| P0 / SRE | No deployed operational probes, time-weighted SLIs, fresh dependency evidence or load/failover measurements | Deploy only to an isolated qualification environment; bind genuine health probes, timestamps and outage windows; exercise dependency failure, recovery and alerting; verify readiness remains failed for absent/stale evidence |
| P1 / storage performance | Full-state staging and defensive copies have unqualified O(store-size) cost | Measure memory/latency/throughput at target scale; introduce bounded transactional storage and quotas without weakening failure atomicity; rerun fault/concurrency tests |
| P1 / security + SRE | Checksum is not backup authentication; trusted paths/single writer; no Windows or network-filesystem durability evidence | Define backup threat model, authenticated artifact custody, filesystem/path/size limits and key management; qualify intended OS/filesystem; keep unsupported modes unavailable |
| P1 / connectors | Redirect check does not establish a complete outbound network policy, TLS posture or vendor health | Add TLS/egress/DNS/SSRF policy and real vendor smoke tests using authorized nonproduction credentials; prove timeouts/redaction/failure receipts without claiming unbound catalog entries are integrations |
| P1 / product + architecture | Broad repository claims, alternate entry points and facade consistency not exhaustively audited | Inventory actual public/package/runtime entry points, map claim->execution->fresh test/receipt, isolate experimental/advisory surfaces and qualify every production-critical path |

## Reproduction

On a **complete checkout**, use normal imports and the ordinary test/package gates:

```sh
python -m pytest -q tests/test_toe_unified_production_guardrails.py \
  tests/test_toe_unified_atomic.py tests/test_toe_unified_promotion.py \
  tests/test_toe_unified_intelligence.py
python packaging/toe/build_and_verify.py
# Then run the repository-required broader suites and enterprise clean install.
```

Only when deliberately reproducing the limited retrieved closure:

```sh
python evidence/production-hardening/run_snapshot_tests.py "$PWD" tests -q
```

A successful snapshot run must never be reported as installed-package, fleet,
security-boundary or production-readiness certification.
