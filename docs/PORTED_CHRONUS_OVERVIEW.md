# CHRONUS V2

**HYBA Software Limited | Software-defined computational execution fabric**

Chronus is HYBA's heterogeneous execution plane and virtual iGPU. Its role is to execute admitted workloads under explicit resource, precision, security, provenance and qualification contracts. Chronus is **not** TURING: TURING owns virtual quantum-computation semantics; Chronus may serve as an execution substrate. EUCLID orchestrates intelligence, PYTHIA retains final mining search authority, AL HARAS owns security policy, OVID owns transformation contracts, and THESEUS owns durable custody.

## What Chronus solves

Chronus is intended to provide a portable execution contract across CPU reference execution, optional host accelerators and distributed execution; route workloads without misrepresenting the device that executed them; support verifiable execution and signed result receipts; enforce resource limits, tenant boundaries and evidence-based readiness; and provide an auditable foundation for enterprise and scientific workloads.

## Expected impact

Potential impact includes lower integration costs across heterogeneous execution environments, better workload portability, inspectable execution provenance, and more efficient operation on admitted workloads. **Savings, throughput, scaling, accelerator equivalence, and production readiness require measured workload-specific evidence.** No measured superiority is asserted here.

## Current repository baseline

The repository now contains an initial executable security and qualification implementation in `src/chronus/`, tests in `tests/`, and a CI workflow. The supplied wider Chronus V2 system remains to be integrated; this initial foundation is not production qualification. The documented qualification, security, receipt and custody contracts are in [the implementation specification](docs/CHRONUS_V2_IMPLEMENTATION_CONTRACT.md). The [evidence register](docs/QUALIFICATION_AND_CLAIMS.md) distinguishes designed, implemented and measured status.

## Product boundaries

- **Chronus:** execution and scheduling, backend admission, route attestation, virtual iGPU interface.
- **TURING:** independent virtual quantum computer, state/operator semantics, quantum measurements and certificates.
- **Kellogg:** tensor and exact-field substrate.
- **EUCLID:** cognition and orchestration.
- **PYTHIA:** mining plan, nonce coverage, SHA-256d and share submission authority.
- **AL HARAS:** authentication, authorization, security policy.
- **OVID:** exactness, transformation and equivalence contracts.
- **THESEUS:** custody, provenance, recovery and replay.
- **Salamander:** bounded self-healing and optimization authority. The canonical package (`hyba-salamander-self-healing`, from `hybadatadevops1/HYBAEnterprise`) is proprietary and not vendored here; `chronus.integration.salamander_theseus` drives THESEUS repair through it under AL HARAS authorisation when it is installed. THESEUS Reed-Solomon parity repair runs inline by default. Status per capability: `docs/SELF_HEALING.md`.

## Engineering priorities

1. Extend the committed initial source tree and tests to the complete Chronus execution fabric.
2. Replace hardcoded qualification claims with executable, fail-closed gates.
3. Validate canonical serialization, signing and receipt-chain verification.
4. Implement and test explicit key-provider selection and durable custody.
5. Run independently reproducible qualification, security and execution benchmarks.
6. Publish measured claims only with environment, revision, command and retained results.

**Status:** Initial security and qualification implementation committed. Test execution and production qualification **Unavailable** until CI results are verified.
