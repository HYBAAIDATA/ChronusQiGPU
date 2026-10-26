# Internal mining workflow: contracts, authority and executable evidence

**Internal treasury engineering documentation — not a public mining product brief.**

## 1. Scope, source and status rules

This document follows the owner's mining notes and the canonical authority model,
not a replacement architecture. It describes the production software path from
connection to literal pool verdict, plus the learning and recovery feedback loops.

Reviewed source base: `b131edc408a37ff7c03534d694bfcdaf0c827abb`.
The qualification workspace includes the proposed PR #14 planner/transport changes
and PR #17 canonical-execution postcondition. Neither proposal is treated as merged.
This document and new support-invocation tests extend the PR #17 branch.

Evidence terms:

- **Implemented:** concrete source seam exists; not a claim that it executed.
- **Selected-test pass:** the identified software test ran successfully in the
  retained qualification. It confirms its assertions, not every use of that module.
- **Reachable:** a public symbol/module resolved; not proof it was invoked in mining.
- **Invoked in support test:** a specific real algorithm was called via PYTHIA;
  not proof every live SearchPlan selects it or that it accelerates proof of work.
- **Loopback verdict:** a local pool answered; distinguish scripted responses from
  an independently verifying loopback pool, and both from an external live pool.
- **Unverified:** no fresh supporting evidence; never silently promote to PASS.

No physical GPU/iGPU/QPU is a prerequisite for the native mathematical software
path. Logical topology, configured workers and native arithmetic are not evidence
of physical accelerator execution, fleet throughput or quantum speedup.

## 2. One pipeline, distinct owners

```text
operator identity / endpoint / tenant-custody configuration
  -> pool connection -> subscribe -> authorize
  -> authoritative job / negotiated target / extranonce / session-generation
  -> generation-scoped nonce lease + upstream agentic proposal
  -> PYTHIA observe / recall / Intelligence / suppose / compose / final plan
       Turing quantum arsenal + Kellogg tensor support + backend census
  -> exact 32-face / 11D / H4-600 / Hilbert composition
  -> sealed resident Hendrix itinerary, complete authorised lease
  -> Chronus execution -> actual SHA256d work
  -> canonical planned/requested/executed postcondition
  -> independent host recheck + exact header/target + freshness gates
  -> guarded single-writer mining.submit
  -> literal accepted / rejected / unresolved pool outcome
  -> durable session/evidence records -> PYTHIA learning
  -> Salamander observe / diagnose / authorize / act / measure / retain-or-rollback
       AL HARAS governs sensitive side effects; no search/proof authority transfer
```

### Responsibilities and prohibitions

| Component | Positive responsibility | Must not do |
| --- | --- | --- |
| Operator/configuration | Choose approved endpoint, worker, tenant/custody and submission posture | Invent credentials or bypass admission/release policy |
| Stratum client / proof adapter | Negotiate work identity and target; serialize one submission path | Accept a hypothesis as a valid proof or invent a pool response |
| AgenticMiningController | Provisional measured policy, generation-scoped plan/lease provenance | Bypass final PYTHIA composition on queue miss or fallback |
| PYTHIA | Final mining intelligence, memory, supposition, composition, search strategy and learning | Change the negotiated target or claim acceptance without pool evidence |
| Intelligence | Predictive, causal, counterfactual, topological and geometric planning evidence | Become a second writer; treat prediction/confidence as proof |
| Turing / quantum arsenal | Exact/symbolic and supported quantum algorithm surfaces composed by PYTHIA | Silently replace canonical Hendrix or claim all algorithms ran from inventory alone |
| Kellogg | Tensor mathematics, networks and compression support | Assume quantum-algorithm, mining-planning or pool-truth ownership |
| Chronus | Execute the authorised plan and record completed work/backend identity | Compile a different search plan or relabel another order as Hendrix |
| AL HARAS | Policy/identity-bound authorization and audit for protected actions | Decide nonce validity, enlarge a lease or manufacture acceptance |
| Salamander | Governed healing/optimization, measurement, rollback and durable evidence | Become the mining planner, change Stratum identity, target or proof validity |
| Session / custody / ledgers | Durable attempt/outcome attribution and replay/restart continuity | Convert missing response into accepted/rejected or confuse sent with confirmed |

