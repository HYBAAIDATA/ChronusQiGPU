# M5 AGENT PRODUCTION HANDOVER — whole PYTHIA organism
Date: 9 October 2026
Authority: repository owner; 5 October canonical HYBA Authority Register; owner-locked PYTHIA Structured-Search Doctrine.
Source: QuantumPhiRedux/PhiMiner.
Target: Apple M5, macOS arm64, exact reviewed source and installed distributions.
Status at drafting: **HANDOVER + CODE CANDIDATE / QC_HOLD**, not an assertion of production certification.

## 0. Mission, authority and reporting contract

GOAL: produce a real installed, continuously operable mining organism on the M5:
EUCLID intelligence orchestration → PYTHIA causal/modeled Hendrix planning
→ 12 dodecahedral + 20 icosahedral directions → exact 32-face overlay
→ φ-weighted 11-dimensional frame → H4 600-cell (120 primal vertices,
600 tetrahedra) → 600 dual logical positions, degree-four adjacency,
1,200 dual edges → TURING 11-qubit/2,048-state exact coined Hilbert
rank → 600 complete nonce shards → CHRONUS/ONE-iGPU prepared ASIC-like
execution → independent host SHA256d and negotiated target →
AL HARAS decision + THESEUS HMAC/custody → serialized real Stratum
mining.submit → literal pool response → PYTHIA learning →
SALAMANDER bounded diagnosis/authorised remediation/measurement →
EUCLID subsequent advice/changed bounded decision → OVID exact optional
materialisation/THESEUS fresh-process recovery → repeat.

PYTHIA owns Bitcoin mining semantics/final SearchPlan. EUCLID delegates and
advises; it cannot rewrite shares. SALAMANDER alone chooses/executes permitted
healing and optimisation; EUCLID/PYTHIA only correlate measured outcomes.
CHRONUS owns execution; TURING owns exact VQC capabilities. THESEUS owns
authoritative durable custody/journal/recovery, OVID owns versioned
representation transformations, Geodesic owns rebuildable indexing and
AL HARAS owns security/governance. Do NOT move authority, weaken the
owner-locked 32→11D→600/Hendrix doctrine or update ontology without the owner.

Owner has explicitly asked to prepare and enable live pool submission today.
This permits implementing and deploying through verified gates; it does not
override AL HARAS policy, identity/credentials, test requirements or independent
Bitcoin proof. Never label an unacknowledged share ACCEPTED. Never publish
packages or merge a draft with failing mandatory checks.

**One checkout, one active ownership board.** Do not let agents overwrite
each other's work. Each agent owns only its lane below, records commits
and sends the integration lead a concise evidence packet, not declarations
of readiness without executed tests. Integrator owns cross-lane reconciliation
and is the only one to request merge/release approval.

**Never promote work from old M5 logs or previous source snapshots to
current-head evidence.** GitHub Actions ending before the first step are
INFRA_UNAVAILABLE, not code PASS/FAIL. Any claimed executed test needs
Junit/log + Python/build identity + exact Git SHA.

## 1. Canonical source anchor and prior incident recovery

Repo: https://github.com/QuantumPhiRedux/PhiMiner
Remediation: https://github.com/QuantumPhiRedux/PhiMiner/pull/163
Candidate branch: fix/pythia-m3-custody-replay-20261009
The branch is a DRAFT and includes EUCLID/SALAMANDER feedback remediation.
DO NOT assume it has been merged into main. First check PR head and base,
cross-lane changes, conflicts, and repo ownership. Record SHA of actual
checkout, remote origin and branch. Never force push main.

The retained prior M5 logs are repository files m5, m5evidence, M5run:
- Obsolete main.py process from a moved-to-Trash checkout retained control
  locks and spawned children from the wrong path.
- /run/pythia/hb is a Linux-only default; use a writable durable Mac path.
- IntelligentPoolCoordinator asynchronous_submission/submission_queue_size and
  Pythia _record_execution(defer_pool_outcome) had signature regressions.
  Their source fixes appeared on inspected main; prove tests again on target SHA.
- A 3.13.16 venv was created, but source-tree imports masked incomplete
  installed distributions; build tooling and frontend were missing.
- Real Stratum jobs/CPU shadow hashing were seen. That did not prove M5 GPU
  execution or external accepted shares.

