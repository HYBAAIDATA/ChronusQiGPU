# HYBA Capability Map, Transform Decision Register, and Validation Plan

**Status:** consolidation map and test plan; not a certification or production-readiness claim.  
**Scope:** HYBA platform, AL HARAS/L-HRAS governance, TOE reasoning/evidence, Salamander resilience, Millennium Maths probes, phi-based defensive triage, transform research, and proposed sovereign/alliance/multilateral deployment profiles.

## 1. Executive direction

Maintain **one HYBA platform and one evidence/authority model**. Do not create separate forks for AL HARAS, Five Eyes, NATO, or the United Nations. AL HARAS/L-HRAS supply security governance and authorization boundaries; TOE supplies reasoning/evidence integration; Salamander remains the canonical adaptive-resilience control plane. Millennium Maths is an isolated, bounded mathematical-probe service—not a mission-data processor, identity authority, policy engine, or action authority.

The golden ratio (φ) is a candidate structural parameter for explicitly declared workloads. It is not inherently cryptographic, does not itself establish attack detection, and does not justify replacing Fourier/FFT/QFT everywhere. Keep conventional methods as the reference implementation unless a named workload demonstrates that an alternative is more correct, secure, efficient, or operationally useful.

## 2. Capability map

| Layer | Intended responsibility | Relevant repository entry points | Validation needed |
|---|---|---|---|
| HYBA platform | Shared runtime, package and deployment boundary | `README.md`, `docs/v2/00_INDEX.md`, `packaging/HYBA_PUBLICATION_CATALOG.md` | Install/build matrix, dependency and API compatibility, reproducible packaging |
| Security and authority | Tenant/purpose binding, policy, authorization, audit and operator controls | `docs/al-haras/`, `docs/v2/01_SYSTEM_TRUTH.md` | Negative authorization tests, tenant isolation, audit integrity, policy/version binding |
| Reasoning and evidence | TOE assessment and structured evidence integration | `docs/al-haras/TOE_PLATFORM_INTEGRATION.md` (branch path) | Evidence provenance, uncertainty retention, replay, missing/conflicting evidence |
| Resilience | Canonical Salamander observation/control plane | `docs/al-haras/SALAMANDER_ADAPTIVE_RESILIENCE_INTEGRATION.md` (branch path) | Baseline absence, failure/rollback, post-action verification, human approval |
| Mathematical probes | Bounded Millennium Maths requests, separate from mission assessments | `millennium/millennium_reasoning_service.py`; AL HARAS offering adapter | Input/output bounds, timeouts, origin/token safety, schema validation, no theorem overclaim |
| Defensive triage | Advisory φ-weighted prioritization and review-slot allocation | `recovery/hyba_data/source/hyba_data/hermes/offerings/phi_security_optimizer.py`; `national_security.py` | Determinism, calibration, holdout performance, fairness/workload impact, tenant isolation |
| Transform research | Golden/metallic transforms, chirp-Z acceleration, wavelet/scaling-domain experiments, RTL prototype | Inventory in §3 | Mathematical properties, inverse/reconstruction, numerical stability, complexity, independent baselines |
| Deployment profiles | Environment-specific controls and integration contracts over shared core | Proposed profiles in §5 | Threat model, data-flow review, identity integration, accreditation and acceptance by each operator |

**Architecture rule:** assessment and scoring are not authorization. An anomaly score is not proof of attack; a missing signal is not healthy; a successful handler call is not proof of recovery. Consequential actions must go through the existing authorization/action path.

## 3. Transform decision register

This is a source-based inventory, not a declaration that each item is production-ready. Paths may be in legacy or research areas and should remain labelled accordingly until promoted through the gates in §4.