## 3. Contract-by-contract workflow

The C identifiers below are documentation identifiers, not invented definitions
for historical REQ-002/008/010/020.

### C01 — Operator, tenant and custody admission

- **Input:** explicit endpoint/worker configuration, approved tenant, bounded quota,
  storage roots, separate integrity/custody keys and required AL HARAS actor/token.
- **Owner/seam:** `mining_runtime.py`; strict-M3 setup;
  `scripts/provision_m3_tenant.py::provision` and existing custody implementation.
- **Contract:** administrative admission is explicit; required settings and durable
  projection verification cannot be replaced by an in-memory success flag.
- **Failure:** missing/invalid identity, quotas, keys or verification refuses admission.
- **Evidence:** verifying loopback runtime test provisions an isolated test tenant
  through the real helper. This does not admit or certify an operator's live tenant.

### C02 — Connection and handshake

- **Owner/seam:** `production_transport.py::connect_with_failover`,
  `ProductionStratumClient`; protocol client `connect`/subscribe/authorize.
- **Input/output:** configured endpoint -> connected, subscribed, authorized session.
- **Contract:** stages remain independently observable; transport-connected is not
  ready-to-mine. Use the configured protocol/security policy, not opportunistic downgrade.
- **Failure:** close failed setup, record refusal, rotate only through configured
  endpoints; V2 secure-channel setup may refuse. V2 is not certified by V1 tests.
- **Tests:** Stratum session/state/events, production transport, transport chaos;
  canonical workflow exercises a real TCP V1 handshake to a local pool.
- **Pending proposal:** PR #14 adds strict finite timeout and queue validation;
  do not describe that fix as present on main until merged.

### C03 — Authoritative work and target

- **Owner/seam:** `stratum_adapter.py::handle_message`, `set_exact_target`,
  `parse_notify`, `replace_subscription`; coordinator work-identity refresh.
- **Input/output:** notify, difficulty/target and subscription -> bound job/header inputs,
  session/generation and extranonce widths.
- **Contract:** pool work identity/target are authoritative. New sessions and clean jobs
  invalidate old work. No target means no valid candidate/submission.
- **Failure:** malformed width/hex/target/job or stale job raises/refuses; never guess.
- **Tests:** `test_stratum_adapter.py`, `test_stratum_session.py`,
  `test_stratum_state.py`, `test_stratum_events.py`.

### C04 — Lease and upstream agentic proposal

- **Owner/seam:** `AgenticMiningController`, immutable `SearchPlan`, nonce leases;
  `geodesic_support.py::_baseline_plan`, `_build_plan`, `_apply_pythia_authority`.
- **Contract:** lease belongs to the current generation; complete authorised domain
  has no gaps/overlap. A queue miss still passes through PYTHIA.
- **Failure:** foreign generation, invalidated/replayed lease, wrong bounds or expired
  plan refuses launch. Supporting solve-first evidence cannot demote canonical identity.
- **Tests:** execution-router lease/generation/coverage tests; resident foreign-bound
  tests; PR #17 postcondition tests. Upstream generic plan preservation is PR #14.

### C05 — Intelligence, recall and supposition

- **Owner/seam:** `pythia_agentic_cycle.py::PythiaAgenticMiningAuthority.plan`,
  `_memory_recall`, `_five_modal_evidence`; `pythia_authority.py::plan`.
- **Contract:** final plan retains upstream provenance, memory recall, bounded
  five-modal result, explicit supposition and capability context. Errors/unavailable
  components are reported truthfully rather than promoted into successful inference.
- **Historical limit:** the exact old `SuppositionEngine.form_supposition` class is
  not recovered; current explicit supposition receipts are not renamed as that class.
  `Intelligence.agentic_mining.AgenticMiningWorkflow` remains advisory lineage,
  not a second Stratum writer.
- **Evidence:** canonical workflow exercises composed planning/role receipts.
  That test alone does not assert that every modality returned a useful result;
  per-plan `available`, result and reason fields remain necessary evidence.

### C06 — Quantum arsenal and tensor composition

