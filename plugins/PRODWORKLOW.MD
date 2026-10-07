<aside>
🛡️

This is the M3-aligned PYTHIA mining runbook. It preserves the strong execution, lease, verification, stale-work, append-only outcome, recovery-test, and evidence-separation mechanics while correcting the canonical authority model and structured-search doctrine. It is an implementation and evidence gate, not a production declaration.

</aside>

## 1. Canonical authority model

The following ownership is normative for M3. No component may impersonate another authority.

| Authority | Canonical responsibility | Boundary it must not cross |
| --- | --- | --- |
| **EUCLID** | Intelligence orchestration: coordinates intelligence services and supporting reasoning | Must not take PYTHIA's mining authority or compose the final mining plan in its place |
| **PYTHIA** | Mining intelligence and final `SearchPlan` composition; owns the canonical mining-search decision | Must not execute, verify, or claim pool acceptance |
| **TURING** | Independent VQC / quantum-computation authority supporting PYTHIA when selected | Must not become share-validity or pool-acceptance authority |
| **KELLOGG** | Tensor capability supporting encoding, ordering, and computation | Must not own mining intelligence or execution routing |
| **PYTHAGORAS** | Historical lineage and research context | Must not become evidence of future predictability, execution, or acceptance |
| **CHRONUS** | Heterogeneous execution authority; CPU, GPU, Metal, ASIC, remote, and other routes are adapters beneath it | Must not claim host proof or pool acceptance |
| **THESEUS** | Durable custody, records, continuity, integrity, recovery, and provenance | Must not be reduced to a projection layer or replaced by OVID for mining evidence |
| **OVID** | Representation/state transformation: fold, materialise, transform, and metamorphose representations where required | Must not become the canonical mining evidence store or be inserted into every persistence path without a transformation need |
| **SALAMANDER** | Bounded healing and optimisation | Must not govern identity, authorise arbitrary actions, plan nonce search, or determine share validity |
| **AL HARAS** | Security and governance: identities, capabilities, authorisation, policy, deny-by-default boundaries | Must not mutate historical custody or declare a share valid |
| **SHA256d verifier** | Independent candidate proof against the reconstructed header, negotiated target, current work identity, and stale rules | Must not claim pool acceptance |
| **Pool** | External acceptance authority | Its response must not be inferred locally |

The durable flow is therefore:

`EUCLID orchestrates intelligence → PYTHIA composes the final mining plan → AL HARAS authorises → THESEUS preserves custody and continuity → OVID transforms representations when required → SALAMANDER bounds healing/optimisation → CHRONUS executes → SHA256d proves → Pool adjudicates`

The repository contract's durable-record rule is retained only where it agrees with this canonical M3 correction: THESEUS owns durable custody and continuity; OVID owns representation transformation. [[1]](https://github.com/QuantumPhi2/PhiMiner/blob/main/CONTRACTS.md)

## 2. Structured-search doctrine — non-negotiable

