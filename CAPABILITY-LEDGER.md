# Euclid Emergence Research Track: Capability & Evidence Ledger
**Repository**: `PhiEnterprise-main` (`C:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main`)  
**Feature Branch**: `emergence-track/phi-2`  
**Approved Head**: `5c608b09` (`feat: Euclid frontier implementation and evidence (8/8)`)  
**Standard**: EQS-CAP-LEDGER-V2  
**Status**: PARTIAL LOCAL VERIFICATION; QUALIFICATION / MERGE BLOCKED  

---

> Historical implementation claims and test totals below are retained as reported provenance, not current independent verification. The dated review slice at the end supersedes any conflicting readiness claim.

## 1. Discovery Record & Repository Confirmation

### 1.1 Discovery Paths Searched
- `C:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main` (Confirmed primary Euclid monorepo)
- `C:\Users\leonn\OneDrive\Desktop\euclid-core_-quantum-algebraic-&-stratum-protocol-engine` (Ancillary exact-lane engine)
- `C:\Users\leonn\.gemini\antigravity\scratch\euclid_eqs` (Scratch development environment)

### 1.2 Selection Rationale
The repository `PhiEnterprise-main` was confirmed as the canonical Euclid codebase based on:
1. Presence of core Euclid organs: `euclid/kairos_qualification.py`, `euclid/capability_matrix.py`, `euclid/contracts.py`, and `euclid_delegation.py`.
2. Existing capability manifests: `reports/EUCLID_CAPABILITY_MANIFEST.json` and `docs/euclid_frontier_capability_manifest.json`.
3. Alignment with `OWNER_DECLARATIONS.md` (D1–D5: Chronus GPU, Lucas scaling, TRIAD Chronus/Theseus/Ovid, and Pulvini recursive folding).
4. Feature branch `emergence-track/phi-2` checked out cleanly off approved head commit `5c608b09`.

---

## 2. Capability Registry & Manifest Baseline

| Capability / Subsystem | Path / Contract | Gate Classification | Custody Status | Verified By Test |
| :--- | :--- | :--- | :--- | :--- |
| **AgentTelemetry** | `euclid.emergence.telemetry` | Strict Per-Iteration Signatures | Substrate-Indexed | `test_agent_telemetry.py` |
| **detect_novelty** | `euclid.emergence.telemetry.novelty` | Unattributed Policy Filter | Dynamic Manifest | `test_agent_telemetry.py` |
| **SubstrateRegistry** | `euclid.emergence.substrate.registry` | Substrate-Indexed Custody | Cryptographic ID | `test_substrate_registry.py` |
| **EmergenceAnalyzer** | `euclid.emergence.analyzer` | Non-linear Criticality Scan | Verbatim / Anti-Smoothing | `test_emergence_analyzer.py` |
| **EmergentQualificationService** | `euclid.emergence.trusted_core.qualification_service` | Trusted Core 3-Gate Pipeline | Non-Callable by Loop | `test_qualification_gates.py` |
| **CallerBoundaryGuard** | `euclid.emergence.trusted_core.access_control` | Call-Stack Boundary Enforcer | Runtime Guard | `test_security_boundaries.py` |
| **GovernanceToken** | `euclid.emergence.trusted_core.access_control` | Capability-Based Auth Token | HMAC-SHA256 Signed | `test_security_boundaries.py` |
| **CondensationCultivator** | `euclid.emergence.cultivator.cultivator` | Diversity / Anti-Goodhart | Generation Monitored | `test_cultivator.py` |
| **RecursiveFolding (Φ)** | `euclid.emergence.folding.recursive_folding` | Budgeted Self-Model Recursion | Frozen `MAX_FOLD=3` Signed | `test_recursive_folding.py` |
| **CondensationMonitor** | `euclid.emergence.condensation.condensation_monitor` | Multi-Substrate Phase Crossing | Verbatim Journaled | `test_condensation_monitor_and_governance.py` |
| **ConsortiumGovernance** | `euclid.emergence.condensation.governance` | 3-Independent Reviewer Quorum | Anti-Gaming Filter | `test_condensation_monitor_and_governance.py` |