- **Owner/seam:** `PythiaQuantumArsenal.resolve/invoke/inventory`;
  `_compute_surfaces`; Turing implementations; Kellogg tensor interfaces.
- **Contract:** Hendrix is canonical; tunnelling, annealing, swarming and entanglement
  remain reachable to PYTHIA. Other public algorithm surfaces are not artificially
  removed. Availability, selection, actual invocation and measured benefit are separate.
- **New executable support tests:** mandatory alias resolution; symbolic Landau-Zener
  reference; zero-field Ising gap; GHZ Born probabilities/correlated measurement;
  seeded swarm repeatability and its explicitly classical sampling boundary; unknown
  capability refusal. All calls go through the real PYTHIA arsenal API.
- **Not claimed:** a mining speedup, all-algorithm correctness, execution of every
  algorithm on every block, or physical entanglement from a software test.
- **Observed workspace gap:** `quantum2026` module was unavailable because the full
  `quantum_compute_substrate` package is not restored locally. The repository contains
  the package. Its Grover/VQE/QAOA/QFT/period-finding/etc aliases are **not qualified**
  in this run. Inventory's `module_complete` describes exposure scope, not availability.

### C07 — Optional corpus/VQC guidance

- **Owner/seam:** `Intelligence/mining_structure_training.py`,
  `Intelligence/bitcoin_vqc_training.py`, `_vqc_guidance`.
- **Contract:** validated historical observations/checkpoint may inform ordering only;
  absent checkpoint is `NO_CHECKPOINT`, not a fabricated trained model. Training stays
  outside the synchronous live hot path. Full raw-block custody remains optional.
- **Evidence:** default structural seed dependencies were restored byte-for-byte
  from the reviewed base to run canonical workflow tests. The CSV manifest's historical
  provenance is not a fresh independent re-verification of all historical headers.
- **Unverified here:** VQC training quality, a compatible trained production checkpoint,
  all corpus/custody suites, or prediction of future winning nonces.

### C08 — Exact structural composition and resident seal

- **Owner/seam:** `exact_search.py`, `pythia_search.py`, `resident_search.py`,
  `geodesic_support.py::_bind_plan_execution_intent`.
- **Contract:** canonical 32-face dual construction, 11D/H4-600 and Hilbert support
  feed a sealed resident Hendrix itinerary. Full authorised lease coverage survives
  composition. Do not confuse 600 logical cells with 600 observed physical devices.
- **Failure:** plan/header/target/tampering mismatch, unsealed artifact or unsupported
  exact transport refuses; executor cannot create its own replacement plan.
- **Tests:** resident geometry/coverage/serialization/tamper/bounds, exact-vs-reference
  and router resident execution cases. Hilbert selection may be explicitly declined;
  this is not evidence all optional algorithms were used.

### C09 — Chronus execution and truthful work accounting

- **Owner/seam:** `resident_router.py`, `execution_router.py::execute_plan`,
  backend registry and actual bound hasher.
- **Contract:** execute only authorised itinerary/chunks; actual completed work,
  requested/executed route, algorithm and fallback reasons remain distinct fields.
  CPU/native software execution is valid software evidence, not physical GPU evidence.
- **Failure:** stale work stops; out-of-domain candidate, count inflation, missing
  canonical executor or mismatch fails closed. Capabilities do not imply launches.
- **Tests:** execution-router and resident suites, including real software SHA256d
  and genesis verification. Hardware-only OpenCL tests are explicitly skipped here.

### C10 — Canonical execution postcondition (notes implemented in PR #17)

- **Owner/seam:** `search_authority_guard.py::require_canonical_execution`, called
  by `ProductionExecutionRouter.execute_plan` before returning a result/candidate.
- **Contract:** independently classify canonical path using plan architecture marker;
  reject non-Hendrix canonical plan before dispatch; positive completed work requires
  planned/requested/executed order to be exactly Hendrix, with no nonce-order fallback.
- **Failure:** throw before candidate escapes. Missing fallback reason proves nothing.
  Backend fallback preserving Hendrix remains distinct from algorithm replacement.
- **Zero work:** refusal may honestly omit executed-order evidence; existing
  router candidate/count validation still applies.
