# Chronus & AL HARAS — CISO Security, Sovereignty & Compliance Brief

**Document posture:** evidence-gated working brief; not a certification, audit opinion, or production sign-off
**Review date:** 17 November 2026
**Owner:** HYBA Data / HYBA Security — owner assignment required for each claim below
**Current release posture:** Chronus is **not release-qualified**. See the [claim audit](claim-audit.md), [release decision](../RELEASE_DECISION_MCKINSEY_TECH.md), and [current status](../STATUS.md).

## Executive decision

This brief may describe proposed controls and implementation surfaces. It may not assert that Chronus or AL HARAS prevents exfiltration, guarantees idempotency, compensates irreversible actions, proves deletion by a regulatory deadline, satisfies a framework, or is production-qualified until the corresponding claim reaches the required maturity level and has a retained evidence artifact.

The governing rule is simple: a claim may be stated only at the lower of its evidence level and the level required by the claim. **“Guarantee” is reserved for an attested, scoped control at L5.** Negative, partial, stale, and uncovered results remain in the evidence record.

Mining smoke testing and the capacity addendum are retained as pinned, separate work products. They are not used here as evidence for security, compliance, customer deployment, or production qualification.

## 1. Claim-maturity policy

| Level | Meaning | Permitted wording |
| :--- | :--- | :--- |
| **L0 — ASSERTED** | Prose only; no retained artifact | “intended to” |
| **L1 — DESIGNED** | Schema, policy, or configuration is committed | “designed to” |
| **L2 — BUILT** | Deployed in staging and exercisable | “implemented” |
| **L3 — TESTED** | Executed with N recorded, including pass and fail results | “verified across N=…” |
| **L4 — OPERATED** | Live operating window with observed metrics for at least 30 days | “operated ≥Nd, observed …” |
| **L5 — ATTESTED** | Dated, scoped, independent third-party attestation | “attested by <auditor>” |

Rules:

- `report_level(C) = min(evidence_level(C), required_level(C))`.
- “Guarantee,” “prevents,” “compliant,” “certified,” “audited,” and “production-qualified” are not inferred from source presence, test counts, framework mapping, or a green UI state.
- Evidence past its expiry demotes the claim by one level automatically.
- A failed or partial vector is published beside passes; it is never dropped from the register.
- Every row below has an intentionally empty evidence field. The blank is a gap, not proof of absence or proof of the claim.

## 2. Claim-maturity register

The table below captures the report’s prior load-bearing claims and the four objection areas. “Current level” is the highest level this report is permitted to use as written today; it does not award a release or compliance status.