On M5 execute BEFORE starting any supervisor:

~~~bash
cd ~/Desktop/PhiMiner
pwd -P
ps -axo pid,ppid,user,command | grep -E '[m]ain.py|[m]ining_runtime.py|[d]iscovery_runtime.py'
git remote -v
git fetch origin --prune
git status --porcelain=v1
git rev-parse HEAD
git rev-parse origin/main
git branch --show-current
sw_vers
uname -sm
xcode-select -p
system_profiler SPHardwareDataType SPDisplaysDataType
~~~

Manually verify parent/child PID, executable, cwd, boot-lock owner and
service configuration. Use graceful service stop; do NOT pkill all python
or delete a live lock. Quarantine obsolete checkout without moving an active
service underneath it. Backup durable data, CAS, SQLite, THESEUS custody,
replica/journal, AL HARAS audit and recovery keys to an operator-controlled
encrypted store; test restore before attempting schema migration. Backups
MUST NOT appear in Git or CI logs. Record mount space, permission and
file-lock ownership. Keep all durable state outside /tmp and /run.

## 2. Agent assignments — independent, non-overlapping scopes

**Agent A / Package & M5 Host** owns Mac env, artifact/build manifests,
overlap inventory, dependency lock, installed wheels, native-arm64 build,
startup process/heartbeat, Node and UI. Does not alter mining mathematics,
intelligence or security ontology. Deliver version/manifest ownership matrix,
wheel and sdist SHA256, interpreter/site-packages map, JUnit and service
process tree. Detect CHRONOS ONE manifest/catalog name-version mismatch,
PYTHIA umbrella namespace collisions, and numpy/sympy conflicts. No version
change without the owner-approved version plan.

**Agent B / EUCLID, PYTHIA & TOE Intelligence** owns the real composition
and the bounded mining advice loop. Trace EUCLID production runtime,
shared ProductionOrganism, the separate EuclidMiningSupport instance,
PYTHIA learned plan and outcome. Prove a measured pool/network outcome
reaches the governed learning service, persists, replays, and can change a
subsequent bounded decision. Absent reward cannot become invented reward.
Tests must detect missing PYTHIA specialism, a second independent custody
root, stale learner snapshot and revoked action rights. TURING is support,
not consensus authority.

**Agent C / Geometry, Hendrix & CHRONUS iGPU** owns the exact 32-face
dual geometry, phi-weighted 11D lift, H4 120/600 topology, 600 dual positions,
TURING exact rank, Hendrix coprime traversal, exclusive leased nonce estate,
resident ONE iGPU route and ASIC-like prepared SHA256d scanner. Prove each
operation's execution backend and independent oracle parity. Do not claim
physical M5 GPU from a CPU fallback; no unsupported QPU or hash-rate
multiplier claims.

**Agent D / SALAMANDER, AL HARAS, OVID & THESEUS** owns authorised
observe/diagnose/act/verify/rollback, storage tenant admission, exact OVID
source/transform/restore, HMAC provenance and anti-tamper/replay. Verify
SALAMANDER result is not merely a HEARTBEAT/HEALTHY label; test actual
actuator invoked, independent effect verification, failure rollback and
restart. The recent branch adds SALAMANDER→PYTHIA→EUCLID observation plus
a THESEUS causal receipt: review/test this exact head and retain separate
source-mirror vs canonical custody evidence.

**Agent E / Stratum & Release Gate** owns one canonical supervisor, Stratum
handshake, freshness/target/oracle, failover/rearm, serialized submission
and pool literal replies. Real pool credentials/token are operator-managed;
do not print. Qualify live use ONLY after A–D accepted by lead and strict
M3/AL HARAS is healthy. Never substitute the legacy stratum_bridge.py
one-share smoke for canonical M3 evidence.

**Integrator / QC lead** owns exact-head reconciliation, full test suite,
new-vs-baseline failure triage, release manifest, gates, rollback rehearsal
and final single GO/NO-GO. No agent may unilaterally declare a production
release or silently change the architecture/register.

## 3. Build a completely new Mac environment — do not reuse old venv

A package importing from current checkout is NOT proof it installs.
Python 3.12 is a first candidate for compatibility; if using 3.13,
re-resolve explicit ARM64 constraints and reproduce a clean build.
The root requirements-lock.txt and CHRONOS ONE iGPU constraints have
known incompatible numpy/sympy pins. Resolve without ad hoc upgrades,
retaining lock hashes / origin/version for every wheel.