- **Tests:** 21 P0 boundary cases, plus actual resident success/stale/proof regressions.

### C11 — Independent proof, header and freshness validation

- **Owner/seam:** `execution_router.py::_independent_recheck`;
  `stratum_adapter.py::build_coinbase/merkle_root/build_header/validate_candidate`.
- **Contract:** rebuild canonical 80-byte header, independently compute SHA256d,
  interpret digest with correct endianness, require digest <= negotiated target;
  recheck job/session/freshness before submission. Optional seals cannot replace PoW.
- **Failure:** wrong hash/target/job/header/nonce or stale identity is not submittable.
- **Tests:** Stratum adapter, host-mismatch and genesis tests; independent verifying
  pool rejects missing-target shares, wrong workers and unknown jobs.

### C12 — Submission authority and one writer

- **Owner/seam:** coordinator search/submission path,
  `ProductionStratumClient.submit/request/_writer_loop`, `MiningSession.begin_submission`.
- **Contract:** only proof-checked current work reaches `mining.submit`; disabled
  submission can still search/verify but writes nothing. Request IDs, bounded writer
  and attempt attribution must not permit duplicate/foreign writes.
- **Failure:** timeout/disconnect/write/cancel is not acceptance. Do not blindly resend
  an unresolved written attempt as though it was never sent.
- **Tests:** production transport/receipts; canonical shadow-mode case; verifying
  loopback canonical runtime to submission. Live endpoint is not used in these tests.

### C13 — Literal verdict, unresolved state and durable custody

- **Owner/seam:** pool response handler, `MiningSession.submission_finished`,
  `_resolve_share`, execution/cycle/custody ledgers.
- **Contract:** accepted only from literal matching pool acceptance; rejected only
  from literal matching refusal. Missing outcome stays unresolved. Persist actual
  outcome and attribution, not a simulated success or local proof renamed acceptance.
- **Tests:** canonical scripted accept/reject cases, execution receipt tests;
  verifying loopback independently rebuilds coinbase/merkle/header and recomputes
  SHA256d before its verdict, then checks durable session records.
- **Limit:** scripted easy-target acceptance tests assert response handling;
  verifying loopback provides stronger local proof evidence. Neither is a live share.

### C14 — PYTHIA learning and evidence feedback

- **Owner/seam:** `geodesic_support.py::_record_execution`,
  `PythiaAgenticMiningAuthority.learn_execution`, memory/store and cycle ledgers.
- **Contract:** canonical coordinator records measured execution first, then passes
  attributed outcome to learning. Unknown pool result remains unknown; hypotheses,
  host validity, submitted work and accepted shares are different labels.
- **Evidence:** exercised by selected canonical/loopback paths; no claim that this
  run independently qualifies every memory tier, long-term training or restart mode.

### C15 — AL HARAS action authorization and Salamander modes

- **Owner/seam:** `salamander.authority.ALHarasActionAuthorizer`, control plane,
  `recovery_authority.py::RecoveryGovernor._authorize_dispatch`.
- **Contract:** protected action requires bound allow decision/evidence when strict
  authorization is required. Recheck hash-chain/replay/idempotency/deadline boundaries;
  do not consume an authorization for a different action/target/tenant.
- **Modes:** NORMAL, DE_RATE, FREEZE_SPECULATION, RECOVERING, PAUSED, FAULTED;
  existing supervisor TTL is 10 seconds. Freeze-speculation and mode precedence are
  operational contracts, not permission to mutate proof/search identity.
- **Important configuration limit:** base coordinator's recovery-authorization flag
  defaults false. Existence of the authorizer is not proof a given deployment bound
  and required it. Audit strict runtime composition separately before release.
- **Tests:** autonomic, mining-mode acceptance, authority replay and recovery-dispatch
  boundary suites. Test policies/tokens are isolated fixtures, not operator credentials.

### C16 — Salamander measured healing and optimization

- **Owner/seam:** `salamander/runtime.py::MiningAutonomyBridge`, `mining_runtime.py`
  snapshot feedback; RecoveryGovernor, ClosedLoopOptimizer and actual actuators.