| Claim ID | Claim or control as previously stated | Control / scope | Current level | Wording allowed now | Evidence artifact URI / attestation | Owner | Test date / expiry | Verifier | Known holes |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| CM-001 | “Chronus eliminates bulk data transit entirely”; data is never copied or unencrypted outside the customer boundary | Data movement, storage, memory, connectors, logs, and subprocessors | L0 | Intended to reduce bulk data movement in supported designs |  |  |  |  | No data-flow proof; no deployment-specific connector inventory; no memory/egress test |
| CM-002 | “Zero-Copy Native Pointer Architecture” protects customer data | Pointer/handle design and actual execution path | L1 | Designed to use content-addressed handles and in-place access where implemented |  |  |  |  | Pointer naming is not proof of zero-copy behavior or absence of replication |
| CM-003 | “Air-gapped capable” and “customer-custodied PKCS#11 HSM” | Deployment profile and external key custody | L0 | Intended to support deployment profiles that may provide these controls |  |  |  |  | External provider operation and customer-held custody are not established; local fallback remains a known boundary |
| CM-004 | TLS 1.3 and ML-KEM protect control-plane descriptors | Network path, algorithm configuration, certificate and key lifecycle | L1 | Designed to protect configured control-plane traffic |  |  |  |  | No exact deployment configuration, interoperability run, or cryptographic assessment |
| CM-005 | Workload state is immutably folded into Merkle-anchored OVID receipts | Receipt construction, canonicalization, storage, and verification | L1 | Designed to emit versioned, signed execution receipts |  |  |  |  | Immutability, anchoring, and end-to-end execution coverage are not independently evidenced |
| CM-006 | Mathematical subspace projection enforces strict hardware/software tenant isolation | Tenant boundary, authorization, memory, and side-channel scope | L0 | Intended to support tenant separation |  |  |  |  | No isolation test suite, hardware boundary evidence, or side-channel assessment |
| CM-007 | 94 invariants and 8 release gates are enforced on every build | CI policy, exact commit, protected branch, and release workflow | L1 | Designed to evaluate declared invariants and gates in CI |  |  |  |  | Exact-current hosted CI and protected-release evidence remain unavailable |
| CM-008 | Purity gates ban floating-point drift, heuristics, and “simulation theatre” tokens | Static checks and mathematical-path scope | L2 | Implemented checks exist for the declared source scope |  |  |  |  | Scope and current run artifact must be attached; this is not a security or compliance outcome |
| CM-009 | Operators cannot inspect raw customer payloads; zero-knowledge verification exposes only receipts | API behavior, authorization, logging, and response contents | L1 | Designed to limit verification responses to receipt material |  |  |  |  | No adversarial disclosure test, authorization matrix, or deployment evidence |
| CM-010 | Ed25519 and ML-DSA-65 protect manifests and receipts | Signing, verification, algorithm semantics, key custody | L2 | Implemented signing/verification interfaces are present |  |  |  |  | Interface presence is not FIPS validation, custody evidence, interoperability, or attestation |
| CM-011 | Reproducible builds are verified against RFC 8785 manifests | Build inputs, canonicalization, artifact comparison, provenance | L1 | Designed to bind declared artifacts to canonical manifests |  |  |  |  | No retained exact-commit reproducibility packet or independent verification |
| CM-012 | The system has a minimal dependency footprint and no black-box C binaries | Dependency inventory and execution path | L0 | Intended to minimize opaque dependencies in selected mathematical paths |  |  |  |  | Scope is unbounded; this does not establish supply-chain security |
| CM-013 | RBAC roles and short-lived RS256/Ed25519 JWTs provide secure user management | Identity, authorization, token lifetime, revocation, and audit | L2 | Implemented role/token surfaces exist where exercised |  |  |  |  | No complete authorization matrix, abuse test, deployment configuration, or security assessment |
| CM-014 | Mutual TLS, PKCS#11 token binding, and continuous session nonces provide zero-trust identity | Service identity and session controls | L0 | Intended to support stronger service identity where configured |  |  |  |  | No exact deployment proof; PKCS#11 custody and mTLS coverage are open |
| CM-015 | Rate-limited REST APIs and strict Pydantic v2 schemas protect external interfaces | API gateway, limits, validation, and failure handling | L2 | Implemented interface controls exist in the declared code path |  |  |  |  | No route-by-route limit test, saturation evidence, or public abuse assessment |
| CM-016 | Dual-signature quorum is required for tenant provisioning and quota expansion | Administrative authorization and durable audit | L2 | Implemented administrative controls are present where exercised |  |  |  |  | No complete route coverage, bypass test, or operator evidence |
| CM-017 | Every workload emits an immutable, non-repudiable ML-DSA-65 receipt | Receipt coverage, signature verification, and durable storage | L2 | Implemented receipt surfaces exist; receipt coverage remains to be tested |  |  |  |  | “Every,” “immutable,” and “non-repudiable” exceed current evidence |
| CM-018 | The NCSC 1–14 matrix is “COMPLIANT” or “EXCEEDS” | Framework conformity assessment | L0 | Frameworks are reference criteria for a future assessment |  |  |  |  | No independent assessment, scope statement, control mapping evidence, or attestation |
| CM-019 | Cellular sheaf cohomology isolates injected prompts or corrupted state | Detection, isolation, and recovery implementation | L0 | Intended research/design concept; not an established security control |  |  |  |  | No executable control evidence, vector suite, or operational boundary |
| CM-020 | Clean operation has 0.0% cross-blade drift and an H¹ value of 1.4142 for an attack | Metric definition, workload, sampling, and comparator | L0 | No quantitative outcome may be stated yet |  |  |  |  | No source, measurement protocol, N, confidence, or failure results |
| CM-021 | Affected tools are isolated in 38 nanoseconds before downstream output | Detection latency and output gating | L0 | No timing claim may be stated yet |  |  |  |  | No device, workload, percentile, clock source, or adversarial benchmark |
| CM-022 | DSW monopole logic self-heals memory/state faults | Fault detection, repair, and recovery semantics | L0 | Intended recovery concept only |  |  |  |  | No executable implementation or fault-injection evidence |
| CM-023 | An instanton cobordism restores state in one clock cycle without discarding caches | Recovery duration and state preservation | L0 | No recovery guarantee may be stated |  |  |  |  | No fault model, measurement, recovery trace, or retained artifact |
| CM-024 | FRI zk-STARK proofs validate execution traces without disclosure | Proof system, verifier, trace coverage, and privacy boundary | L0 | Intended to explore proof-backed verification |  |  |  |  | No current proof artifact, verifier result, soundness scope, or disclosure test |
| CM-025 | The proof path protects model weights, enterprise data, and tenant IP | Confidentiality property of the complete system | L0 | Intended to reduce disclosure in a defined proof design |  |  |  |  | No end-to-end data-flow, side-channel, or exfiltration evidence |
| CM-026 | Customer keys remain in certified FIPS 140-2 Level 3/4 hardware | External custody and certification scope | L0 | Intended only for a deployment with verified customer custody |  |  |  |  | No provider operation, certificate scope, customer evidence, or key-path test |
| CM-027 | The platform and AL HARAS OS have been “audited and certified” | External audit/certification claim | L0 | No audit or certification claim |  |  |  |  | No dated assessor, scope, report, or certificate; repository status says not qualified |
| CM-028 | “0” banned patterns proves a secure mathematical path | Static result and security conclusion | L3 | Verified across N=… declared static checks, if the exact run artifact is attached |  |  |  |  | A static check does not prove security, compliance, or absence of all unsafe behavior |
| CM-029 | `PRODUCTION_QUALIFIED` across 8 gates and 94 invariants | Production admission decision | L0 | Not release-qualified; admission remains evidence-gated |  |  |  |  | Superseded by current status and release decision; exact CI/attestation/device evidence is open |
| CM-030 | Zero-auth receipt verification exposes zero raw payload | Public verification endpoint and response contract | L1 | Designed to verify a receipt without requiring raw payload access |  |  |  |  | No route-level privacy test, deployment evidence, or abuse analysis |
| CM-101 | “Prevents exfiltration” through injection filtering | C1–C6: least capability, default-deny egress, canaries, DLP, render isolation, egress manifest | L1 | Designed to reduce and observe exfiltration; at L2, “implemented” only for exercised controls |  |  |  |  | Detection is probabilistic; residual vector classes remain open |
| CM-102 | “Idempotency key required” implies enforced deduplication | M1–M5: intent-before-dispatch, durable unique constraint, memoized result, TTL, reconciler path | L1 | Designed for at-most-once dispatch via durable deduplication |  |  |  |  | Need DDL proof, K=20 replay, kill/restart test, TTL comparison, and bypass proof |
| CM-103 | “Compensating action” handles irreversible actions | R1–R6: intent, authoritative read-back, reconciler, drift state, scoped compensation, close blocking | L1 | Designed to reconcile observed state to source of truth within a stated SLA |  |  |  |  | Read-back coverage is unknown; uncovered tools remain unreconciled-by-design |
| CM-104 | “Provable deletion ≤30d” | D1–D6: scope, crypto-shred/delete, probe, backup schedule, pseudonymized ledger, subprocessors | L0 | No universal deadline claim; state primary, backup, ledger, and subprocessor clocks separately |  |  |  |  | Legal hold, sector floors, backups, replicas, logs, and subprocessor clocks are unresolved |
| CM-105 | Mining smoke gate blocks every release and OTA ring promotion | S1–S8: ingest, schema, freshness, calibration, edge safety, watchdog, rollback, telemetry gaps | L1 | Pinned gate design retained separately from this brief |  |  |  |  | No claim of pass or deployment qualification is made here; attach results to release records |
| CM-106 | Capacity addendum establishes the onboarding ceiling | A1–A7: latency, tenant budget, fabric growth, staffing, concurrency/DR, cost, stop-onboard threshold | L1 | Pinned capacity work product retained separately; no capacity or SLA claim here |  |  |  |  | A4 reviewer staffing and the stop-onboard trigger remain unsigned |