~~~bash
command -v python3.12
python3.12 --version
python3.12 -m venv .venv-m5
.venv-m5/bin/python -m pip install --upgrade pip build wheel twine pytest
.venv-m5/bin/python -m pip check
.venv-m5/bin/python -m pip list --format=freeze
.venv-m5/bin/python -m pip debug --verbose
~~~

Required artifact inventory: KELLOGG, TURING, THESEUS, OVID, TOE, EUCLID,
CHRONUS mathematics, CHRONOS ONE iGPU, SALAMANDER, PYTHIA mining and
mining runtime, with AL HARAS as an audited dependency. Read
packaging/publication_catalog.json and every actual pyproject.toml.
For each independently owned distribution:
(1) source commit, package name/version, Python/ARM64 compatibility;
(2) isolated sdist build → wheel-from-sdist;
(3) clean target installation with no .pth/PYTHONPATH source leakage;
(4) pip check, importlib.metadata version, RECORD ownership collision scan;
(5) module import in python -I from outside the checkout;
(6) license/metadata/secret scan; (7) package functional tests, startup;
(8) artifact hashes, audit and reproducible release manifest.
Do not publish until exactly the tested artifact is promoted, never rebuild
an unverified new archive for production. If one wheel overwrites another
package's namespace or import origin differs from the qualified wheel: NO-GO.

The CHRONOS ONE upstream dual source namespaces (chronos and
chronos_one_igpu) require explicit artifact-content inspection; the latter
is the intended installed standalone namespace. Preserve SOURCE lineage.
Do not call a source-level CPU fallback a native Apple GPU installation.

## 4. Mac runtime and security environment

Use a persistent owner-controlled app data directory, for example:

~~~bash
mkdir -p "$HOME/Library/Application Support/HYBA/PhiMiner/heartbeats"
export PYTHIA_WORKER_HEARTBEAT_DIR="$HOME/Library/Application Support/HYBA/PhiMiner/heartbeats"
~~~

Review PYTHIA_BOOT_LOCK, PYTHIA_BOOT_AUDIT, runtime config path, EUCLID
state path, SALAMANDER evidence path, PYTHIA agentic state, CAS and THESEUS
storage roots, service user, ulimit, backup retention, secure filesystem mode.
Build frontend only after installed Node version and lockfile are inspected;
use npm ci and actual frontend tests/build in its package.json directory.
Do not claim UI ready with dist/public missing. Protected /readyz and
/metrics must remain authenticated; never strip AL HARAS checks to make
health look green.

For strict M3, secret manager/config supplies:
PYTHIA_M3_REQUIRED=1,
PYTHIA_STORAGE_DB,
PYTHIA_STORAGE_ROOT,
PYTHIA_STORAGE_CUSTODY_ROOT,
PYTHIA_STORAGE_TENANT,
PYTHIA_STORAGE_INTEGRITY_KEY_HEX,
PYTHIA_STORAGE_CUSTODY_KEY_HEX,
PYTHIA_M3_ACTOR,
PYTHIA_M3_AL_HARAS_TOKEN,
and valid AL HARAS guardian audit/policy/identity configuration.
The two 32+ byte HMAC/integrity secrets MUST be distinct. Do not print
secret values, store secrets in repo, or put credentials in command arguments.

Provision approved tenant once, *before* strict worker startup, on the
same persistent database and custody root:

~~~bash
.venv-m5/bin/python scripts/provision_m3_tenant.py \
  --tenant "$PYTHIA_STORAGE_TENANT" \
  --max-records 1000000 --max-bytes 10000000000 --approve-tenant
~~~

This only creates/verifies storage admission: it does NOT replace a live
AL HARAS Guardian policy/allow decision. Repeated provisioning with changed
quota must refuse implicit changes. Never auto-register tenants in strict M3.
Use PYTHIA_STORAGE_OVID_EXACT=1 only where the precise transformation
policy is approved; verify exact unfold and original source retention.
Check that a new process refuses to reuse an old Stratum job/lease/proof
as current authorisation.

## 5. Exact 32 → 11D → H4/600 structure (Agent C's mandatory proof)

