# Agent 1 — integrated launch prerequisites, not launch completion

## Candidate and disposition

- Working repository: `HYB-APHIDATA/HYBAEnterprise`.
- Main observed through GitHub at `b131edc408a37ff7c03534d694bfcdaf0c827abb` on 2026-10-25.
- Agent 1 branch: `agent1/integrated-launch-qualification-20261025`, created at PR #13 head `d11f3bb5e8b42066152a6661c179b5bd64f17d22`.
- PR #13's notebook replay, invariant and promotion repairs are preserved by ancestry, not reimplemented or declared qualified. Its partial-export results retain their original scope.
- Open PR #14 is mining-specific and excluded. No mining implementation, production deployment, publication, migration, billing activation or live provider operation performed.
- No combined Agent 1/Agent 2 candidate is frozen. Commit returned by this repair push identifies the implementation; evidence manifest binds local file contents. A candidate commit cannot contain its own final hash.
- **Launch OPEN / production and publication HOLD.** This is a prerequisite repair PR, not the integrated commercial service.

## Ownership/composition map

Customer-facing hierarchy remains Capacity Fabric; Movement / Storage / Tensor; Enterprise / Cloud / Sovereign; governed Intelligence and Hermitten economics. No internal engine is being turned into a standalone launch SKU or control plane.

| Owner | Preserved authority | Concrete source surface / disposition |
|---|---|---|
| Chronus | iGPU/heterogeneous execution, not tensor mathematics or custody | `chronus.device`, `chronus.virtual_igpu`; no device route run in this pass |
| Kellogg | Tensor mathematics, exact/finite-precision planes and artifacts | `kellogg`; no implementation copied; separate acceptance OPEN |
| Theseus | Durable custody, integrity, persistence, healing and restart recovery | `aethel.theseus.open_theseus`, `aethel.enterprise.custody.compose`, `EnterpriseCustody.backup` |
| Ovid | Representation transforms/materialisation, equivalence, lineage | `aethel.ovid.Ovid`, enterprise versioned Ovid registry; no reassignment to custody |
| PULVINI | Applicable folding/data-computation with reconstruction bounds | `quantum_compute_substrate.pulvini`; not interchangeable with Ovid's exact Zeckendorf transform |
| AL HARAS | Identity derivation, authorization and policy | `al_haras.identity.derive_authenticated_actor`, `al_haras.entitlements.SubscriptionAuthority`; these are library surfaces, not an IdP or mounted backup service |
| SALAMANDER | Bounded authorized supervision/recovery | `salamander.control_plane.ActionRegistry.register` requires a separate named verifier; `bind_authorizer` requires its canonical AL HARAS authorizer |
| TURING | Capability-bounded VQC/quantum computational semantics | Existing public API; no compute/billing change or physical-QPU claim |
| TOE | Common domain-general intelligence | Existing shared backend; unnecessary to first byte-exact storage scenario; other admitted scenarios remain OPEN |
| EUCLID | Orchestration, not duplicate authorities | Existing orchestrator; `CompositionRoot` recovers custody before consumers; orchestration acceptance OPEN |

Only the active storage/policy/recovery surfaces were inspected for this pass. The remaining names/ownership are the owner's mandate, not a fresh whole-engine execution audit.

### Conflicts recorded, not promoted

- `docs/ENTERPRISE_OFFERINGS.md` calls Resilient/Compress/Accel/Compass/Secure/Governance six offerings and uses scoped GA labels. These historical aliases/technical descriptions do not create six additional launch offers or current qualification.
- `docs/ENTERPRISE_CAPABILITY_BRIDGE.md` conflates the Pulvini name with Ovid transformation and describes an older mining-to-Intelligence migration story. PULVINI and Ovid retain distinct current authorities. Mining is not a mandatory launch dependency.
- Existing low-level `open_theseus(durable=True)` / `open_triad(durable=True)` deliberately remain memory-only without a directory. The enterprise convenience boundary now requires the explicit disk binding; low-level compatibility is unchanged.
- Legacy `legacy-ovid-root/v1` remains explicit and separate. No silent root rebinding or dual writes.
- `services/resilience-gateway/DEPRECATED.md` marks that historical surface deprecated; no customer backup API inferred from it.

## First agreed workflow