## 3. Injection filtering and exfiltration boundary

Filtering is detection, not a containment guarantee. The intended layered control is:

- least capability for untrusted contexts;
- default-deny, per-session egress with an allowlist and logs;
- canary tokens in the corpus;
- output DLP scanning for secret patterns;
- render isolation with image beacons, prefetch, and link expansion disabled;
- a per-session egress manifest written to the ledger.

Before this area can be described at L3, the register requires a red-team suite with at least 25 named vectors and pass/partial/fail results, canary trigger rates over M staging runs, a default-deny log sample, configuration proof for render isolation, and an explicit residual-risk statement. At L2 the only permitted security wording is “reduces and observes.”

## 4. Durable deduplication and irreversible actions

Idempotency is an enforcement property, not a required request field. A qualifying implementation must commit intent before dispatch, enforce `UNIQUE(tool_id, tenant, idempotency_key)` in durable storage, memoize outcomes, retain keys for the full retry horizon, and route intent-without-outcome cases to reconciliation.

Irreversible actions are not “compensated” unless the operation is genuinely reversible. The control objective is reconciliation: record expected post-state before dispatch, read back from the authoritative source, compare on schedule and on demand, expose drift as `UNRECONCILED`, assign an owner, and block session close after the stated SLA.

## 5. Deletion and regulatory deadlines