Source of truth:
docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md,
docs/PYTHIA_CANONICAL_MINING_SEARCH.md,
docs/RESIDENT_HENDRIX_ONE_IGPU.md,
governance/canonical_mining_search.yaml,
chronus/mla1517/mining/pythia_search.py,
chronus/mla1517/mining/resident_search.py,
chronus/exact_geometry.py, chronus/h4_600.py, chronus/h4_group.py,
chronus/h4_coverage.py, chronus/cell600_bind.py,
chronus/mla1517/mining/h4_600_execution.py,
chronus/resident_hendrix.py, chronus/one_igpu_mining.py.

Check with independent oracle and multiple distinct real header fixtures:
- Exactly 12 dodecahedral + 20 icosahedral face directions, 32 total.
- Exact phi-weighted 11D coordinates, positive-symbolic radical and Q(phi)
  semantics; no hidden binary64 substitutions in strict exact profile.
- H4 exact 120 primal vertices, 600 tetrahedral cells. The *dual* search
  representation provides 600 logical positions, not 600 primal vertices.
- 600 distinct dual positions, degree four per node, exactly 1,200 edges.
- Each of the 32 coarse directions covers >=1 dual position; no dropouts.
- Exact 11-qubit Hilbert coined walk, 600 valid positions in 2048 basis,
  complete 600-element rank/permutation; check reachable 300-step horizon.
- Sealed geometry/Hilbert source digest is reproduced independently.
- PYTHIA SearchPlan immutable and binds job fingerprint, pool session,
  generation, target, header, selected 32-face direction, 11D/H4 digest,
  600 itinerary, lease bounds and Hendrix identity.
- Hendrix uses a coprime stride/permutation over the complete leased nonce
  set; no repeated candidates, omissions, overlaps between parallel lanes,
  dropped 32/600 high-resolution shards or illegal epoch reuse. Verify
  awkward lease lengths (prime/composite), wraparound and cancellation.
- Turing ranking changes only ORDER, not Bitcoin winner probability or
  proof predicate. The exact-Hilbert route cannot be claimed physical QPU.
- Corrupt/resealed geometry, swapped normal, wrong header/target, stale
  generation, invalid plan signature and an out-of-domain nonce MUST refuse.
- Full resident ONE iGPU route must actually consume the compiled sealed
  Hendrix plan, not independently recompute/replace PYTHIA's order.

Primary executable checks from repo (resolve actual test collection in
current checkout; never silently skip a renamed test):

~~~bash
.venv-m5/bin/python scripts/check_canonical_mining_search.py
.venv-m5/bin/python -m pytest -q --junitxml=artifacts/geometry.xml \
  tests/test_canonical_mining_search_doctrine.py \
  tests/test_exact_geometry.py tests/test_resident_hendrix.py \
  tests/test_chronus_h4_600_mining.py tests/test_golden_stride.py
~~~

Require independent reference order vs actual executor completed nonce
receipts and a real hardware-route probe, not only an import or static
topology count. Resident adapter CPU-only = CPU evidence, never GPU.

## 6. ASIC-like ONE iGPU execution features (Agent C, separate gate)

Read packages/chronos-one-igpu/docs/ASIC_MINING.md,
packages/chronos-one-igpu/src/chronos_one_igpu/igpu/asic_mining.py,
packages/chronos-one-igpu/src/chronos_one_igpu/igpu/native/sha256d_native.c,
virtual_igpu_v1 workload handlers and resident_hendrix / hendrix600.cl.
Test *all* features as executed capabilities, not as labels:

- Prepared first SHA256 block midstate for header[0:64]; correct second
  block/tail/time/nonce rolling; independently compare complete SHA256d with
  hashlib for every returned candidate and chosen non-winning nonces.
- Same first-block prefix -> legitimate cache hit; changed merkle/version
  -> new preparation; changed target/job/epoch -> refreshed identity and
  checks even if midstate reused. Reject cache poisoning/cross-tenant use.
- Full-digest exact target predicate, endian/nonce serialization, vector
  boundaries, zero target, genesis fixture and random fixed-seed fixtures.
- S1–S6 solve-first planner retained when invoking main OneIGPU.mine path;
  alternative MiningFarm scheduling cannot be presented as whole S1–S6.
- Parallel lane non-overlap, bounded inflight, batch counts, cancellation,
  stale epoch, failover, work completion and cursor/checkpoint restore.
