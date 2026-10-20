# Supervisor Gate A — Missing-signature and contract audit

**Decision: HOLD. Gate A export completed; no production gate has been closed.**

Date: 2026-10-20. Scope: nine selected Notion records, freshly loaded through authenticated Notion MCP. This is a document completeness audit, not a source-level ABI diff, implementation re-review, runtime qualification, license reconciliation or legal sign-off. MISSING_IN_RECORD means the exported record does not establish the item; it does not mean implementation is absent. Required/target behaviour must not be reported as observed runtime behaviour.

## Deliverables

- `NINE_NOTION_RECORDS.md`: all nine exact loaded bodies, source references and body hashes.
- `notion-records/*.md`: each exact body separately; `*.json`: complete loaded page result including title, source URL and edit timestamp.
- `EXPORT_MANIFEST.json`: source metadata, body hashes and provenance scope. No credentials are included.
- `API_GAPS.json`: per-product named surfaces, unresolved fields, acceptance requirements and pending owner sign-off.
- `SHA256SUMS`: hashes for the pack files, excluding itself.

The export is a snapshot, not a live sync. Compare body SHA-256 to detect subsequent Notion changes. Exact body preservation includes Notion XML-style mentions and code tags.

## Gate rule

Fresh same-candidate execution + retained artifact + accountable owner sign-off are required. Author-reported passes, static inspection and documentation locks do not qualify a release. Paid CI is deferred; mandatory local/self-hosted checks remain. No chat approval substitutes for required lane sign-off or bypasses repository protections.

## Common missing executable contract fields

For every product, establish these from the real installed version at a frozen full source SHA:

- [ ] Distribution, import namespace, component owner, version, source commit and exported symbol inventory.
- [ ] Exact positional/keyword parameters, types, defaults, nullability, validation and resource limits.
- [ ] Return/result and persisted/wire schema, versioning, evidence fields and canonical serialization fixtures.
- [ ] Typed errors/refusals, unavailable/unsupported states, and actual transport status mapping if a network transport exists.
- [ ] Authentication/authorisation, tenant/object scope, policy hooks and secret/key lifecycle for applicable boundaries.
- [ ] Concurrency, idempotency/replay, timeout/cancellation, partial completion and durable acknowledgement semantics where applicable.
- [ ] Declared exactness/fallback policy, actual backend/provider and no silent device substitution.
- [ ] Source-to-installed API parity and independent positive/negative acceptance receipts.

If a field is not applicable, the owner must document why; do not fabricate a REST API for a library.

## Per-product audit


### PULVINI — Folding Product, Contract & API Lock

Source: <mention url="https://app.notion.com/p/339540722ac047da84098000c32d88d0">PULVINI — Folding Product, Contract & API Lock</mention>

- **Present in record:** Fold/unfold/validate operation families; zphi_exact, hyperbolic and holograph modes are referenced.
- **Unresolved:** Canonical module/export and exact signatures; mode-specific input/output and residual/kernel encoding; reconstruction-error semantics and resource limits; package/license boundary.
- **Required acceptance, not executed here:** Round-trip plus corrupted/missing metadata refusal, counting residuals and all representation overhead.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

### TURING VQC — Product, Contract & API Lock

Source: <mention url="https://app.notion.com/p/e183affb2dd64fc9ae5701c694f0c220">TURING VQC — Product, Contract & API Lock</mention>

- **Present in record:** Backend/capability registry, sampling/marginals, certificates and turing-vqc are named.
- **Unresolved:** Installed backend/registry signatures and serialisation schemas; readout order versus sorting/deduplication; actual tableau-storage metric; QPU refusal and real tensor dependency bindings.
- **Required acceptance, not executed here:** Independent-reference phase/measurement/continuation parity, seeded sampling and unsupported-domain refusal; entropy and QEC separately.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

### Kellogg — Product, Contract & API Lock

Source: <mention url="https://app.notion.com/p/ccfcdd6511be4c93bb516102bf90a495">Kellogg — Product, Contract & API Lock</mention>