- **Contract:** observe -> diagnose -> authorize -> bounded action -> measure ->
  retain improvement or reject/rollback -> hash-chained durable evidence -> restore.
  A successful restart must retain canonical execution topology, not silently demote it.
- **Failure:** missing evidence/authorization, unsuccessful postcheck or absent actuator
  cannot be labelled repaired. Recovery/optimization never owns nonce validity.
- **Evidence:** selected control-plane/authorization tests and runtime loopback path;
  these do not certify every production actuator, fault class, crash/restart or rollback.
- **Remaining:** complete installed-runtime actuator/recovery/soak/restore qualification.

## 4. Reconciliation with the original M1–M16 thesis notes

Preserve the notes as design lineage; do not relabel historical demonstration behavior
as the current production contract or silently mark it implemented.

| Historical note | Canonical mapping / disposition |
| --- | --- |
| M1 state-space initialization | C08 exact composition; current sealed resident architecture, not a claim the old TypeScript amplitude state is in the hot path |
| M2 Chebyshev K* | Specific historical Grover iteration optimizer not qualified as the canonical Hendrix driver; retain as support research until exact implementation/invocation evidence exists |
| M3 Grover/oracle/Lucas steps | Turing support under C06; do not equate supported Grover mathematics with an evaluated Bitcoin validity oracle or demonstrated O(sqrt(N)) mining cost |
| M4 clean_jobs interrupt | C03/C04/C09/C11 freshness/generation cancellation; selected tests |
| M5 Born candidate extraction | Support algorithm evidence C06; not the sole canonical candidate extractor or a substitute for SHA256d |
| M6 face/local nonce derivation | C08 lease-preserving canonical itinerary; historical 5/27-bit encoding is not silently asserted identical to the current resident mapping |
| M7 exact header | C11 canonical coinbase/merkle/80-byte serialization; selected tests |
| M8 MeetsTarget | C11 digest <= negotiated target only; historical `passes || nonce % 4 === 0` demonstration fallback is forbidden on the production proof boundary |
| M9 share resolution | C12/C13 real wire submission and literal verdict; historical `markShareResolved(..., true)` simulation is not production acceptance |
| M10 exact audit trail | C08/C10/C13 provenance/seals/receipts; no claim all old nine invariants or RTL assertions were rerun |
| M11 telemetry/hashrate | C09 measured completed work/time; configured ceiling, topology and sampling are not measured hashrate |
| M12 breaker/failover | C02/C15/C16; selected failure tests, full operational soak remains pending |
| M13 mempool template | Pool-supplied canonical jobs in this path; independent solo-node template builder not qualified here |
| M14 retargeting | C03 pool target updates; independent Bitcoin consensus retarget implementation not certified by Stratum tests |
| M15 quantum-walk optimization | C06 available support, C16 governed measured changes; no blanket claim every walk is selected or profitable |
| M16 consciousness/face integrity | Mathematical/integrity lineage, not an independent production health certificate; selected exact geometry tests are narrower |

These distinctions keep the notes actionable without replacing Hendrix, shrinking
coverage, inventing oracle knowledge, or weakening proof/pool truth.

## 5. Evidence, implementation gaps and release gates

See `qualification/mining-workflow-contracts/README.md`, retained logs, inventory,
JUnit report and manifest for the final selected-test result and exact source scope.
The executable support tests are `tests/test_mining_quantum_support_contracts.py`;
P0 runtime integration remains `tests/test_p0_canonical_execution_boundary.py`.

Still required before a blanket production-ready claim:

1. Review/merge applicable PR #14 and #17 changes with exact-head CI and protected gates.
2. Clean install the complete repository and run unsuppressed doctrine/P0/full regression.
3. Restore and qualify the complete quantum substrate package; inspect per-plan
   Intelligence/arsenal selection and invocation evidence, not inventory alone.
4. Audit actual strict AL HARAS/tenant/network binding and all enabled actuators.
5. Run composed-service fault/soak/restart/backup/restore/rollback qualification.
6. With approved private runtime configuration, retain independent live-pool response
   evidence before claiming an external accepted share. No live activation here.

No merge, deployment, public release, physical-fleet measurement or accepted live
share is implied by this document. Mining remains private treasury infrastructure.