| Implementation / claim location | What it appears to do | Current interpretation | Required next step |
|---|---|---|---|
| `golden_quantum/golden_fourier.py` | Golden-ratio weighted sum with a Fourier-like complex phase | Hybrid transform candidate; not a universal Fourier replacement | Establish exact definition, domains, inverse conditions, conditioning and reconstruction error |
| `golden_quantum/metallic_fourier.py` | Generalizes weighting to metallic means while retaining a complex Fourier phase | Parameterized hybrid; still uses Fourier phase | Test parameter families and state when they add value over standard DFT/FFT |
| `golden_quantum/golden_czt.py` | Chirp-Z/Bluestein-style route intended to compute the golden transform more efficiently | Algorithmic acceleration candidate for that defined transform | Verify against direct summation, complexity and memory scaling; profile Decimal/numeric costs |
| `golden_quantum/golden_wavelet.py` | φ-related scale/dilation construction with FFT filter-bank implementation | Scaling/wavelet research; itself uses FFT machinery | Verify frame/reconstruction properties, boundary effects and signal classes |
| `kellogg/golden_convolution.py` | Convolution defined for a declared scaling-domain transform | Alternative operation for scaling symmetry, not a drop-in replacement for translation-symmetry convolution | Prove or test the convolution theorem for its stated transform and supported domain |
| `legacy/hardware/rtl/golden_ontology_transform.sv` | Fibonacci-basis RTL described in comments as an FFT-butterfly replacement | Legacy hardware research artifact; comments are not proof of orthogonality, exactness, synthesis quality or equivalence | Derive the matrix/basis properties; verify inverse/conditioning and RTL with independent reference model, formal properties and synthesis reports |
| `legacy/scripts/euclid_tapeout_checklist.py` and related legacy checklist references | Mentions Fibonacci-butterfly transform/tapeout status | Historical claims/checklist, not current acceptance evidence | Reconcile each assertion with source, tests, tool logs and current status |
| `docs/TURING_STRUCTURAL_RESEARCH_GATES.md` | Defines research promotion rules for Pisot-indexed transforms vs cyclic QFT | Governing research boundary: Fourier/QFT remain canonical for cyclic/abelian symmetry unless evidence justifies an alternative | Keep `theorem_proven=false` and hardware `NOT_RUN` until supported by proof or measurements |

### Transform selection rule

Choose the transform from the structure of the workload, not the branding:

- **Cyclic/translation symmetry, conventional spectral analysis, interoperability:** DFT/FFT/QFT remains the baseline.
- **Declared scaling, self-similar, quasicrystal, or φ-structured data:** evaluate golden/metallic/scaling alternatives as candidates.
- **Hardware/RTL:** no performance or exactness claim without reproducible synthesis and timing/area/power evidence, reference equivalence, and formal/property checks appropriate to the claim.
- **Security-sensitive use:** a transform is not a cryptographic primitive unless separately designed and cryptanalytically evaluated for that purpose. Obscurity, unusual bases, or irrational constants do not imply security.

## 4. Transform test and promotion gates

Every candidate must have a named owner, mathematical contract, test corpus, baseline, and evidence receipt.

### Gate T0 — Contract and scope
- Define input domain, shape, normalization, coefficient ordering, precision, boundary rules, expected output, and supported parameter ranges.
- State whether the transform is linear, invertible, orthogonal/unitary, a frame, approximate, or intentionally lossy. Do not use these terms interchangeably.
- State the workload and why its symmetry matches the candidate.

### Gate T1 — Correctness and properties
- Compare against an independent direct reference implementation on small inputs.
- Test impulse, constant, basis vectors, random vectors, sparse signals, adversarial magnitudes, non-power-of-two lengths, empty/singleton cases, and supported edge lengths.
- Check linearity where claimed; inverse/reconstruction; energy preservation where claimed; orthogonality/unitarity by matrix/property tests where claimed; and convolution identities only where mathematically specified.
- Use exact algebraic arithmetic for exact claims; otherwise publish precision and tolerances.

### Gate T2 — Numerical stability
- Measure forward error, inverse error, condition number or a suitable stability proxy, overflow/underflow, cancellation and sensitivity to input perturbations.
- Sweep sizes and parameter ranges. Include high-dynamic-range and near-degenerate cases.
- Separate algorithm error from floating-point/Decimal implementation error.

### Gate T3 — Performance and resource use
- Compare against best-practice baselines such as NumPy/SciPy FFT and direct DFT for small sizes; use equivalent hardware, precision, warm-up, and batching.
- Record runtime distributions, throughput, peak memory, scaling with N, and preprocessing/setup cost.
- For RTL, record toolchain/version, target device, synthesis area, timing closure, power method, resource utilization and reference-model equivalence. If hardware was not run, status is `NOT_RUN`.

