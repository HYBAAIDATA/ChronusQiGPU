# Governed API release: evidence-path safety increment

## Status and scope

**NOT PRODUCTION READY. Draft integration increment; not a public release.**

Baseline inspected: `main`, `585d7b11d9cc8e183ff4d5cda44996a9ac30dc4e`.
No API handler, subsystem algorithm, authentication contract, package interface,
public version, frontend, authority decision or durable custody implementation is
removed or replaced by this increment. Lucas/Grover implementation is owner-held
and out of scope. No live pool submission, deployment or public publication was performed.

This increment repairs the existing assurance evidence route, rather than adding
endpoints or a second validator. It is not the requested complete governed API
integration. Endpoint reachability and full contract parity remain unaudited.

## Defects addressed

- Empty `results/` could pass the canonical rollup.
- Mandatory results, commit identity, digests and execution identity were unchecked.
- SKIP could satisfy gate execution; publication counted non-failing results as green.
- Promotion suppressed execution failures with `make -k gates || true`.
- Resilience checked test-file presence instead of executing the declared suite.
- Promotion receipt generation could read an incomplete result set without the
  canonical manifest validator.

## Canonical evidence route

`make gates` clears prior top-level result files before dispatch, including under
parallel make. Every existing declared gate uses `scripts/gate_runner.py`.
The runner obtains HEAD from Git (not a caller-supplied environment value), rejects
tracked changes before and after execution, records actual callable identity and
wall-clock execution bounds, normalises repository-contained artifact paths,
hashes evidence and referenced files, and writes the result atomically.

`config/assurance-gates.json` enumerates the eleven existing mandatory gates.
`scripts/assert_gate_rollup.py` is the sole validator reused by rollup, GitHub
publication and promotion-receipt issuance. All mandatory results must be PASS,
schema-valid, digest-valid and bound to the checked-out commit. Missing results,
SKIP, ERROR, FAIL, stale commits, duplicate identities, noncanonical filenames,
duplicate JSON keys, absent or altered artifacts, path escapes and symlink
escapes are rejected. JSON input is bounded at 4 MiB.

Promotion no longer suppresses gate failure, retains artifacts with `always()`,
and validates evidence even after dispatch failure. AL HARAS remains the
promotion authority: its existing receipt builder, approval requirements and
signing key requirement are unchanged.

Result fields preserved: `gate`, `status`, `reason`, `artifacts`, `started_at`,
`finished_at`. Additive schema-v2 fields: `source_commit`, `execution`,
`artifact_digests`, `evidence_digest`, `schema_version`.
Old result producers must regenerate evidence; legacy result files cannot promote.
No API contract is changed. This preserves evidence capability, not permissive
acceptance of a defective legacy file. `make gate-rollup` and existing script
entry points remain usable. A mandatory SKIP now returns a nonzero gate exit.

Digests establish integrity, **not producer authenticity**. The runner does not
certify canonical runtime identity, prevent an authorised writer from fabricating
new JSON, or prove that unit-test substitutes are real components. Existing
unit/assurance checks remain useful but cannot certify the API production voyage.

## API-release obligations

`config/api-release-gates.json` records 31 mandatory API evidence obligations,
using the same manifest schema and validator. Producers for those obligations are
not implemented in this increment. Do not fill them with generic assurance
results, canned success or the hermetic tests below.

```bash
python scripts/assert_gate_rollup.py --manifest config/api-release-gates.json
```

With no real API producer results, this is red. Neither assurance rollup nor the
new CI protocol workflow emits an API `production_ready=true` certificate.
Connecting those producers and a trusted production-component certification
chain remains required before that status can be derived.

Required application route remains:

`transport → identity → tenant → AL HARAS → validation → owning authority →
execution → verification → THESEUS/OVID → evidence → response → observability`.

Authority ownership remains EUCLID, PYTHIA, TURING, CHRONUS, THESEUS, OVID,
SALAMANDER and AL HARAS. This document specifies the intended boundary, not proof
that every runtime request already follows it.

## Validation performed

39 hermetic local tests exercise the runner, validator and publication consumer.
They use isolated temporary Git repositories, protocol-fixture evidence and
mocked outbound GitHub publication. Those mocks are **unit-test only** and are
not production-composition providers. Local validation occurs before the GitHub
commit and is not commit-bound release evidence. The PR CI workflow reruns these
tests on its checked-out revision; that too certifies only the gate protocol.

Python compilation and workflow YAML syntax checks were performed. Full
repository lint/format/test, actual resilience suite execution, installed package
and container voyages were not run in this partial MCP-downloaded workspace.

The tests plant protocol defects and verify rejection; this is not the requested
full API mutation campaign. Authentication bypass, wrong algorithm, wrong
CHRONUS route and fabricated live telemetry mutation tests remain unexecuted.

## Required delivery ledger