Deletion is tracked by data class and surface: primary store, embedding index, summaries and lineage, caches, snapshots/backups, replicas, logs/ledger, and subprocessors. The register requires a signed scope list, deletion or crypto-shred mechanism, post-deletion probe, backup expiry schedule, ledger pseudonymization map, and the DPA-derived subprocessor list before an L3 deletion statement.

L4 requires legal review of statutory holds, sector retention floors, jurisdictional regulator clocks, owners, evidence types, and counsel sign-off. Until then, no universal “provable deletion ≤30d” statement is permitted.

## 6. Framework mapping — not a conformity assessment

The NCSC Cloud Security Principles, NIST SP 800-53, FedRAMP High, ISO/IEC 27001, and FIPS references are assessment criteria only. The previous `COMPLIANT` and `EXCEEDS` labels are withdrawn from this brief. A future matrix must bind each principle to a control ID, deployment scope, evidence artifact, test date, expiry, owner, and independent verifier. Source implementation or a framework cross-reference does not award conformity.

## 7. Pinned work products retained outside this brief

### Mining smoke testing

The S1–S8 gate remains pinned for execution before every release and after every OTA ring promotion. A failed sensor-continuity, schema, freshness, calibration, safety-envelope, watchdog, rollback, or telemetry-gap check blocks the ring. Smoke results belong on the release record, not in this security claim register.

### Capacity addendum

The A1–A7 addendum remains a separate versioned work product covering measured p95/p99 latency, tenant token budgets, fabric and index growth, projection cost, reviewer staffing against LOW 72h / HIGH 8h targets, concurrency and DR headroom, cost per 1,000 inferences, and the stop-onboard threshold. It does not establish an SLA until reviewer capacity is staffed and signed.

## 8. Explicitly unproven

- No vector suite is exhaustive; exfiltration residual classes remain open at every level.
- Reviewer capacity is unstaffed until A4 is signed; the HIGH/8h target is aspirational.
- Reconciliation depends on an authoritative read-back adapter; log-only tools remain unreconciled-by-design.
- Legal review is an external dependency and blocks L4 regardless of engineering quality.
- No row in this register is a certification, customer deployment, physical-device result, or production admission.