PYTHIA mining is a **structured-search system with complete nonce-estate coverage**. The canonical production search identity is **Hendrix**. This is an owner-locked architectural doctrine, not an optional experiment. [[2]](https://github.com/QuantumPhi2/PhiMiner/blob/main/docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md)

### Canonical itinerary

`Real Stratum job → PYTHIA observation / memory / intelligence / supposition → Hendrix structured-search plan → 32-face → 11D representation → H4/600 logical vertices → Turing/Hilbert support where selected → Chronus execution → candidate → independent host SHA256d + negotiated target → verified submission → literal pool outcome → PYTHIA learning → Salamander bounded recovery/optimisation`

The 32-face, 11D, H4/600, and Turing/Hilbert structures support the Hendrix itinerary. They do not replace Hendrix as the search identity.

### Search invariants

1. Structured search is canonical and preserves complete coverage of the authorised nonce estate.
2. Hendrix is the default production traversal.
3. Flat/uniform enumeration may exist for reference, fallback, control, or completeness testing, but cannot replace the canonical structured-search route by default.
4. PYTHIA owns mining intelligence and final `SearchPlan` composition.
5. PYTHIA may compose supposition, tunnelling, annealing, swarming, entanglement, Turing, Kellogg, Chronus, and other authorised support capabilities without transferring mining authority.
6. Structure changes ordering and prioritisation; it must not silently prune the authorised nonce estate.
7. SHA256d plus the negotiated target remains the sole share-validity proof.
8. Pool acceptance is literal external evidence; submission is not acceptance.
9. **O(1) structure-directed candidate resolution** is the canonical search-design objective. It must not be silently replaced by an O(N) flat-search architectural assumption. Measurement and formal proof of that complexity remain separate evidence questions.
10. No agent, contributor, benchmark, refactor, audit, or external convention may demote Hendrix, weaken full coverage, or transfer final SearchPlan authority without explicit written owner approval. [[2]](https://github.com/QuantumPhi2/PhiMiner/blob/main/docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md)

### Resonance evidence boundary

- `R_phi >= 0.5` is the project structural band used by the current resonance analysis/training surfaces.
- The committed 200-real-nonce artifact records **122/200 = 61.0%** in that band.
- The fixed-seed uniform control rate is **61.805%**.
- These figures must not be interchanged. The 61.0% real-corpus rate is not the 61.805% control rate.
- The current result does not establish winner-vs-uniform discrimination at the threshold.
- Neither this result nor later evidence gives an agent authority to redefine PYTHIA as blind search.

Resonance, VQC output, tensor output, historical structure, search position, or model confidence may influence ordering; none can declare a valid share. The canonical doctrine records the same distinction and keeps the structural architecture separate from measured effectiveness. [[2]](https://github.com/QuantumPhi2/PhiMiner/blob/main/docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md)

## 3. Workflow A — Boot, custody, governance, and readiness

**Objective:** start the correct runtime, recover durable custody through THESEUS, establish AL HARAS security boundaries, use OVID only where representation transformation is needed, and expose truthful readiness.

### Correct authority sequence

1. Validate the deployment manifest, schema/version compatibility, service identities, capability policy, signing/encryption-key policy, pool configuration, backend policy, and device policy.
2. Start **THESEUS custody/integrity/recovery**. Verify durable records, continuity, provenance, recovery witnesses, and integrity state. Rebuild only derived views; never invent, overwrite, or silently drop custody evidence.
3. Start **AL HARAS identity/capability/governance**. Load deny-by-default policies, service identities, capabilities, approval bindings, tenant boundaries, and revocation state.
4. Start **OVID transformation services only where required** by a declared fold, materialisation, representation conversion, or metamorphosis contract. A normal custody write does not need to pass through OVID merely because OVID exists.
5. Start **SALAMANDER** and load unrecovered healing/optimisation events. Open critical faults block only the affected route unless policy requires a wider stop.
6. Start Stratum observation and establish a connection/session epoch.
7. Start **EUCLID** orchestration, then **PYTHIA** mining intelligence and final-plan composition.
8. Start selected **TURING** and **KELLOGG** support paths, then **CHRONUS** execution routes, verifier, and submission path.
9. Publish readiness only when every required module is reachable through its canonical interface and its evidence class is truthful.

The repository's deployment documentation distinguishes HTTP health from worker readiness and distinguishes the control service from the separately approved live miner. `/api/health` proves HTTP responsiveness only; `/readyz` is the worker-readiness surface. [[3]](https://github.com/QuantumPhi2/PhiMiner/blob/main/DEPLOYMENT.md)

### Readiness gates

- THESEUS custody, integrity, recovery, continuity, and provenance checks pass.
- AL HARAS identity, capability, deny-by-default, and approval checks pass.
- Any required OVID transformation contract is available and verifiable.
- Salamander has no unrecovered critical route-blocking fault.
- Stratum connection and authorisation succeed.
- PYTHIA can produce a final Hendrix-based plan with complete nonce-estate coverage.
- Selected Turing/Kellogg support is explicit and unavailable routes remain unavailable.
- Chronus backend/device checks pass for the declared route; no silent evidence-class downgrade is allowed.
- A bounded no-submit test can plan, lease, execute, independently verify, preserve custody in THESEUS, and replay.
- Live submission approval is absent by default and, when enabled, is bound to the intended pool identity.

**Failure rule:** no truthful readiness signal, no mining. `/api/health` alone is never sufficient.

## 4. Workflow B — Canonical PYTHIA mining voyage

**Objective:** let PYTHIA own the final mining plan, preserve complete structured-search coverage, authorise through AL HARAS, execute through Chronus, prove independently, submit only with explicit approval, and record the literal pool outcome.

**Canonical path:**

`BOOT → CONNECT → SUBSCRIBE → AUTHORIZE VIA AL HARAS → RECEIVE JOB → PYTHIA PLAN → HENDRIX STRUCTURED SEARCH → LEASE → CHRONUS EXECUTE → HOST SHA256d RECHECK → VERIFIED_PROOF → SUBMIT → POOL OUTCOME → PYTHIA LEARNING → SALAMANDER HEAL/OPTIMISE → CONTINUE`

### Stage contract

1. **Connect:** create a Stratum connection identity and monotonic connection epoch.
2. **Subscribe/authorise:** persist the protocol exchange and accepted capabilities as source evidence; AL HARAS supplies the identity and capability decision.
3. **Receive job:** capture the literal Stratum job, target, difficulty, coinbase components, extranonce data, clean-jobs flag, timestamps, connection identity, and generation.
4. **Build immutable work identity:** include enough fields to distinguish reconnects, generations, extranonce, ntime, version rolling, and reused pool job IDs.
5. **EUCLID orchestration:** coordinate the intelligence surfaces and provide context to PYTHIA; do not compose the final mining SearchPlan or create a second mining authority.
6. **PYTHIA composition:** combine observation, memory, intelligence, supposition, Turing/Kellogg/Chronus support, and the declared 32-face → 11D → H4/600 → Turing/Hilbert itinerary into the final `SearchPlan`. Hendrix remains the default traversal.
7. **AL HARAS authorisation:** validate tenant, actor/service identity, capability, route, schema version, work generation, submission policy, and allowed backend. THESEUS durably records the resulting authorisation and provenance evidence; it does not replace AL HARAS as the authoriser.
8. **Lease:** allocate a bounded, non-overlapping lease for the immutable work identity. Preserve lease transitions as append-only events or enforce a strict transition graph.
9. **Structured search:** Hendrix traverses the authorised nonce estate completely. Supporting intelligence may order and prioritise; it may not prune coverage or declare a winning nonce.
10. **Chronus execution:** record actual route/adapter/backend, device identity, executable/build digest, hashes attempted, measured duration, status, and hardware-executed state. CPU, Metal, GPU, ASIC, remote, and unavailable routes remain distinct.
11. **Independent host recheck:** reconstruct the exact header and recompute SHA256d against the negotiated target, work identity, generation, and stale rules.
12. **Custody and evidence:** THESEUS records durable custody, continuity, provenance, execution evidence, candidate verification, and proof lineage. Use OVID only if a declared representation transformation is required.
13. **Verified proof:** create `verified_proof` only after independent verification succeeds. Record failed and passed candidate checks separately; neither resonance nor a local model output can create proof.
14. **Submit:** submit only a `verified_proof` and only when AL HARAS-approved live-submit authority is bound to the intended pool identity.
15. **Record outcome:** append the literal pool response, reason, attempt, message ID, and observed time. Local computation never upgrades this to pool verification.
16. **Learn and heal:** PYTHIA consumes the outcome for bounded future planning; Salamander may propose bounded healing/optimisation and must measure and record the result. Neither rewrites historical custody or changes share validity.
17. **Continue:** return to lease allocation unless the job is stale, the route is unhealthy, approval is withdrawn, or a readiness gate fails.

### Hard stops

- No EUCLID, TOE, Turing, Kellogg, resonance, or model shortcut to submission.
- No transfer of final SearchPlan authority away from PYTHIA.
- No default replacement of Hendrix with flat search without explicit owner approval.
- No proof without measured execution and independent SHA256d verification.
- No submission without `verified_proof` and AL HARAS-approved live-submit authority.
- No hardware claim without a real device-bound run.
- No hashrate from planned range, logical shard count, configured worker count, resonance, or mathematical topology.
- No pool acceptance inferred from a local digest.

## 5. Workflow C — Clean jobs, stale work, and retries

**Objective:** prevent old work from becoming new evidence while continuing on the current generation.

1. Capture each notification under the correct connection/session epoch.
2. Create a new generation and immutable work identity; never key the evidence chain by pool `job_id` alone.
3. On `clean_jobs`, append invalidation events for pending, leased, and executing work on that connection/channel and older generation only.
4. Stop dispatch to invalidated leases. The executor returns an explicit cancellation/stale result; it must not silently mark work complete.
5. Preserve committed execution, verification, submission, and pool-outcome records. Staleness affects new actions; it does not rewrite custody.
6. Reject late candidates and submissions at the AL HARAS/THESEUS boundary with the relevant generation and connection evidence.
7. For a retryable transport failure, create a new submission attempt with an incremented attempt number. Never overwrite the prior attempt.
8. Escalate a stale-job spike to Salamander and suspend the affected route when policy thresholds are exceeded.

**Acceptance evidence:** old work is invalidated only within the intended channel, no overlapping lease appears under the same work identity, and the miner continues on the new generation.

## 6. Workflow D — Fault handling, restart, and recovery

**Objective:** survive disconnects, device loss, process restarts, custody faults, and representation-transform faults without fabricating or losing evidence.

### Fault ownership

- **THESEUS faults:** custody interruption, continuity break, provenance mismatch, recovery failure, integrity/witness failure, or durable-record inconsistency.
- **OVID faults:** transformation failure, fold/materialisation mismatch, representation reconstruction failure, metamorphosis failure, or transformation-provenance mismatch.
- **AL HARAS faults:** identity failure, capability denial, revoked approval, policy mismatch, or tenant-boundary violation.
- **CHRONUS faults:** device loss, backend failure, thermal condition, route mismatch, or measured execution failure.
- **SALAMANDER:** bounded diagnosis, healing/optimisation proposal, action, measurement, retain/rollback decision, and recovery evidence.

### Sequence

1. Detect the fault and append a traceable event tied to the relevant custody, transformation, identity, connection, job, plan, lease, device, submission, or storage object.
2. Stop only the unsafe capability. Never silently fall back from a missing physical backend to a different evidence class.
3. For a THESEUS custody fault, freeze the affected writes, reconcile continuity and recovery witnesses, and restore from the latest verified custody point.
4. For an OVID transformation fault, quarantine the affected representation, preserve the source custody, record the transformation contract/version, and retry or roll back the transformation without changing the source evidence.
5. For an AL HARAS denial, retain the deny reason, invalidate the affected approval/session when required, and do not resume until policy permits it.
6. Restart the affected component or the whole stack.
7. Reconcile connection epochs, job generations, open leases, custody records, checkpoints, transformation provenance, and derived projections.
8. Restore the latest valid PYTHIA/EUCLID context and session state. Reissue only leases valid for the current generation and policy.
9. Record recovery as a new event or recovery ledger entry; do not mutate the original fault.
10. Prove continued operation with a fresh job, bounded no-submit execution, independent host verification, and replay.

**Recovery invariant:** every committed THESEUS ID appears exactly once; every incomplete action is explicitly recoverable or abandoned; every OVID transformation is reproducible or explicitly failed; no projection claims evidence that THESEUS did not commit.

## 7. Workflow E — Evidence, audit, and export

**Objective:** produce a replayable package while keeping the canonical M3 mining gate separate from optional sovereign/customer deployment extensions.

1. Select the lifecycle by tenant where applicable, connection epoch, job generation, work identity, plan, lease, execution, validation, submission, outcome, transformation, custody, and recovery IDs.
2. Validate the execution package against `chronus.execution-evidence.v2`: `schema`, `workload`, `planner`, `substrate`, `execution`, `validation`, and `provenance` are mandatory. [[4]](https://github.com/QuantumPhi2/PhiMiner/blob/main/schema/evidence.schema.json)
3. Include target/header reconstruction inputs, adapter/backend, device identity, executable/build digest, verifier identity, timestamps, AL HARAS policy/approval decision, and literal pool response where applicable.
4. Preserve the durable evidence and lineage in THESEUS. Include OVID transformation receipts only where a transformation occurred.
5. Verify the package offline when the chosen deployment profile requires it.
6. Record export verification as a new immutable custody event.

### Optional sovereign/customer extension

Customer-managed keys, air-gapped verification, tenant isolation, retention/zeroization, bilingual audit outputs, dual-control privileged operations, and sovereign audit-pack export are deployment extensions. They become mandatory only for a deployment profile that selects them; they are not prerequisites for the canonical M3 miner gate.

## 8. Workflow F — M3 production-readiness gate

The M3 gate is about **PYTHIA executing its canonical voyage**. It is not a promotion gate into UnifiedEnterprise or another product architecture.

<aside>
ℹ️

`CI_UNAVAILABLE` is neither PASS nor FAIL. For this release, retained clean-environment M3 execution against the frozen SHA is the authoritative executable gate. Remote CI remains an outstanding evidence class until runners and minutes are restored.

</aside>

### Required M3 evidence

- [ ]  Current commit, doctrine version, machine policy, and manifest SHA are pinned.
- [ ]  EUCLID orchestration, PYTHIA final-plan composition, AL HARAS authorisation, THESEUS custody, selected Turing/Kellogg support, Chronus execution, verifier, submission, pool outcome, and Salamander healing paths are present in the canonical module manifest.
- [ ]  PYTHIA retains final SearchPlan authority and Hendrix remains the default production traversal.
- [ ]  Complete nonce-estate coverage is demonstrated for the authorised lease; no silent pruning occurs.
- [ ]  The canonical structured-search itinerary is 32-face → 11D → H4/600; TURING/Hilbert is invoked when PYTHIA's SearchPlan selects that support path.
- [ ]  O(1) structure-directed candidate resolution remains the design objective and is not silently replaced by an O(N) flat-search architecture. Any complexity claim is separately marked measured or formally proved only when evidence exists.
- [ ]  Startup, `/readyz`, reconnect, restart, custody recovery, transformation recovery, and continued mining pass.
- [ ]  Software execution evidence is retained separately from hardware execution evidence.
- [ ]  Every submitted candidate has independent host SHA256d and target verification.
- [ ]  `verified_proof` is required before submission; failed candidate checks cannot submit.
- [ ]  Live Stratum connection and job reception are demonstrated.
- [ ]  The verified submission path is executable and fail-closed.
- [ ]  If a valid candidate occurs and is submitted, the literal pool response is recorded as a separate outcome.
- [ ]  If no valid candidate occurs during the bounded run, `POOL_OUTCOME` / `POOL_ACCEPTED` remain `UNAVAILABLE`, not `FAIL`.
- [ ]  An accepted share is not a prerequisite for declaring the software/device path ready.
- [ ]  Stale-job, duplicate-lease, out-of-range nonce, tampered proof, missing device, revoked approval, wrong-tenant, and transformation-mismatch negative tests pass.
- [ ]  Crash, continuity, recovery, replay, tamper, soak, device-bound, and bounded live-pool tests pass.
- [ ]  Hashrate uses actual hashes attempted over trusted elapsed time, not lease size or logical topology.
- [ ]  The resonance evidence is labelled correctly: `R_phi >= 0.5`, 122/200 = 61.0% real-corpus band rate, and 61.805% fixed-seed uniform control rate.
- [ ]  The owner makes the external production declaration from the evidence ledger; the codebase must not self-certify.

If any M3 gate is open, label the capability **not yet production-ready**. Do not use missing evidence as permission to weaken the canonical architecture.

## 9. Full ownership map

| Boundary | Canonical owner | May create/decide | Must never claim |
| --- | --- | --- | --- |
| Intelligence orchestration | EUCLID | coordinate intelligence services and supporting reasoning | PYTHIA's final mining authority |
| Mining intelligence and plan | PYTHIA | final `SearchPlan`, structured-search decision, mining learning | execution, proof, or pool acceptance |
| Quantum/VQC support | TURING | selected VQC/quantum computation and support evidence | share validity or pool acceptance |
| Tensor support | KELLOGG | tensor encoding/computation support | mining intelligence or execution routing |
| Historical lineage | PYTHAGORAS | historical context and research lineage | future predictability, execution, or acceptance |
| Heterogeneous execution | CHRONUS | route/device/backend execution evidence | host proof or pool acceptance |
| Durable custody | THESEUS | records, continuity, integrity, recovery, provenance | representation transformation authority |
| Representation transformation | OVID | fold, materialise, transform, metamorphose, and transformation receipts | canonical mining evidence custody |
| Healing/optimisation | SALAMANDER | bounded diagnosis, action, measurement, retain/rollback | security governance or share validity |
| Security/governance | AL HARAS | identity, capability, authorisation, policy, deny-by-default | historical custody mutation or share validity |
| Candidate proof | SHA256d verifier | independent header/target verification and `verified_proof` | pool acceptance |
| External adjudication | Pool | literal response to a submission | local software or hardware evidence |

## 10. Corrected implementation backlog

- [ ]  Freeze the M3 authority map and reject superseded THESEUS/OVID wording.
- [ ]  Pin the owner-locked structured-search doctrine and machine policy.
- [ ]  Keep PYTHIA as the sole final mining SearchPlan authority; keep EUCLID orchestration above it.
- [ ]  Keep Hendrix as the canonical default traversal and preserve complete nonce-estate coverage.
- [ ]  Preserve the 32-face → 11D → H4/600 → Turing/Hilbert itinerary and explicit support composition.
- [ ]  Record `R_phi >= 0.5`, 122/200 = 61.0%, and 61.805% control as separate evidence figures.
- [ ]  Move identity, capability, authorisation, policy, and deny-by-default enforcement to AL HARAS.
- [ ]  Implement THESEUS durable custody, records, continuity, integrity, recovery, and provenance.
- [ ]  Keep OVID limited to declared representation/state transformations with transformation provenance and failure handling.
- [ ]  Keep Salamander limited to bounded healing and optimisation.
- [ ]  Freeze complete `WorkIdentity`, connection epoch, job generation, lease, candidate, proof, submission, outcome, custody, and transformation IDs.
- [ ]  Retain non-overlapping leases, actual device/work measurements, independent SHA256d verification, `verified_proof` before submission, and literal pool outcomes.
- [ ]  Implement custody recovery tests, OVID transformation-failure tests, AL HARAS denial tests, Chronus route/device tests, and Salamander bounded-action tests.
- [ ]  Add negative, crash, replay, tamper, soak, device-bound, completeness, and bounded live-pool tests.
- [ ]  Produce the signed M3 release evidence report with measured limits, open gaps, and owner declaration.

> PYTHIA plans. EUCLID orchestrates intelligence. TURING and KELLOGG support. CHRONUS executes. SHA256d proves. The pool adjudicates. AL HARAS governs and authorizes. THESEUS preserves custody and continuity. OVID transforms representations. SALAMANDER heals and optimises. None may impersonate another authority.
> 

## 11. Database and file-taxonomy completion audit

**Audit verdict: PARTIAL — not yet complete for the M3 end-to-end storage gate.**

### What is already present

- `hyba_db` provides a tenant-scoped six-layer ontology store with physical blocks, folds, tensors, graph nodes/edges, proofs/attestations, contracts, ontology, computations, quotas, foreign keys, WAL mode, digest checks, HMAC/attestation, and `verify_database()`. It also has projection methods for pool connections, jobs, shares, targets, and certificate relationships. [[5]](https://github.com/QuantumPhi2/PhiMiner/blob/main/docs/HYBA_ONTOLOGY_STORE.md)[[6]](https://github.com/QuantumPhi2/PhiMiner/blob/main/hyba_db/store.py)
- THESEUS custody has a producer registry, schema/dependency admission, opaque payload custody, content digests, lineage, checkpoints, recovery, replay, retention, and pending semantic revalidation. [[7]](https://github.com/QuantumPhi2/PhiMiner/blob/main/docs/THESEUS_INTERFACE_CONTRACT.md)
- OVID has declared, versioned transformation contracts, exactness states, transform lineage, equivalence verification, and a handoff of transform provenance into THESEUS. [[8]](https://github.com/QuantumPhi2/PhiMiner/blob/main/docs/OVID_INTERFACE_CONTRACT.md)
- `ProductionSystemRelations` and `ProductionOrganism` bind PYTHIA, TOE, Kellogg, TURING, Salamander, AL HARAS, EUCLID, and Chronus-related handoffs to one shared data fabric, with tests for real writes, verification, and restart continuity. [[9]](https://github.com/QuantumPhi2/PhiMiner/blob/main/aethel/enterprise/system_relations.py)[[10]](https://github.com/QuantumPhi2/PhiMiner/blob/main/tests/test_shared_system_relations_production.py)
- A storage-archaeology script and report already classify component storage surfaces into categories such as core substrate, control-plane database, durable evidence store, memory, compatibility, legacy, experimental, and disconnected. [[11]](https://github.com/QuantumPhi2/PhiMiner/blob/main/scripts/probe_storage_archaeology.py)[[12]](https://github.com/QuantumPhi2/PhiMiner/blob/main/reports/hyba_storage_archaeology.json)

### Why the storage gate is not complete

1. **The taxonomy is currently a generated report, not an authoritative file registry.** The archaeology report lists components and paths, but it does not create a durable file object, file version, storage URI, lineage binding, or database foreign key for every runtime artifact.
2. **There are still multiple persistence surfaces.** The repository explicitly describes `hyba_db` as additive and not a replacement for Aethel snapshots, Chronus `PrimeDB`, or mining persistence. SQLite, local journals, file snapshots, compatibility stores, reports, manifests, and caches therefore remain separate surfaces unless the common file registry is added. [[5]](https://github.com/QuantumPhi2/PhiMiner/blob/main/docs/HYBA_ONTOLOGY_STORE.md)[[13]](https://github.com/QuantumPhi2/PhiMiner/blob/main/docs/hyba/DATA_SUBSTRATE.md)
3. **Operational records are not the same as file records.** THESEUS stores opaque payload bytes plus producer, kind, digest, lineage, dependencies, and metadata; it does not yet provide a first-class file taxonomy with path, MIME, artifact class, storage URI, revision, retention, and file-to-domain-object bindings. [[14]](https://github.com/QuantumPhi2/PhiMiner/blob/main/aethel/enterprise/records.py)
4. **The mining projection is not yet a complete relational lifecycle.** `hyba_db` has pool/job/share graph projections, but the M3 run requires explicit durable links for connection/session, job generation, work identity, plan, lease, execution, candidate verification, `verified_proof`, submission attempt, literal pool outcome, learning, recovery, and any attached artifacts. [[6]](https://github.com/QuantumPhi2/PhiMiner/blob/main/hyba_db/store.py)
5. **Shared-system binding is not file completeness.** The current shared-fabric tests prove that subsystem records enter one custody graph and survive restart; they do not prove that every generated report, manifest, checkpoint, journal, proof, cache snapshot, or transformation artifact is registered and reconciled.

### Canonical file taxonomy

Use one taxonomy for runtime files and generated artifacts. Do not copy the entire source tree into the runtime database. Source code remains governed by Git commit and path; the database stores a source reference (`repository`, `commit`, `path`, `sha256`) unless an audit profile explicitly requires the payload.

| File class | Examples | Authority | Required database link |
| --- | --- | --- | --- |
| `source_reference` | Python, Rust, TypeScript, SQL, schemas | Git/release manifest | repository, commit, path, digest, release/capability |
| `configuration` | `.env` references, TOML/YAML/JSON config | AL HARAS / deployment | profile, tenant, secret-reference, version |
| `contract` | authority, transform, evidence, API contracts | owning subsystem | contract name/version, invariant, producer |
| `manifest` | module, deployment, capability, search, schema manifests | owner / release process | manifest digest, commit, scope, status |
| `stratum_source` | connection exchange, job, target, generation | Stratum/PYTHIA | connection epoch, job generation, work identity |
| `plan` | PYTHIA `SearchPlan`, Hendrix itinerary, advisory frames | PYTHIA | plan ID, job, lease, owner, evidence state |
| `lease` | nonce lease and transition events | PYTHIA/Chronus coordinator | work identity, interval, generation, transition chain |
| `execution` | device dispatch, hashes attempted, timings, backend receipts | CHRONUS | lease, device, adapter, build digest, evidence state |
| `candidate_verification` | pass/fail SHA256d checks | SHA256d verifier | execution, nonce, reconstructed-header digest, target |
| `verified_proof` | independently verified proof artifact | SHA256d verifier | candidate verification, verifier build, custody record |
| `submission` | Stratum submit request/attempt | submission boundary | verified proof, pool connection, attempt number |
| `pool_outcome` | accepted/rejected/stale/timeout response | Pool | submission, message ID, literal response |
| `transform` | OVID fold/materialise/reconstruct output | OVID | transform contract/version, input/output digest, equivalence verdict |
| `custody` | THESEUS envelope, journal, checkpoint, recovery receipt | THESEUS | record ID, tenant, lineage, integrity/MAC, checkpoint |
| `governance` | AL HARAS decision, Salamander healing/optimisation | AL HARAS/SALAMANDER | actor, capability, policy, action, result, recovery link |
| `audit` | signed audit pack, replay report, gate result | THESEUS/release owner | evidence scope, signature, manifest, verification status |
| `cache` | local memory snapshot, derived index, projection | producing subsystem | source record IDs, cache version, rebuild recipe; never authoritative |
| `legacy` / `experimental` | frozen or research-only files | explicit owner | status, reason, exclusion from production path |

### Required file object and link model

Implement a first-class `file_object` / `file_version` record in THESEUS custody or its canonical database projection with, at minimum:

- `file_id`, `tenant_id`, `logical_name`, `logical_path`, `file_class`, `artifact_kind`;
- `owner_system`, `producer`, `producer_version`, `schema_version`, `evidence_state`;
- `mime_type`, `extension`, `byte_length`, `sha256`, `content_encoding`;
- `storage_backend`, `storage_uri`, `storage_generation`, `created_at`, `retention_policy`;
- `parent_file_id`, `lineage_ids`, `transform_id`, `transform_version`, `equivalence_verdict`;
- `source_commit` / `release_id` for source references;
- `status` (`ACTIVE`, `QUARANTINED`, `SUPERSEDED`, `RETIRED`, `MISSING`);
- immutable `file_event` history for ingest, verify, transform, link, publish, quarantine, restore, and retire.

Add typed link records from files to domain objects. Every operational file must link to at least one of: tenant, connection/session, job generation, work identity, SearchPlan, lease, execution, candidate verification, verified proof, submission, pool outcome, transform, custody record, governance event, or release gate. A file with no link is an orphan and must fail the integrity gate.

### Physical storage taxonomy

Use a content-addressed, tenant-scoped path that is derived from the database record, for example:

`<root>/<tenant>/<file_class>/<artifact_kind>/<evidence_state>/<sha256[0:2]>/<sha256>.<extension>`

The path is a location, not an identity. The database record and digest remain authoritative. A write must:

1. create a temporary object and compute the digest;
2. validate taxonomy, producer, tenant, and links through AL HARAS/THESEUS;
3. atomically commit the file manifest and custody record;
4. fsync/rename the object into its content-addressed location;
5. verify readback and record the file event;
6. quarantine or remove uncommitted temporary objects during recovery.

Do not treat local caches, reports, or raw paths as authoritative until this manifest-and-custody transaction succeeds.

### End-to-end module file obligations

- **EUCLID:** orchestration traces and handoff records.
- **PYTHIA:** final SearchPlan, memory checkpoints, learning/outcome records, and mining provenance.
- **TURING:** program, result, witness, pipeline report, and VQC evidence.
- **KELLOGG:** tensor state, encoding/attestation, and tensor provenance.
- **CHRONUS:** execution receipts, route/device evidence, hashes attempted, timing, and build digest.
- **THESEUS:** custody envelopes, journal, checkpoints, recovery, continuity, provenance, and file manifests.
- **OVID:** transformation inputs/outputs, contract/version, exactness, lineage, and equivalence verdicts.
- **AL HARAS:** identity, capability, authorization/denial, policy, and security audit evidence.
- **SALAMANDER:** bounded healing/optimisation proposal, action, measurement, retain/rollback, and recovery evidence.
- **Stratum/verifier/pool:** source jobs, candidates, verified proofs, submissions, and literal outcomes.

Each adapter must write through the shared data port or a canonical file-registry API. Direct writes to unmanaged `data/`, `artifacts/`, `reports/`, local journals, or cache directories are either registered as `cache`/`legacy` or rejected by the M3 gate.

### Storage/database completion gates

- [ ]  Taxonomy schema and allowed classes are versioned and owner-approved.
- [ ]  File manifest and file-version records exist in the canonical custody/database path.
- [ ]  Every runtime artifact root is inventoried; no unmanaged production path remains.
- [ ]  Every file record has a digest, storage URI, owner, evidence state, version, and domain-object link.
- [ ]  Every active file on disk has exactly one active manifest record; every active manifest has readable bytes.
- [ ]  Every generated file from EUCLID, PYTHIA, TURING, KELLOGG, CHRONUS, THESEUS, OVID, AL HARAS, SALAMANDER, Stratum, verifier, and pool boundaries is registered or explicitly classified as non-authoritative cache/legacy.
- [ ]  The database verifies tenant isolation, foreign keys, custody integrity, file hashes, transform lineage, and graph connectivity in one gate.
- [ ]  File write + custody record commit is atomic and restart-safe; orphan files and orphan records are detected and quarantined.
- [ ]  Rebuild tests prove that derived indexes/projections can be recreated from THESEUS custody and registered files.
- [ ]  The full mining lifecycle links job → plan → lease → execution → candidate verification → verified proof → submission → pool outcome → learning/recovery, with attached file manifests at each evidence boundary.
- [ ]  A clean restart, corruption, missing-file, duplicate-file, stale-generation, and transformation-mismatch test passes.

**Completion verdict:** the repository has strong custody, transformation, ontology, attestation, and shared-system foundations, but it does not yet prove a complete file-taxonomy registry linked to every database entity and every module artifact. M3 storage should remain **GATED** until the file manifest/link/reconciliation gates above are implemented and executed.