- **Present in record:** TT/MPS/MPO mathematics and safe .pv artifact responsibilities are defined.
- **Unresolved:** Canonical tensor exports/signatures, dtype/shape/rank/error-budget schema, artifact-version/authentication schema, exact exception and limit mapping.
- **Required acceptance, not executed here:** Complex tensor reconstruction and reference contractions; malformed/nonfinite/invalid-HMAC and corrupted artifact refusal.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

### Chronus — Hardware Product, Contract & API Lock

Source: <mention url="https://app.notion.com/p/8774f4fa7c344656b1f0d0532e502e71">Chronus — Hardware Product, Contract & API Lock</mention>

- **Present in record:** Hardware capability/execution semantics, actual-device evidence and explicit fallback are specified.
- **Unresolved:** Distinct Chronos/Chronus distribution-to-API mapping; execution/capability signatures; device fingerprint/handle lifetime and tenant binding; fallback/error schema; actual device receipts.
- **Required acceptance, not executed here:** Required-device refusal and actual device binding, tenant isolation and reference-output/timing evidence.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

### EUCLID — Product, Contract & API Lock

Source: <mention url="https://app.notion.com/p/f1ea1e2825114d54986de07910b99dca">EUCLID — Product, Contract & API Lock</mention>

- **Present in record:** EuclidCreativeKernel.run/refine/adapt_world, EuclidCreatorAPI and ProviderManifest are named.
- **Unresolved:** Exact arguments/defaults/type signatures and result/manifest serialisation; full exception schema; declared transport scope; persistent-store/provider binding and concurrency version fields.
- **Required acceptance, not executed here:** Rights/coherence refusal, deterministic semantic identities, world-version conflicts, honest rendered status and provenance tamper detection.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

### SALAMANDER — Enterprise Product, Contract & API Lock

Source: <mention url="https://app.notion.com/p/97f11d176eb149659add24c32d58b07e">SALAMANDER — Enterprise Product, Contract & API Lock</mention>

- **Present in record:** Typed health/recovery operations and telemetry reporter examples are documented.
- **Unresolved:** Canonical control-plane callable exports/payload schemas; adapter-versus-pseudocode distinction; action registry and approval types; telemetry freshness/authenticity, unknown-state and rollback schema.
- **Required acceptance, not executed here:** Unknown/stale state, quarantine, denied action, bounded recovery, human-gated compaction and restart truth reacquisition.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

### Theseus — Product, Contract & API Lock

Source: <mention url="https://app.notion.com/p/14ef71cd36624fd8bc1e1c44e820b552">Theseus — Product, Contract & API Lock</mention>

- **Present in record:** Custody/write/read/replicate/heal/recover obligations and historical namespaces are documented.
- **Unresolved:** Authoritative root/component/version and catalog import mapping; commit/acknowledgement/consistency schema; tenant and object keys; transaction/journal concurrency; read-only/fsync/repair semantics; key identity/rotation API.
- **Required acceptance, not executed here:** Tenant/traversal/crash/journal-tail/concurrent-writer/backup-during-write faults, restore and authenticated custody continuity.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

### Ovid — Product, Contract & API Lock

Source: <mention url="https://app.notion.com/p/b2ea679b44554cb2b837575ef1a205a4">Ovid — Product, Contract & API Lock</mention>

- **Present in record:** Versioned transform/materialise and migration handoff semantics are documented.
- **Unresolved:** Canonical facade signatures, actual hyba_db/ovid/aethel mapping and authority; working-form/residual lineage schema; sealed handoff/commit token and error semantics; ontology-attestation admission.
- **Required acceptance, not executed here:** Version mismatch, corrupted/missing reconstruction state, interrupted handoff and ontology-policy refusal with identity-preserving reconstruction.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

### SALAMANDER Mining — Workload Contract & API Lock

Source: <mention url="https://app.notion.com/p/06fe66554a704882a36026442fbffdc6">SALAMANDER Mining — Workload Contract & API Lock</mention>

- **Present in record:** ProductionMiningIntegration and IntelligentPoolCoordinator.apply_salamander_mode are named.
- **Unresolved:** Current integration module/signatures; exact mode enum and payload/result/error schemas; auth/action replay policy; binding to canonical SearchPlan/proof/pool owners; heartbeat and recovery evidence schema.
- **Required acceptance, not executed here:** Disconnected rehearsal, denied/replayed actions and honest unavailable states; separately authorised pool-kill recovery and heartbeat measurement; live acceptance attributed to pool.
- **Lane status:** contract qualification incomplete; source ABI diff NOT_RUN; owner/sign-off UNASSIGNED/PENDING.