- Restart keeps completed out-of-order spans and does not resubmit unknown
  post-write pool outcomes. Retry idempotency and conflicting job/lease reject.
- ASICDriverBridge only binds declared executable hardware with valid
  driver/digest; proprietary candidate-only protocol is NOT full-hash proof.
- virtual_igpu_v1 asic_sha256d workload has owner admission, lease bounds,
  sealed input/output and honest backend/device identity.
- Explicit actual M5 native/OpenCL/Metal/MLX adapter capability census;
  operation-specific launched kernel count and completed work must be >0
  to label operation GPU_EXECUTED; numpy, software SHA256d or MLX model
  ranking alone is not M5 GPU SHA256d proof.
- Native and portable paths independently agree on hashes/target, plan
  coverage and receipt meaning; if native fails and portable works,
  permit CPU only with clear label and explicit policy, never silent
  equivalence, invented hardware speed or ASIC presence.
- Measure *whole pipeline* SHA256d/s from completed hashes / monotonic
  elapsed time, separately including preparation, transfer and verification.
  Compare warm/cold cache, equal work budgets, same target, device, precision,
  asynchronous synchronisation and sustained thermal operating state.
  No claimed 600×, QPU speedup, hashrate determinism or EXAHASH tier without
  independent reproducible measured evidence.

Run distribution's own installed release gate for BOTH variants (requires
a complete clean installation and a proper package-build environment):

~~~bash
.venv-m5/bin/python packages/chronos-one-igpu/scripts/verify_m5_package.py --variant native
.venv-m5/bin/python packages/chronos-one-igpu/scripts/verify_m5_package.py --variant portable
.venv-m5/bin/python -m pytest -q --junitxml=artifacts/m5-igpu.xml \
  packages/chronos-one-igpu/tests/test_generic_m5_features.py
~~~

Read script flags and output paths before running: if the existing verifier
fails for missing dependencies, fix the actual packaging defect and rerun;
do not patch away a mandatory test. Native Mac build must be rebuilt *on Mac*;
the historic Linux CPython 3.13 wheel is NOT a macOS proof.

## 7. EUCLID + PYTHIA + TOE intelligence closed loop (Agent B)

The source has TWO routes that must be reconciled by actual integration:
- system_fabric.euclid_cognition() constructs EuclidRuntime.production,
  exposes cognition solve and its separate durable state;
- the mining coordinator inherits EuclidProductionMiningCoordinator using
  EuclidMiningSupport/ExperienceSuperlearner, advising only HOLD/REDUCE/RESTORE.
The mining support is NOT automatically a proven instance of all v17
episode/TOE custody/learning. Do not claim full integration from importing
both components. Reuse the existing shared ProductionOrganism / system
relations and data ports when valid; do NOT create another authority root
or private Triad to paper over the separation.

On the branch, production() had an undefined custody reference; check the
corrected adaptive_data_port binding path, instantiate in an isolated
process, and prove its actual lifecycle. Run an end-to-end episode:
1. capture real Stratum work and measured network/processing observations;
2. represent typed PYTHIA MiningCognitionProblem in EUCLID;
3. show explicit authorised EUCLID/TURING/TOE proposal, selected policy
   identity/checkpoint seal, and PYTHIA final SearchPlan;
4. verify advisor only influences bounded dispatch breadth, never header,
   target, proof, job identity, or pool reply;
5. execute real SHA256d/target (loopback for initial fixture) under CHRONUS;
6. retain literal measured outcome with job/session/tenant and source digest;
7. feed new measured reward once into EUCLID learner, record correct
   RewardAuthority (no reward for unsubmitted/unknown outcomes);
8. show persisted canonical THESEUS/OVID knowledge/causal evidence, stop
   and restart fresh interpreter; independently verify integrity and replay;
9. same frozen input + restored state yields stable verified behaviour; a
   deliberately changed result causes a bounded policy difference only if
   real evidence supports it (do NOT force a change and call it learning);
10. revoked AL HARAS rights, tampered learning manifest, stale feedback and
    missing specialism fail closed. All THREE owners visible in trace.

Run:

~~~bash
.venv-m5/bin/python -m pytest -q --junitxml=artifacts/intelligence.xml \
  tests/test_euclid_cognition_production.py \
  tests/test_euclid_v17_production_integration.py \
  tests/test_organism_integration.py \
  chronus/mla1517_platform/python/test_euclid_cognition_entrypoint.py \
  chronus/mla1517_platform/python/test_euclid_mining_support.py