Agent 2 agreed verified backup-and-restore as the first **Storage** journey. Agreement on a scenario is not agreement on an implemented HTTP contract, and is not permission to ignore remaining launch obligations.

| Workflow stage | Owning entry point | Required configuration | Failure boundary | Acceptance / current evidence |
|---|---|---|---|---|
| Authenticated identity | AL HARAS identity derivation | Verified identity/audience supplied by actual trusted transport/IdP | Request actor header is not proof | Network identity, session expiry/revocation binding OPEN |
| Tenant/capability admission | AL HARAS subscription authority; custody hooks | Issuer/key binding, tenant/actor/capability, validity and limits | Refuse unauthenticated/cross-tenant/expired/unsupported | Source reviewed only; service binding OPEN |
| Transformation | Ovid versioned API | Explicit transform/exactness, max length | Refuse invalid form, unsupported exactness/overflow | Existing complete contract suites required; not rerun |
| Durable commit | `open_enterprise_store(durable_dir=...)` → canonical triad → Theseus | Explicit directory + `theseus-custody/v1` | Refuse missing/conflicting mode before owner creation | 11 isolated function-unit checks; installed acceptance blocked |
| Snapshot | `EnterpriseCustody.backup(new_path)` | New disjoint operator-controlled destination | Existing path/symlink and overlapping root refused; failed copy is unverified | 6 backup-method/filesystem unit checks; installed acceptance blocked |
| Restore/recovery | Existing custody restore; SALAMANDER registry/authorizer/verifier | Validated source, isolated staging, bounded authorized handler and independent postcondition | Existing restore deletes live dirs before recover: do not expose as customer API | Transactional staged cutover/rollback OPEN |
| Verification | Custody read/verify + Ovid equivalence | Expected input digest, representation/lineage, actual store identity | No success on absent/unverified result | New installed fresh-process tests written, not executed successfully |
| Result/evidence | Actual service then Agent 2 UI | Candidate-bound receipt and redacted evidence export | No fabricated endpoint, evidence, savings or chargeable units | HTTP contract and joint journey OPEN |

The repaired smoke tests only commit/read/reattach the same directory in one process; output explicitly says `reattach_same_process`. It is NOT a backup/restore customer journey or fresh-process restart evidence.

## Implemented repairs and compatibility

1. `open_enterprise_store` forwards `durable_dir`, explicitly selects canonical Theseus custody, rejects non-boolean durability, refuses `durable=True` without a directory and refuses contradictory `durable=False` with a directory. Intentional memory-only callers must now pass `durable=False`.
2. `smoke_measured_put` requires the caller's retained directory, reopens through the public factory, checks returned bytes/digest and literal verified disk-bound Theseus facts before emitting measured local integrity evidence. No HMAC authenticity or independent attestation implied by the envelope hash.
3. `EnterpriseCustody.backup` no longer deletes an existing destination. Same-root, ancestor and descendant destinations are refused before copy. New disjoint copies retain the existing lock/copy behavior. A concurrent destination creation makes `copytree` fail rather than overwrite. This is NOT an OS sandbox or a cross-process snapshot-consistency proof.
4. Existing bridge tests migrate their intended durable cases to explicit temporary directories. New normal installed API tests and a reproducible prerequisite runner are supplied. Existing authority and regression gates are not deleted or weakened.

Compatibility: old convenience-factory or smoke calls without `durable_dir` now raise `ValueError`; low-level memory APIs are unchanged. Repeated backups must use a new unique destination. There is no overwrite flag, deletion, automatic migration or data-format change. A failed partial backup remains for diagnosis and must not be published as verified.

## Executed evidence — carefully scoped

| Check | Before | After | Scope |
|---|---|---|---|
| Final durable boundary units | 11 run: 2 assertion failures, 7 errors, 2 passes | 11 passed normal; same 11 passed under `-O` | AST-selected real production functions; explicit triad double; initializer/engines NOT executed |
| Backup filesystem units | 6 run: 4 failures, 1 error, 1 pass | 6 passed normal; same 6 passed under `-O` | Real backup method + real disposable filesystem; actor/event doubles; overlap copy tripwires; NOT installed custody |
| Normal import attempt | N/A | collection error: `aethel.cassini` missing | Actual package initializer preserved; incomplete selected export |
| Isolated installed attempt | N/A | `aethel` not installed | No initializer bypass or source fallback used |
| Candidate runner | N/A | exit 2 BLOCKED: full Git checkout required | No `.git` and no complete installed artifact set |
| Syntax compilation | N/A | passed for changed Python files | Syntax only |

