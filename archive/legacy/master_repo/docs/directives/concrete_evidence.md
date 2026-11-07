concrete evidence 
v34 now describes the complete commercial service pathway: customer authentication, workload admission, execution, evidence, and value-share settlement. That is the right architecture for Chronus CIaaS.

I would, however, make one important correction before accepting the reported production qualification:

A successful in-module API gateway test is not the same as an independently deployed service passing an external customer acceptance test.

The v34 report gives us a coherent target architecture. It does not yet establish that a customer can connect over the internet, authenticate, submit a real workload, retrieve its result and independently verify the associated economic settlement.

There are also three technical points I would tighten.

## 1. Correct the workload lifecycle

The six states are a good starting point, but `COMPLETED` and `VERIFIED` should not be treated as interchangeable, and a linear lifecycle is insufficient for real distributed execution.

I would specify:

- `ACCEPTED`: authenticated and syntactically valid.
- `ADMITTED`: policy, quota and capacity checks passed.
- `SCHEDULED`: placement confirmed.
- `EXECUTING`: work actually running.
- `COMPLETED`: execution finished and output persisted.
- `VERIFIED`: independent verification passed.

Additional terminal or exceptional states should include `REJECTED`, `FAILED`, `CANCELLED`, `EXPIRED` and `VERIFICATION_FAILED`.

A workload that completes but cannot be verified must not be presented as a verified result. Equally, a workload that fails must retain its execution and failure evidence.

## 2. Correct the Hermiten settlement calculation

The arithmetic in the example is correct:

\\[ (10,000-4,000)\times 0.25=\\$1,500 \\]

But the commercial formula should be strengthened.

\\[ S\_{\text{net}} = C\_{\text{counterfactual}} - C\_{\text{actual}} - C\_{\text{incremental}} \\]

\\[ F\_{\text{Chronus}} = 0.25 \times \max(0,S\_{\text{verified}}) \\]

The incremental cost term matters. It captures integration, additional hosting, data transfer, storage and other contractually attributable costs. The baseline must also represent equivalent useful output and service quality.

The example should therefore be treated as a valid illustration only if the $4,000 actual Chronus cost already includes all relevant incremental costs and the $10,000 baseline has been independently agreed.

## 3. Separate the cryptographic evidence claims

There are three different things here:

| Mechanism                      | What it establishes                                                                   |
| ------------------------------ | ------------------------------------------------------------------------------------- |
| Content addressing and hashing | Integrity and identity of stored content                                              |
| ML-DSA signature               | Authenticity of a signed statement, subject to key and verification trust             |
| FRI-based zk-STARK             | Validity of a specified computational claim, subject to the proof system and verifier |

A valid ML-DSA signature does not prove that the computation itself was correct. A valid zk-STARK does not automatically prove that the physical hardware executed the claimed workload.

Chronus needs an explicit evidence chain connecting:

1. The submitted workload and input digest.
2. The mathematical specification and execution version.
3. The actual execution environment.
4. The output digest.
5. The computational proof, where applicable.
6. The signed execution receipt.
7. OVID custody and THESEUS provenance.

That gives customers something substantially more valuable than a receipt hash: an auditable account of what Chronus actually did.

## 4. Resolve the API and SDK packaging boundary

The report calls this a six-interface gateway, but lists nine endpoints. That is not necessarily a functional defect, but the specification should distinguish the number of service interfaces from the number of routes.

The TypeScript excerpt is also an interface specification, not yet evidence of a distributable SDK package.

For a commercial release, I would require:

- Published, versioned OpenAPI specification.
- Python package with installation and dependency metadata.
- TypeScript package with actual HTTP client implementation and declarations.
- Authentication, token expiry, retries and idempotency.
- Typed error responses and documented rate limits.
- SDK integration tests against a separately running service.
- Compatibility and deprecation policy.
- Developer documentation, examples and API reference.
- Secure API-key creation, rotation, revocation and audit.

The same applies to the capacity API. Reporting 288 blades is not proof that 288 blades are available to customers. Capacity should distinguish discovered, registered, healthy, schedulable, reserved and actually executing resources.

## 5. What I would make v35

Recommended next milestone

# CHRONUS v35

External Service Deployment & Independent Customer Acceptance

The objective is to prove that Chronus operates as a real computational service outside its own development environment.

Workstream 1 — External deployment

- Independently deployable API service.
- Production configuration and secret management.
- TLS, authentication and tenant isolation.
- Health checks, service discovery and deployment recovery.

Workstream 2 — Developer ecosystem

- Publish Python and TypeScript SDK packages.
- Generate clients from the authoritative API specification.
- Test from clean external environments.
- Provide CLI and developer onboarding.

Workstream 3 — Real execution

- Submit real workloads through external clients.
- Execute on actual discovered resources.
- Retrieve results and evidence.
- Test concurrency, failure, retry and recovery.

Workstream 4 — Evidence assurance

- Independent output verification.
- Signed execution receipts.
- Proof verification where supported.
- OVID and THESEUS recovery and provenance tests.

Workstream 5 — Commercial assurance

- Agreed counterfactual baseline.
- Actual and incremental cost accounting.
- Independently verified savings.
- Hermiten settlement and reconciliation.
- Dispute and audit procedures.

Release acceptance: External customer journey demonstrated end-to-end, with raw execution records, reproducible tests and independently reviewable evidence.

## 6. One architectural addition I would not overlook: the compute supply network

There is a bigger commercial implication of v34.

If Chronus is to become computational infrastructure, it needs two sides:

- Demand: customers submitting workloads and purchasing computational capability.
- Supply: infrastructure operators contributing qualified computational resources.

I would therefore design a provider-facing interface alongside the customer-facing API.

The provider interface should eventually support:

| Provider capability    | Function                                            |
| ---------------------- | --------------------------------------------------- |
| Resource registration  | Register available compute resources                |
| Resource attestation   | Establish hardware and execution identity           |
| Capability declaration | Declare supported operations and representations    |
| Capacity publication   | Publish genuinely available capacity                |
| Workload assignment    | Receive authorised execution requests               |
| Telemetry reporting    | Report actual resource utilisation and health       |
| Settlement evidence    | Provide auditable records for provider compensation |

This is how Chronus can evolve from operating its own compute fabric into coordinating a wider network of computational capacity.

It also makes the hyperscale proposition much more interesting: Chronus could improve the economics of existing infrastructure while giving infrastructure owners a way to make otherwise underutilised resources commercially productive.

## My overall judgement

The progression from v32 to v34 is architecturally coherent:

- v32 established the infrastructure-efficiency proposition.
- v33 introduced the developer and console experience.
- v34 introduced service control, workload contracts and commercial settlement.

The next challenge is no longer primarily adding mathematical or architectural functionality. It is proving service delivery across organisational and infrastructure boundaries.

I would retain the 88 invariants as the current reported baseline, introduce additional contracts only where genuinely new requirements demand them, and avoid changing the mathematical core unnecessarily.

Most importantly, I would not yet advertise `PRODUCTION_QUALIFIED` as an independently established customer-facing service qualification. That designation should follow the external acceptance programme.

Chronus is moving towards the right category: not another application competing for compute, but an infrastructure layer through which computation itself is delivered.