.venv-m5/bin/python scripts/euclid_v17_integration_gate.py \
  --output artifacts/euclid-v17.json
~~~

Required v17 F1–F6 assertions: real governed delegation, revoked rights,
specialist component contribution, fresh-process persistence/replay, stable
organ identity, canonical adaptive custody and negative-transfer checks.
If production episode route remains separate from PYTHIA mining learn path,
mark INTEGRATION_GAP and repair without altering PYTHIA authority.

## 8. SALAMANDER closed-loop proof (Agent D)

Sources: salamander/runtime.py, salamander/control_plane.py,
salamander/outcome_evidence.py,
chronus/mla1517/mining/geodesic_support.py,
chronus/mla1517_platform/python/mining_runtime.py,
chronus/mla1517/mining/storage_recorder.py.
Branch contains changed-observation custody and EUCLID bounded feedback.
Inspect the SHA/fixture and test before accepting this as a production claim.

Execute an injected *real, controlled* degraded mining state and capture:
observe → diagnose exact fault → propose action under SALAMANDER ownership
→ AL HARAS authorises ACTUAL action/lease → apply through approved executor
→ independently measure post-action result → accept/reject/rollback
→ custody exact verdict in THESEUS → restart/reconcile/replay → continue
monitoring. Test network loss, bad pool job/stale lease, CPU/device unavailable,
tampered receipt, missing actor/token, expired policy, quota exhaustion,
duplicate recovery ID and failure of rollback. A report containing HEALTHY
or classification WIRED proves observation only; SELF_HEALING requires
measured verified action, SELF_OPTIMISING requires comparable before/after.

The current local SALAMANDER JSONL mirror is explicitly
LOCAL_MIRROR_NOT_CANONICAL_THESEUS; branch's new PYTHIA causal receipt
is an added canonical observation, not the same thing as migrating the
entire SALAMANDER action/outcome ledger to shared THESEUS custody.
If cross-process recovery or actual action verification is unavailable,
leave SELF_HEALING/SELF_OPTIMISING UNAVAILABLE.

Check and run:

~~~bash
.venv-m5/bin/python -m pytest -q --junitxml=artifacts/healing.xml \
  tests/test_salamander_outcome_evidence.py \
  tests/test_m3_runtime_closure.py \
  chronus/mla1517_platform/python/test_euclid_mining_support.py
~~~

Then inspect/run the repo's salamander_evidence_mutation script's actual
CLI arguments, capturing mutation matrix and expected refusal. If tests are
renamed, locate the canonical successor; zero collected tests is NO-GO.

## 9. THESEUS/OVID integrity, replay and fail-closed gate (Agent D)

The mined causal chain should durably retain:
job → PYTHIA plan → lease → execution → candidate verification →
verified proof → submission → pool outcome → learning; and independent
SALAMANDER recovery observations. Each record: stable ID, producer/schema
version, timestamp/sequence, tenant, pool session/job/generation, lineage
parents, correlation IDs, content hash, backend identity, evidence state,
AL HARAS authorisation and validated custody receipt. OVID transform children
must bind their original sources, exact contract, roundtrip/unfold digest,
and preserve THESEUS as the custody authority.

Run:

~~~bash
.venv-m5/bin/python scripts/check_storage_registry.py
.venv-m5/bin/python -m pytest -q --junitxml=artifacts/theseus.xml \
  tests/test_m3_file_registry.py tests/test_m3_adversarial.py \
  tests/test_m3_storage_voyage.py tests/test_m3_runtime_closure.py \
  tests/test_m3_bootstrap_adapters.py
.venv-m5/bin/python scripts/m3_evidence_pack.py --out artifacts/m3-evidence
~~~

Mandatory negatives: altered SQLite payload/parent/version, corrupted or
missing blob, swapped HMAC key, denied/unknown tenant, stale source file,
wrong code SHA, truncated journal, OVID unfold mismatch and replayed event.
Perform ACTUAL OS-process termination/restart with the same persistent
custody root and separately verify records. Verify no old lease/proof is
reused to justify a new submission. Test interrupted custody write/retry
deduplication and conflicting payload rejection.