### Gate T4 — Security and operational robustness
- Test malformed shapes, extreme values, denial-of-service sized inputs, resource limits, reproducibility, and dependency failures.
- For any defensive application, measure impact on false positives, false negatives, lead time, and analyst workload. Do not equate transform novelty with security gain.
- Ensure logs avoid sensitive payloads and preserve tenant boundaries.

### Gate T5 — Independent reproduction
- Pin source revision, environment, dependencies, command, seed, corpus digest and raw results.
- A second operator should reproduce the reported result from the recorded instructions.
- Publish failures and negative results, not only best runs.

### Gate T6 — Promotion decision
Allowed states: `PROPOSED` → `IMPLEMENTED_UNVERIFIED` → `TESTED_ON_DECLARED_DOMAIN` → `BENCHMARKED` and/or `PROVED_FOR_STATED_PROPERTY` → `APPROVED_FOR_NAMED_USE`.  
Promotion is property- and workload-specific. Passing one gate does not imply passing the next or general superiority.

## 5. Deployment-package map: common core, distinct profiles

No repository search performed for this map established a complete, authorized or accredited Five Eyes, NATO, or UN deployment package. Treat the following as **profile specifications to build and validate**, not existing customer deployments, endorsements, access, or certifications.

| Profile | Purpose and controls to define | Acceptance evidence |
|---|---|---|
| Sovereign / national | Data residency, sovereign key custody, local identity/clearance integration, offline operation, local administration, export-control and retention rules | Threat model, deployment bill of materials, data-flow map, key-management review, independent security assessment |
| Five Eyes interoperability (proposed) | Bilateral/multilateral sharing policy, releasability markings, originator control, national caveats, cross-domain transfer boundaries, audit and revocation | Explicit partner-approved interface contract; simulated policy tests; no assumption that membership grants access or approval |
| NATO interoperability (proposed) | Classification and releasability handling, mission/coalition identity, coalition networks, disconnected operations, interoperability standards, incident reporting | Defined target environment and authority; security accreditation by responsible bodies; interoperability and fail-closed tests |
| UN / multilateral operations (proposed) | Mandate- and mission-scoped access, multinational role separation, privacy/human-rights safeguards, multilingual data handling, retention and audit, field/offline operation | Mission-specific data protection and threat assessments; tested role boundaries; independent review and authorized operational acceptance |
| Critical infrastructure / regulated enterprise | Tenant isolation, evidence retention, incident workflows, continuity and recovery, regulated audit, operator approval | Sector-specific threat model, resilience drills, audit evidence and external review |

### Profile implementation contract

Each profile should be a versioned configuration/policy bundle over the same core, with explicit adapters—not a code fork. At minimum define:
1. Identity and federation adapters; no invented or implicit clearance.
2. Classification, handling, releasability, purpose and retention labels attached to data and evidence.
3. Tenant and mission isolation, including negative cross-boundary tests.
4. Data residency, encryption/key ownership, backup, deletion and audit custody.
5. Offline/air-gapped install, update provenance, rollback and dependency inventory.
6. API/interface schemas, version negotiation, failure behavior and export controls.
7. Human approval and authorized actuation path; default deny when policy or identity is unavailable.
8. Operator-specific test evidence, independent assessment and a documented authorization decision.

Do not use “Five Eyes-ready”, “NATO-certified”, “UN-approved”, “accredited”, or equivalent language without explicit, current evidence from the responsible authority.

## 6. Defensive φ triage evaluation

The current φ triage is a transparent deterministic heuristic. Its current score shape is `severity × exposure × confidence × φ^(-age_units)`; review slots are apportioned with descending `φ^(-rank)` weights and largest-remainder allocation. This may help prioritize analyst attention, but it is not a probability of attack and is not cryptographic protection.

Compare it on the same sanitized, time-separated cases against:
- severity-only;
- severity × exposure;
- current operational/policy baseline;
- a simple age-decay baseline tuned on training data only.

