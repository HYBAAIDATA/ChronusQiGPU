# Production evidence matrix

> Follow-up: tenant work from main PR #131 is reconciled in this branch. See
> [package/runtime qualification plan](PACKAGE_QUALIFICATION_PLAN.md) and
> `evidence/package-qualification/` for fresh results and unresolved gates.
> The 94-test figures below are the historical first-patch run at `22aa518`,
> not certification of later changes. Overall readiness remains blocked.

**Overall verdict: not yet production-ready.**

Status vocabulary: **declared** = required/described; **implemented** = code present
but its intended environment has not run; **measured** = fresh execution within
explicit scope; **partial** = only part of the production requirement measured;
**unproven** = no qualifying execution evidence. These are not readiness scores.

Evidence bundle: [`verification.json`](../../evidence/production-hardening/verification.json),
[all-tests JUnit](../../evidence/production-hardening/all-retrieved-green.xml),
[guardrail JUnit](../../evidence/production-hardening/focused-green.xml), and
[rebased-baseline JUnit](../../evidence/production-hardening/rebased-baseline-red.xml).
Test names below refer to
[`test_toe_unified_production_guardrails.py`](../../tests/test_toe_unified_production_guardrails.py).

| Claim / requirement | Status | Execution path and evidence | Limit / release implication |
| --- | --- | --- | --- |
| Single-ingest failures do not publish partial state | measured | `UnifiedDataLayer.ingest -> _transaction -> _apply_ingest`; `test_partial_ingest_never_publishes` injects compression failure and compares all live fields | In-memory only; no acknowledged-write durability |
| Grouped import and quarantine have atomic visibility | measured | `platform.import_records -> ingest_many -> ingest_atomic`; `test_atomic_import_never_exposes_active_quarantined_rows` plus merged atomic suite | Thread-level tests, not multi-process/database transactions |
| Public data reads do not expose mutable nested payloads | measured | `rows`, `scan_rows`, `snapshot`, `restore_payload`; `test_nested_payloads_are_detached_on_every_public_read` | Private internals are trusted, not an access-control sandbox |
| Import checks digest and retains source lineage | measured | `import_records`; `test_import_verifies_claimed_content_digest`, `test_import_retains_quarantine_and_source_lineage` | Retained metadata is not signed provenance |
| Lossy payload coercion is rejected | measured | `detached_payload`, strict canonical JSON; five invalid-payload regressions | Intentional API tightening: migrate tuples/objects/non-string keys before ingest |
| Contextual authorization and background parity | partial | Existing merged `SecurityModel` context isolation and monitor public methods preserved; reader-denial and background-identity regressions pass | No external IdP/endpoint qualification or whole-repository mutator inventory; see follow-up tenant gateway tests |
| Production tenant/security authority | partial | TenantGateway provides per-tenant state/allowlist/live membership; follow-up tenant-qualification suite measures completed revocation before dispatch for every operation | Host-authenticated principals, real endpoints and external adversarial qualification remain required |
| Retraining cannot opt out of validation | measured | `ModelRegistry.retrain -> _evaluation_guard`; `test_legacy_evaluation_flag_cannot_bypass_validation` | Initial `train` remains development-only |
| Model replacement is floor/non-regression/stale-safe in process | measured | Actual `kellogg.tensor_ml` training; merged promotion suite, floor tests, blocked stale-candidate race | No distributed registry CAS, independent validation authority or authenticated model recovery |
| Returned model records cannot mutate live state | measured | Defensive `get` and result copies; `test_returned_model_cannot_mutate_live_registry` | Does not protect against deliberate private-field access |
| Training/validation/promotion/execution separation | partial | Facade retrain requires train + promote capability; existing train overwrite bypass closed | Admin still holds multiple capabilities; no independent approval/evidence service |
| Offline data checkpoint and rollback to a new layer | measured | `checkpoint.save_checkpoint/load_checkpoint`; roundtrip, new-process recovery, governance/audit, corruption and replace-failure tests | Trusted single-writer POSIX files only; directory-fsync/host-crash/power-loss semantics not fault-injected |
| Durable platform restart / live-write recovery | partial | Data checkpoint primitive exists and runs | No WAL; no automatic data acknowledgement persistence; no model/security/connector/receipt recovery |
| Health unknown before observation; preflight != availability | measured | `Operations.availability`, `Probe.measured`, facade health; unknown/preflight/stale-probe tests | Recorded samples are not time-weighted uptime, vendor SLAs or a production SLO |
| Explicit failed readiness and production-start refusal | measured | `readiness`, `start(production=True)`; `test_production_start_and_readiness_fail_closed` | Deliberately blocks production approval |
| Bearer token cannot follow a foreign-origin redirect | measured | REST origin gate and redirect handler; actual two-loopback-server test records zero foreign requests | Does not qualify TLS policy, DNS/SSRF egress controls or all vendor protocols |
| Actual facade-to-data/model integration in focused closure | partial | 94 tests pass using actual facade, exact-linear implementation and data layer | TOE/Kellogg parent initializers intentionally bypassed; not an installed-package test |
| New regressions required in installed wheel/sdist gate | implemented | Extended existing `packaging/toe/build_and_verify.py` suite list; checkpoint file required; snapshot flag scrubbed | Harness wiring tested; artifact builds/installed checks not executed here |
| Whole-package imports, complete repository suite, remote CI | unproven | Normal import in partial snapshot fails at missing `toe.bridge`; exact limitation logged | Snapshot omission, not evidence that the full repo's bridge is missing/broken |
| Live operational deployment, throughput, SLA and fleet resilience | unproven | No deployment or load-test evidence generated | Production gate stays blocked |
| Physical QPU, universal speedup, ROI and legal/business outcomes | unproven | No such claim was tested or asserted | Keep outside production-critical acceptance |