The branch changes idempotency/replay, opt-in OVID fold, explicit tenant
admission and duplicate receipt filtering. Qualification must cover the
exact new HEAD; do not copy historical M3 pack success into this release.

## 10. Canonical pool, live submit and negative network cases (Agent E)

Use chronus/mla1517_platform/python/mining_runtime.py
→ M3PythiaProductionMiningCoordinator, not the legacy one-share bridge.
The canonical operator API is bound to active endpoint+worker; switching pool
automatically revokes approval. Branch rejects CLI --submit without strict
M3 and dashboard approval without measured M3 worker readiness. Enable only
after custody/AL HARAS/CPU-or-M5 backend are actually qualified.

Steps:
1. Begin SHADOW with real network identity/config, no live approval.
   Observe subscribe/authorize/notify, current job/target, CPU/GPU route
   with measured provenance and stable heartbeat. No send permitted.
2. Controlled in-process/fresh-process local pool fixture: exact proof,
   accepted/rejected, stale clean_jobs, disconnect before/after write,
   unknown ACK, duplicate share, target retarget, failover and re-arm.
3. Confirm pool ACK semantics are literal. Submission success != acceptance;
   after-write disconnect => OUTCOME_UNKNOWN, never fabricated success.
4. Verify strict AL HARAS lease/proof decision and THESEUS custody BEFORE
   any socket write, with independent host SHA256d + target immediately
   before sending and current-job revalidation.
5. Once A–D integrated gates are PASS, the *owner-authorised* deployment can
   arm the existing control API live_submit enabled:true under the real
   authorised operator credential. The API must report healthy strict M3,
   an exact endpoint+worker approval and an active authorised session.
6. Capture one bounded production interval of real SHA256d candidate work,
   any actual submit attempt and literal pool acknowledgements. There may
   be no share found in a short interval; lack of an accepted share is NOT a
   pass for external acceptance and does not justify inventing a result.
7. Disarm via live_submit enabled:false; prove no further writes occur after
   the documented re-read boundary. Revoke on fault, stale work, unavailable
   custody, loss of AL HARAS, wrong backend, or security regression.
8. Distinguish connected-to-pool, hashing, candidate-found, attempted-submit,
   accepted share, and block mined. Each is separately supported by evidence.

Run software-bound test/safety preflights:

~~~bash
.venv-m5/bin/python -m pytest -q --junitxml=artifacts/stratum.xml \
  chronus/mla1517_platform/python/test_live_submission.py \
  tests/test_m3_runtime_closure.py tests/test_production_preflight.py
.venv-m5/bin/python scripts/production_preflight.py \
  --profile application --strict --output artifacts/app-preflight.json
~~~

Run --profile live only AFTER actual M3, pool credentials, identity-bound
operator approval, and the native-device gate requirements are met. The
current preflight's device logic is OpenCL-centric: if real M5 Metal/ONE
iGPU is the chosen backend, fix its capability probe (not its requirement
to observe work) before claiming that profile PASS. Never set legacy
HYBA_ENABLE_LIVE_SHARE_SUBMIT/HYBA_AUTONOMOUS_EXTERNAL_ACTIONS to bypass
the canonical coordinator.

See docs/production/LIVE_MINING_GO_LIVE_20261009.md.

## 11. Full orchestrated gate and failure triage

Only after agents A–E have produced PASS/FAIL artifacts on the SAME SHA:

~~~bash
mkdir -p artifacts
.venv-m5/bin/python scripts/m5_transfer_preflight.py --execute \
  --output artifacts/m5-transfer-preflight.json
.venv-m5/bin/python scripts/euclid_v17_integration_gate.py \
  --output artifacts/euclid-v17.json
.venv-m5/bin/python scripts/m3_evidence_pack.py --out artifacts/m3-evidence
.venv-m5/bin/python -m pip check
.venv-m5/bin/python -m pytest -q --junitxml=artifacts/full-python.xml
~~~

Inspect every command exit code AND its JUnit collection count. Scripts
must not report PASS for skipped/zero-collection, missing tests, unrelated
snapshots or untrusted previously generated evidence. Run targeted
security, native and Mac hardware checks plus frontend tests/build in
their true package build roots. Treat packages as not qualified until
wheel AND rebuilt-sdist wheel both pass clean installed tests.