## Supervisor findings requiring source revalidation

The incoming review reports R01–R09 from 2026-10-04. The original numbered findings, source SHA and retest artifacts were not supplied in this Gate A pack. Do not invent the one-to-one R01–R09 numbering or assert those historical defects remain reproduced on current main. Their closure remains **unverified**, which is sufficient to retain the release HOLD.

Carry forward these reported subjects as pending source/fault-injection checks: ownership inversion; tenant collision/traversal; sealed commit boundary; journal atomic repair/tail; cross-process transaction/writer races; directory fsync and read-only no-heal; tenant-scoped Chronus handles and physical device/residency binding; virtual_iGPU overwrite; ontology-attestation bypass. Obtain the original findings and map each exact ID to source, fix, test and artifact.

The documentation target is PULVINI folding / Ovid transform-materialise / Theseus custody. Older code-lineage notes and current catalog imports differ. **Do not select a destructive rebuild root, replay direction or migration from product labels.** Identify the authoritative component/version/commit boundary and prove restore on that actual composition first.

The incoming 100/100 Arena, 78 integration, 4-hour stable mining, pool-recovery and CPU timing statements remain supervisor-supplied historical reports here. This pack does not independently corroborate them or attach fresh logs for them.

## Runtime handoff — pending, not fabricated artifacts

Gate B requires actual `pytest_arena.log`, `regress.log`, `ineffable.log`, `gate.log`, claims-gate output, Chronus execution report and fault-injection logs, with frozen source identity, commands, exit codes and manifest hashes. Discover real pytest nodes from the checkout rather than guessing filenames. Preserve supplied command equivalence, disable pytest cache (`-p no:cacheprovider`) and use distinct basetemps outside the source tree; verify manifests before/after execution, not merely a clean working directory claim.

Incoming mining targets are pool-kill recovery ≤30s and heartbeat p95 <2s. The p95 artifact must define heartbeat age versus inter-arrival metric, clock, sample population/window, count, quantile method, workload and failure-injection conditions. Capture actual recovery start/end events. The stated diff-to-share time examples are not universal: confirm effective independent hash rate, pool difficulty convention, observation window and expected-share model before interpreting a zero-share interval. No share result or timing proof is generated by this export.

License/legal work requires an actual resolved dependency inventory with transitive versions and licenses, source/distribution rights, approved policy/exceptions and the applicable signed/approved customer instruments. No such inventory or approval is created by exporting these charters.

## Owner sign-off matrix

No human lane holder is assigned by inference. Every lane below requires a named accountable owner, candidate SHA/version, review decision and artifact references; any unresolved blocking lane retains HOLD.

| Lane | Holder | Decision | Artifact |
| --- | --- | --- | --- |
| EUCLID | UNASSIGNED | PENDING | NOT ATTACHED |
| Chronus | UNASSIGNED | PENDING | NOT ATTACHED |
| Ovid | UNASSIGNED | PENDING | NOT ATTACHED |
| Theseus | UNASSIGNED | PENDING | NOT ATTACHED |
| PULVINI | UNASSIGNED | PENDING | NOT ATTACHED |
| TURING VQC | UNASSIGNED | PENDING | NOT ATTACHED |
| Kellogg | UNASSIGNED | PENDING | NOT ATTACHED |
| SALAMANDER Enterprise | UNASSIGNED | PENDING | NOT ATTACHED |
| SALAMANDER Mining | UNASSIGNED | PENDING | NOT ATTACHED |
| Security / AL HARAS | UNASSIGNED | PENDING | NOT ATTACHED |
| Legal / License | UNASSIGNED | PENDING | NOT ATTACHED |

## Explicit scope exclusions

No production tag, merge, deploy, publication or paid CI execution. No new arena/v17, hardware, live-pool, ledger, fault-injection, restore, benchmark or license scan pass is claimed. Previously executed scoped 23-method admission regressions are separate evidence and do not substitute for these gates. This pack contains no synthetic PASS receipts, fabricated pytest logs or signed agreements.