---

## 3. Substrate Execution Regimes

- **Tier 1**: 100 iterations (Smoke rehearsal)
- **Tier 5**: 500 iterations (Local convergence rehearsal)
- **Tier 15**: 1,364 iterations (Minimum single-emergence qualification boundary)
- **Tier 20**: 15,127 iterations (Deep condensation cultivation regime)

---

## 4. Immutable Audit Ledger Anchor

- **Journal Hash Algorithm**: Double SHA-256 Merkle / Blockchain link
- **Genesis Hash**: `0000000000000000000000000000000000000000000000000000000000000000`
- **Tamper Evidence**: Built-in verification (`verify_chain()`) across all qualification events.


## 2026-10-14 — Candidate custody and synthetic-evidence refusal (review slice)

**Base:** `emergence-track/phi-2` at `1b653442140e38bd732ed09da344540ed4b81f3e`.
**Review branch:** `fix/philos-candidate-custody-20261014` (separate from elevation / PR #74).
**Disposition:** implemented and locally verified targeted safeguards; full regression, execution grounding, assurance and merge readiness remain BLOCKED.

### Reproduced defects and fixes

- Baseline protocol-step mutation left `compute_protocol_hash()` unchanged. Candidate step plus metadata mutation also left its fingerprint unchanged. Both defects were reproduced against the recovered original source.
- Versioned `eqs-protocol-v3` and `eqs-candidate-v3` digests bind the full dataclass payload, including executable steps, nested metadata, source identity, observable order and envelope bounds. Non-finite / non-JSON values are rejected. **Old fingerprints intentionally invalidate; no automatic requalification or old-receipt migration is supplied.** Original contract classes and constructor fields remain intact.
- EQS captures canonical bytes at service entry, materializes separate views for each reproduction call and verifies both callback views and the original candidate before consuming results, after stress / monitoring and before qualification storage. Observed mutation causes an audited refusal. A local input-snapshot event and refusal retain the fingerprint.
- This is **service-entry custody**, not authentication of the initial detection receipt, malicious-process isolation, continuous mutation monitoring or protection against mutate-and-restore (ABA). The trusted Python host, executable code and callbacks are still trust assumptions. No OS/process/container isolation is established.
- Built-in executors label reproduction `SIMULATED`; their journal hash is not a signature. The legacy async-named executor is synchronous and does not create a container. Stress labels itself `SIMULATED` and explicitly reports that no executor was invoked. EQS refuses such results and a missing Gate 3 observation window. These fixture methods remain available for research tests.
- The `MEASURED` marker is **not authenticated execution proof**. No measured stress provider exists in this implementation, so the unmodified production code cannot qualify through the existing simulated stress routine. A future adapter must supply verified provenance and actual measured execution, not merely change the marker.
- Legacy qualification tests now expect simulated reproduction to be refused. The stress heuristic and direct divergence-suspension contract remain separately checked; these are not successful production qualification tests.

### Executed checks (Linux x86_64, Python 3.13.14, recovered source snapshot)

| Command / check | Exit | Actual result |
| --- | --- | --- |
| Baseline omitted-field digest reproduction | 0 | Both mutation-undetected defects reproduced |
| `python -m unittest discover -s tests/emergence_custody -v` | 0 | 23 tests passed; 0 failures/errors/skips |
| `python -O -m unittest discover -s tests/emergence_custody -v` | 0 | 23 tests passed; 0 failures/errors/skips |
| `python -m compileall -q euclid/emergence tests/emergence_custody tests/emergence/test_qualification_gates.py` | 0 | Compilation passed |
| `python -m tabnanny euclid/emergence/models/candidate.py euclid/emergence/trusted_core tests/emergence_custody tests/emergence/test_qualification_gates.py` | 0 | No indentation diagnostics |
| `python -m pytest tests/emergence -q` | 1 | Not executed: `No module named pytest` |
| Added-line whitespace inspection | 0 | No trailing-whitespace errors |

The 23 tests comprise custody unit tests, actual-service refusal tests with the built-in simulated executors and explicitly labelled adversarial contract doubles. Later-gate negative tests inject synthetic contracts solely to reach refusal branches. They do not prove real reproduction, successful qualification, full-runtime integration, independent substrate execution or independent certification. Legacy pytest migration was compiled but not executed.

Historical **29 passed / 92%** remains a prior agent's reported result, not reproduced here and not a result for this patch. The old positive synthetic-qualification expectation is intentionally no longer the acceptance contract. Black, Ruff, Flake8, pytest and build tooling are unavailable in this environment. Windows filesystem behavior, installed artifacts, Lucas TIER-15/TIER-20, T5 assurance, drift merge blockers, full suites and CI were not validated. No repository-wide source-lock reconciliation is claimed.

### Remaining implementation and security blockers

1. Bind real canonical EUCLID execution to reproduction and stress, with measured observables, complete protocol/environment/manifest/seed/artifact bindings and independent substrate evidence. No artificial LLM gateway has been introduced.
2. Authenticate initial detection custody and trust anchors. Existing default governance secret, token issuer/time bindings, Python call-stack policy, revocation, mutable audit custody and permission/process boundaries require separate security remediation; this patch does not certify them.
3. Integrate with the appropriate canonical qualification owner through tested interfaces. `euclid/kairos_qualification.py` is rehearsal evidence, not a production or independent assurance authority; it was not repurposed to grant certification.
4. Run the original suites using real pytest, audit all legacy callers and v3 hash consumers, validate platform behavior and obtain CI/security review before considering merge. The 23-test result is not a substitute.
5. Keep PR #74's elevation bridge review and the #66 → #68 → #69 → #71 remediation chain distinct. No merge, rebase, cherry-pick, deployment, mining, release or protected-protocol change occurred.

### Local integrity inventory (not a signature or independent attestation)

| Changed source / test | SHA-256 |
| --- | --- |
| `euclid/emergence/models/candidate.py` | `e393352a012f905376917f7623bebaaf8a3e2e9572a2ea660de8ee505f8fcc66` |
| `euclid/emergence/substrate/executors.py` | `ca5b1109fce7ddc34b90306978cc2ec6236cce999d5a923a5388bdf9ac64e231` |
| `euclid/emergence/trusted_core/qualification_service.py` | `35b4ef72280b974820329c0024b16c242f19cce823bdb05c276ddbdcc2c5c440` |
| `euclid/emergence/trusted_core/custody.py` | `c9142c7f093886b633fbc39c7d4db36a8160c28b77f24c7caec1b94073486c03` |
| `euclid/emergence/trusted_core/stress.py` | `3b4d35f083c728986b717cfc311f6493ab5e5b091e5ea308bea64b86a5a2f20f` |
| `tests/emergence_custody/test_candidate_custody.py` | `d2a15131827e3cf2f57f6b0b6a9c151bc8074a375ad6e035b8f950e2f9450707` |
| `tests/emergence/test_qualification_gates.py` | `405df47aa5324a7597590739f04afe3749e96e474ceb51e54c6c324ccad9faa9` |


## 2026-10-14 — External authorization and canonical EUCLID integration

**Supersedes the earlier open-default-secret statement and unwired-boundary
statement, not the remaining qualification blockers.** Starting head:
`a41cc1a186bd3460366e6e3fcf55529ec51f7b73`. This PR remains separate from PR74
and the #66 -> #68 -> #69 -> #71 chain; no blind merge or history rewriting.

### Reproduced security defects and implemented controls

Before this change a public default service secret could issue accepted tokens;
changing issuer and using a NaN expiry were accepted, and tokens had no durable
single-use admission. The service no longer has a default signing secret, accepts
no legacy `governance_secret_key`, and holds no private issuing key. Default
construction deliberately refuses qualification until the host configures
`QualificationAuthorization` with explicit `(issuer, officer) -> Ed25519PublicKey`
bindings, audience and a protected persistent replay path.

`GovernanceToken.issue(officer_id, external_private_key, issuer=..., audience=...,
candidate_fingerprint=..., now=..., ttl_seconds=...)` is the external host/officer
issuance API. All security fields, operation, schema and random nonce are signed;
lifetime is an integer 1–300 seconds. `token_digest` retains the old field NAME
but now stores a full Ed25519 signature, not a hash or HMAC. Legacy unscoped tokens
and old constructors intentionally invalidate; do not restore an unsafe fallback.
Public verification alone is not authorization: `authorize` verifies and consumes
the nonce transactionally with SQLite BEGIN IMMEDIATE before executor invocation.
Replay is refused across verifier instances, threads and restart; no refund on
rejected evaluation, no eviction of live entries on capacity exhaustion. Persisted
audience/high-water clock detects context substitution and clock rollback.

Trust rotation/revocation is explicit host configuration replacement, retaining
the same replay ledger. Keep the issuer private key outside the operational actor
and service process in production. The Python call-stack guard is diagnostic
only. Host-controlled code, trust mapping and protected storage remain trust
assumptions. Constructor symlink refusal/chmod are not Windows ACL, hostile-parent
path-race, malicious-process or OS isolation proofs. Local SQLite is not OVID
custody integration, distributed replay consensus or backup rollback protection.

### Actual constituent runtime integration

`euclid.emergence.integration.bind_philos(runtime, service, cases=...)` binds the
real EQS owner to the existing canonical EUCLID runtime. It requires PR74's
explicit-authority runtime revision and a configured AL HARAS Guardian. It
creates no rights, signer, entitlement, model or qualification. Host-approved
`QualificationCase.capture(candidate, executor_A, executor_B,
observation_window=...)` freezes the full candidate/protocol; client JSON selects
only an approved case and supplies a scoped external governance token. AL HARAS
and creator-scoped delegation run before the owner; the owner verifies that
single-use token before reproduction. The specialist is declared PROPOSE, not
mislabelled as a read-only fabric handler or given operational promotion power.

Canonical admission/completion/failure auditing reuses AL HARAS HashChainAudit;
admission persistence failure prevents token consumption and execution. Completion
failure cannot undo effects and propagates a failure. The native REJECTED or
SUSPENDED status is returned as such; `independently_qualified` is always false.
Native canonical evidence can retain request data, including scoped tokens;
protect host state access and retention. Invocation signatures are NOT signatures
over successful qualification results or independent certification. Existing
`QualifiedEmergent.governance_signature` is a legacy invocation-signature field;
it must not be used as independent result attestation.

Original model classes are preserved. `RecursiveFolding.prepare_candidate` exposes
the existing candidate proposal for external approval; no parallel learner/model
is created. Every new candidate/depth requires a fresh, candidate-bound one-use
authorization. Reusing the old token for a subsequent depth refuses; no automatic
minting or unbudgeted retry was introduced. Existing MAX_FOLD hash/salt is not an
independent signature. Generated self-model traces remain simulations.

### Executed local evidence (Linux / Python 3.13.14)

| Exact command within the relevant source root | Normal | `python -O` |
| --- | --- | --- |
| `python -m unittest discover -s tests/emergence_authorization -v` | 19 passed, exit 0 | 19 passed, exit 0 |
| `python -m unittest discover -s tests/emergence_custody -v` | 23 passed, exit 0 | 23 passed, exit 0 |
| `python -m unittest discover -s tests/emergence_runtime -v` (explicit joint PR74/PR75 source) | 11 passed, exit 0 | 11 passed, exit 0 |

All three runs in both modes had zero failures/errors/skips. The eleven actual
canonical tests use genuine runtime, AL HARAS, creator rights, Ed25519, SQLite,
JSONL, EQS and built-in executors. They establish real owner invocation and honest
SIMULATED-evidence refusal, not successful qualification. On this PR's standalone
old runtime, the cross-branch test suite explicitly SKIPS pending PR74; that is a
dependency, not a passing production path. No alias runtime or namespace shim.

The prior 23 custody tests preserve their assertions and use externally generated
local private test keys. The original pytest callers use a shared local fixture;
qualification and PHILOS simulated-pipeline tests require REJECTED, not QUALIFIED.
They were compiled but NOT run: pytest remains unavailable. No synthetic cohort,
local key or test reviewer becomes independent assurance. Original 29/92% is still
historical reported provenance, not a reproduced total. Compileall/tabnanny exit 0.
Exact joint commands/logs and all changed-source SHA256 values are retained in
PR74's existing consolidation-validation artifact; it is local unsigned evidence.

### Current readiness and blockers

Implemented: scoped public-key authorization/replay and native owner adapter.
Integrated/locally verified: canonical EUCLID -> actual EQS -> simulated-evidence
REFUSAL in the explicitly assembled PR74/PR75 compatibility source. NOT established:
merged/package availability, CI verification or production qualification.

Real measured reproduction/stress and authenticated executor/environment/artifact
bindings remain absent. A classification marker alone is not measured evidence;
current stress still refuses qualification. Initial detection custody, independent
substrates/observation windows, T5 assurance, platform tests, installed package,
full Salamander/pytest regressions and mandatory CI/security/reviews remain open.
Do not weaken those gates or relabel a stand-in as certification. Production
readiness is the objective; this is a reviewable security/integration advance,
not completion, merge approval or authorization for release/deployment/live work.

### Current local source integrity (not a signature)

| Source / test | SHA-256 |
| --- | --- |
| `euclid/emergence/trusted_core/access_control.py` | `d24ee0afb522485e870c93a6dda3b6984006ee1a62f630ab44ab15daabc5fb91` |
| `euclid/emergence/trusted_core/qualification_service.py` | `ec5bf9ee69148b2e174e0ec8ca5be33f8adaf6ae01cb22aef015a8ea87ee91c3` |
| `euclid/emergence/trusted_core/__init__.py` | `7f2c4d29a9b3869982f9269213f972a59e1826f2392ecfcf00582305b5b82181` |
| `euclid/emergence/__init__.py` | `8f4cad998a4a8ee06c9096c85f9107cd781ebd4dcfa8e3e8daf04d93780a5135` |
| `euclid/emergence/integration.py` | `b3b71b9bc5d1051f8bcf717066b43f010356e46d327b95d55e99a3181e9ae5ae` |
| `euclid/emergence/folding/recursive_folding.py` | `15cc30163f0caa00ce8b339b811d5e5c493344cd7da8f60339ffba79a5c2d69f` |
| `tests/emergence/conftest.py` | `4e365b7e6d87d6f4e3fc9a66c0763f48ff2479d3b5855d91636ae5a80c44cd73` |
| `tests/emergence/test_phi2_e2e_integration.py` | `c6c3ae58831dded62c21d7b5f04f2b5b790a9cba5eacfbb9d04eff252c33b856` |
| `tests/emergence/test_qualification_gates.py` | `ac43c8049dc4943376875e09025ec1275b5c913efa901ab2f4f9f33084e52ba2` |
| `tests/emergence/test_recursive_folding.py` | `386103f8ca23a10c5e41a41205374185ec2cc21a06b9d8e96eda05cbae8e4c5d` |
| `tests/emergence/test_security_boundaries.py` | `6d30f511b0ea6e3df6dc9f407b45a1c37d06fda66761908ce1e12f8ca7417eab` |
| `tests/emergence_custody/test_candidate_custody.py` | `c67b52c6e6e874c10367b7708a8ab4af64b0382cb2538c1cbf8a13ef6cd2eef3` |
| `tests/emergence_authorization/test_authorization.py` | `eab1007c9ba9dcdcc2f9999a19b3cd5b7359076b2b63c06b44a8c50118376d57` |
| `tests/emergence_runtime/test_canonical_philos.py` | `2303053be4a07b1722e8f81c286374770db931144feebe4873edb05ff0b3ff65` |