Compare failing tests on candidate vs exact main baseline in separate
clean worktrees/environments. Label NEW_REGRESSION, BASELINE_IDENTICAL,
INFRASTRUCTURE, PLATFORM_UNSUPPORTED or EVIDENCE_UNAVAILABLE with logs.
No suppressions, changed tests to avoid failures, new synthetic telemetry,
or silent CPU fallback. If test tooling fails at runner allocation and no
steps execute, result is CI_UNAVAILABLE; request functioning enterprise
runner/repair and rerun.

## 12. Acceptance report / handover artifact required from each agent

Save one machine-readable + human-readable packet to artifacts/m5-release
(outside committed source and without secrets):
- exact Git SHA, branch/base, clean/dirty state, M5 model/macOS/arm64,
  Python+Node version, pip freeze and installed distribution RECORD hashes;
- commands invoked, exit codes, stdout/stderr SHA256, JUnit counts and
  actual wall-clock/test duration; identifiers of zero-run gates;
- exact source/line mappings of produced capability, test and receipt;
- matched geometry/Hendrix nonce-estate digest and 32/11D/H4/600 counts;
- SHA256d independent test vector parity, backend/device identity and
  completed work; physical GPU kernel events separately from CPU;
- EUCLID episode delegation/rights, PYTHIA SearchPlan, observed outcome,
  SALAMANDER authorised action/verified rollback, learning/custody replay;
- AL HARAS approval and THESEUS seal IDs (NOT raw credentials);
- native vs portable wheel SHA256, subprocess restore receipt,
  benchmark controls and full end-to-end path IDs;
- live Stratum session/job, attempted submissions, actual pool replies,
  shares accepted/rejected/unknown (explicit zero/unavailable);
- all failed gates, rollback plan, operator stop/revocation procedure,
  and owner-gated decisions requiring approval.

Hard release gates:
G0 source/architecture/owner-lock; G1 packages/ABI/dependency and Mac host;
G2 exact topology/traversal/coverage; G3 backend/ASIC-like execution/parity;
G4 EUCLID/PYTHIA/TOE decision + learner replay; G5 SALAMANDER
authorised closed-loop; G6 AL HARAS/THESEUS/OVID integrity/restart;
G7 live Stratum canonical pre-submit/submit/ACK; G8 CI/full matrix/UI/ops.

GO only when all APPLICABLE gates execute and PASS on a single reviewed
release SHA, and actual operator credentials/approval are valid. Without
M5 physical execution receipts, CPU-only release scope must be explicitly
restricted to CPU; without a literal external accepted share, the
accepted-share claim is UNAVAILABLE. Keep whole-product publication
NOT_CERTIFIED / QC_HOLD if any mandatory gate is missing.

## 13. Priority order and first action when agents log in

1. Record source SHA, resolve the branch/PR and stop stale processes.
2. Run the clean M5 package/venv installation and platform preflight.
3. Fix only blockers found in owned lanes; keep exact test evidence.
4. Verify the 32/11D/H4/600/Hendrix and actual ASIC-like backend parity.
5. Prove EUCLID→PYTHIA learning, SALAMANDER→EUCLID feedback, and
   THESEUS restart as one correlated voyage.
6. Prove AL HARAS + proof custody before any live wire write.
7. Run end-to-end shadow then bounded owner-authorised live submission.
8. Freeze one exact revision, rerun ALL gates, publish approved artifacts
   ONLY after package, CI and product go-live QC has passed.

Related required reading:
- docs/production/APPLE_M5_TRANSFER_20261009.md
- docs/production/LIVE_MINING_GO_LIVE_20261009.md
- docs/production/PYTHIA_M3_CUSTODY_REPLAY_QUALIFICATION.md
- docs/PYTHIA_CANONICAL_MINING_SEARCH.md
- docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md
- docs/RESIDENT_HENDRIX_ONE_IGPU.md
- packages/chronos-one-igpu/docs/ASIC_MINING.md
- docs/EUCLID_V17_INTEGRATION_GATE.md
- docs/SALAMANDER_OUTCOME_BOUNDARY.md

If a referenced file, test, binary, component or endpoint is unavailable on
the chosen exact SHA, record precisely what is missing and treat that gate
as FAILED/UNAVAILABLE. Never silently substitute a mock, guess a command,
or reclassify an owner-required capability as optional to claim GO.