**17 distinct final scoped unit checks, not 34 distinct tests.** The earlier 8-check durable harness/logs are an overlapping development subset, not eight additional checks. `installed-attempt.log` predates restoring the real package initializer: its 8 discovered checks and 3 missing-triad errors are NOT normal installed acceptance. Final attempts retain the real initializer and fail collection/import honestly.

No installed engine workflow, authenticated HTTP service, adversarial multi-tenant service journey, process-restart pass, full regressions, hardware, provider, Docker, CI, economics or production qualification is claimed. Untested does not mean absent or disproven.

## Reproduction

Isolated units, explicitly not launch acceptance:

```bash
python docs/qualification/agent1-launch/run_boundary_unit.py
python -O docs/qualification/agent1-launch/run_boundary_unit.py
python docs/qualification/agent1-launch/run_backup_unit.py
python -O docs/qualification/agent1-launch/run_backup_unit.py
```

For failure-first reproduction, extract the exact original files to separate paths from main `b131edc408a37ff7c03534d694bfcdaf0c827abb`; pass each path as the corresponding harness's sole positional argument. The functions/method are parsed, not reimplemented.

Installed prerequisites (requires full clean checkout at agreed exact candidate plus separately installed matching artifacts/dependencies):

```bash
python docs/qualification/agent1-launch/qualify.py \
  --candidate <full-40-character-candidate-sha> \
  --python /absolute/path/to/qualification-venv/bin/python \
  --evidence /absolute/path/outside-checkout/new-evidence-directory
```

The runner does not install/publish/deploy anything. It rejects a partial/dirty/wrong checkout, imports the real initializer in isolated Python, compares the installed Aethel Python inventory/digests with the candidate, records dependency versions, runs normal installed durable/no-clobber tests and complete named source regression suites, and retains errors/skips. Even a green prerequisite result explicitly leaves launch OPEN. It is not all-engine, HTTP, device, license or release approval.

## Operating/recovery handoff

- Do not bind the UI to the local filesystem APIs or treat the test adapter as a service.
- Provision identity, policy verification and per-tenant custody keys out of band; never use fixture keys or browser-asserted identity. The permissive hook default is not an approved admission configuration.
- Bind the actual canonical directory and finish recover/re-admission before consumers start. Stop consumers before closing custody. Do not infer power-loss or multiprocess writer safety from same-process units.
- Keep legacy and canonical roots separate; no cutover or migration is authorized.
- Use a fresh disjoint backup destination. If the API raises, preserve the destination, logs and source. Never recursively delete/retry automatically. A copied directory is not yet verified backup evidence.
- Existing `restore` is not a transaction: it deletes live directories before copy/recover. Before customer exposure, implement authenticated staged validation, recoverable original snapshot, verified atomic/controlled cutover and crash-tested rollback. Until then retain HOLD; do not call it against customer data from the launch service.
- Interrupted/uncertain writes must retain all artifacts for owner reconciliation; never acknowledge success based on timeout, successful transformation or in-memory replicas. Service request-key/reconciliation/cancellation behavior remains unimplemented/unagreed.
- SALAMANDER must use its existing AL HARAS action authorizer and distinct registered postcondition verifier, not invent another policy authority or trust handler success.
- Chronus physical routes must be separately admitted/probed/measured, with required routes refusing incompatible fallback. No hardware was available or exercised here.
- Hermitten Data economics remain separate from deferred TURING usage billing. No cost baseline/price book, savings or billing activation is supplied by these repairs.

## Precise unblock and next work

Supply an authenticated full checkout or a complete Git/source archive at the combined agreed candidate, together with matching installable internal artifacts and supported dependency lock/install procedure. An archive without Git history can support an archive-identity run but does not satisfy this Git-provenance runner unchanged. Do not send raw credentials in chat.

Then implement/qualify the safe staged restore and trusted identity/session/revocation service binding; agree its actual versioned contract with Agent 2, run genuine browser-to-service journeys, execute every remaining ledger scenario, and retain one combined candidate acceptance record. Current lack of a service contract is an implementation gap, not merely a missing URL. None of those requirements is closed by the units above.