Report precision/recall, false-alarm and miss rates, time-to-triage, lead time, analyst workload, calibration if probabilities are later introduced, confidence intervals, subgroup effects, and performance under missing/stale/contradictory telemetry. Fix definitions before the holdout run; use shadow mode first; never make a consequential action solely from this score.

## 7. Platform and package validation matrix

| Test area | Minimum test evidence | Failure behavior |
|---|---|---|
| Unit/regression | All relevant unit tests, deterministic seeds, no hidden network dependency | Block promotion on unexplained regressions |
| Tenant isolation | Cross-tenant reads/writes, audit lookup, cache and error-path isolation | Deny by default; no data leakage |
| Authorization | Missing, expired, malformed, wrong-scope and revoked credentials/policies | No consequential action |
| Evidence/audit | Digest integrity, tamper detection, replay, clock and retention edge cases | Report integrity failure; never silently mark valid |
| Service boundaries | Timeouts, oversized payloads, redirects, TLS/origin validation, dependency outage | Bounded failure; no credential forwarding to untrusted origin |
| Resilience | Missing telemetry, absent baseline, partial failure, rollback and post-action verification | Unknown/unhealthy is not silently normalized to healthy |
| Packaging | Clean environment install, pinned dependencies, SBOM, provenance/signature verification | Fail release if artifacts cannot be reproduced or verified |
| Deployment | Offline install/update, recovery, restore, configuration drift and operator runbooks | No production claim until target environment is tested |
| Performance | Declared workloads and resource envelopes with repeated runs | Report measured numbers only; unrun is `NOT_RUN` |
| Profile compliance | Each profile’s policy fixtures, data-flow review and authority acceptance | Profile remains `PROPOSED` until signed acceptance evidence exists |

## 8. Evidence receipt and status vocabulary

Each validation receipt should contain: repository and commit SHA; component/profile and version; claim/property tested; test command and environment; dependency/toolchain versions; dataset/corpus identifier and digest; random seed; expected and actual results; pass/fail; raw log/artifact references; reviewer; date; and limitations.

Use these terms consistently:
- **Implemented:** source exists.
- **Test authored:** a test exists; execution is not implied.
- **Test passed:** a recorded run passed at a named revision/environment.
- **Benchmarked:** comparable, reproducible measurements exist.
- **Proven:** a proof establishes a clearly stated property under stated assumptions.
- **Approved/accredited:** the responsible authority has issued documented acceptance.
- **NOT_RUN / UNKNOWN:** no evidence sufficient to claim a result.

## 9. Suggested execution order

1. Freeze the source inventory and label every Fourier-replacement claim by path, owner, status and intended workload.
2. Run existing transform tests and add missing independent-reference/property tests.
3. Execute the transform benchmark suite with pinned environments and publish negative as well as positive results.
4. Execute the φ triage unit tests; then run offline/shadow holdout evaluation against conventional baselines.
5. Run the consolidation integration/security tests: TOE, Salamander, Millennium boundary, tenant isolation and authorization negative cases.
6. Build profile policy fixtures and simulated federation tests; keep institutional profiles proposed until target operators define and accept their controls.
7. Promote only claims whose evidence receipts meet the stated gate. Update `docs/v2/` canonical truth/readiness docs to reflect measured outcomes; keep legacy research clearly marked.

## 10. Canonical references

- [Repository canonical documentation index](docs/v2/00_INDEX.md)
- [Turing structural research gates](docs/TURING_STRUCTURAL_RESEARCH_GATES.md)
- [AL HARAS golden-ratio defensive triage](AL_HARAS_GOLDEN_RATIO_CYBERSECURITY.md)
- [Golden Fourier implementation](golden_quantum/golden_fourier.py)
- [Metallic Fourier implementation](golden_quantum/metallic_fourier.py)
- [Golden CZT implementation](golden_quantum/golden_czt.py)
- [Golden wavelet implementation](golden_quantum/golden_wavelet.py)
- [Legacy golden ontology RTL](legacy/hardware/rtl/golden_ontology_transform.sv)
- [Current readiness position](docs/reviews/SOVEREIGN_READINESS_POSITION_2026-10-12.md)

This map should be updated only when the referenced implementation, tests, measured receipts, or external acceptance evidence actually change.