| # | Required report | Current evidence/status |
|---|---|---|
| 1 | Canonical API architecture | Intended route preserved; complete executable integration unverified |
| 2 | Complete endpoint inventory | NOT COMPLETE; control source inspected, repository-wide reachability not established |
| 3 | Every production-route authority mapping | UNVERIFIED |
| 4 | Authentication model | Existing operator-map/legacy key and guardian interfaces untouched; complete audit pending |
| 5 | AL HARAS authorisation model | Existing mediation/signing preserved; every governed side effect unverified |
| 6 | Tenant-isolation proof | NOT EXECUTED |
| 7 | Role/entitlement model | Existing model untouched; all-path consolidation unverified |
| 8 | API versioning policy | No version changed; first public release must be 1.0.0, subject to owner policy |
| 9 | Compatibility guarantees | No runtime APIs altered; mandatory evidence must regenerate to schema v2; contracts untested |
| 10 | Request/response/error schemas | Gate-result schema improved; application contracts unverified |
| 11 | OpenAPI/contract artifact | NOT GENERATED OR CERTIFIED |
| 12 | Idempotency | API side-effect retry semantics NOT EXECUTED |
| 13 | Concurrency | API state races NOT EXECUTED; make clears before recursive dispatch |
| 14 | Deadlines/cancellation | API propagation NOT EXECUTED |
| 15 | Long-running operations | NOT VERIFIED |
| 16 | Streaming/telemetry | NOT VERIFIED |
| 17 | Mining truth boundaries | Untouched; no live-pool validation |
| 18 | TURING algorithm identity | Untouched; voyage NOT EXECUTED; Lucas/Grover owner-held |
| 19 | CHRONUS provenance | Untouched; voyage NOT EXECUTED |
| 20 | THESEUS/OVID custody | Untouched; real persistence/restart NOT EXECUTED |
| 21 | SALAMANDER governed actions | Untouched; action/rollback voyage NOT EXECUTED |
| 22 | Frontend/API trust | Untouched; forged-identity attacks NOT EXECUTED |
| 23 | Security/adversarial results | Gate JSON/path/digest tests only; full API campaign NOT EXECUTED |
| 24 | Mutation results | Protocol defects rejected; full API transition mutations NOT EXECUTED |
| 25 | Production composition | NOT EXECUTED; mocks cannot qualify |
| 26 | Restart/replay | Gate-file readback only; real subsystem restart/replay NOT EXECUTED |
| 27 | Performance | NOT MEASURED |
| 28 | Chaos/failure | NOT EXECUTED against real subsystems |
| 29 | Clean-install package/container | NOT EXECUTED |
| 30 | Deploy sentry | NOT EXECUTED |
| 31 | Full repository suite | NOT EXECUTED |
| 32 | Release-gate manifest | Assurance manifest wired; API obligation manifest deliberately unsatisfied |
| 33 | Evidence digests | Protocol file hashes/local validation record; no production voyage digests |
| 34 | Source commit | Baseline above; increment commit returned by GitHub; actual gate runs bind HEAD |
| 35 | External dependencies | Canonical runtime, custody, policy config/keys, deployment and pool access not validated |
| 36 | Machine-derived readiness | No valid complete API evidence set; NOT PRODUCTION READY |

## Required counters

All twelve requested counters are **UNKNOWN / NOT PROVEN**, not zero:

- UNAUTHENTICATED_PRIVILEGED_PATHS
- FAIL_OPEN_AUTH_PATHS
- FAIL_OPEN_TENANT_PATHS
- CROSS_TENANT_VIOLATIONS
- SHADOW_AUTHORITY_IMPLEMENTATIONS
- FABRICATED_API_METRICS
- UNVERIFIED_PRODUCTION_ROUTES
- PRODUCTION_MOCK_SUBSTITUTIONS
- MISSING_MANDATORY_GATE_RESULTS
- FALSE_GREEN_READINESS_PATHS
- UNREVIEWED_PRODUCTION_ENDPOINTS
- OPEN_MATERIAL_API_DEFECTS

The API manifest exposes missing obligations mechanically. A complete inventory
and independently executed gate set are needed to derive the global counts.
Do not substitute zero because this increment introduces no new endpoints.

## Integration and remaining remediation

PR #135 (`repair/H-verification-release`) proposes overlapping rollup, make and
promotion changes. This PR is based on the immutable inspected main baseline,
not that unmerged branch. Reconcile overlapping hunks during review; preserve
H's unrelated ownership/defect work, incorporate any added required producers in
the manifest, and retain manifest/Makefile/implementation drift tests. Do not
merge both validators or restore optional mandatory skips.

Next work: finish the full externally callable surface inventory; trace trusted
identity/tenant/governance ownership for each caller; select an existing governed
operation and prove real execution, verification, custody, evidence, restart and
replay; then bind that proof and its negative/mutation voyages to the API
manifest. Correct replacements and caller migration must precede any retirement.
