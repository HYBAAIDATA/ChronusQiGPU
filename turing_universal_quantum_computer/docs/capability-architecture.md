# Capability architecture and verified dependency map

## Decision and scope

TURING delivers computational intelligence capability. AL HARAS supplies the
security responsibility, Salamander bounded self-healing/optimisation, and
EUCLID intelligence/routing/delegation in the capability-delivery architecture.
They are dependencies of the governed delivery composition, not unrelated
optional products to bolt on. The platform provisions and governs access;
customers need not assemble its internal packages. Entitlements and contractual
limits are separate from package layout. No pricing or service promises are added.

The mathematical library remains independently usable and correct without
credentials or an intelligence service. Keep `hyba-turing-vqc`, `VQCPipeline`, the
typed facade, finite-domain contracts, exact result classes and verification
intact. A local library call is not an authenticated enterprise service operation.

## Actual local call graph

```text
Local mathematical package (unchanged)
  TuringPipeline -> native_adapter -> canonical VQCPipeline

Governed delivery composition
  ProductionOrganism(tenant, guardian, explicit token provider when configured)
    -> CompositionRoot -> ONE shared THESEUS/OVID fabric
    -> SharedALHaras -> real AL HARAS decisions
    -> SharedSalamander -> legacy diagnosis/repair proposals (not verified actuation)
    -> SharedTuring -> canonical VQCPipeline -> certificate / custody / replay
    -> SharedEuclid -> EuclidRuntime
       route_specialist / dispatch_specialist
         -> bound-tenant check -> AL HARAS -> typed/bound verdict validation
         -> creator-scoped delegation -> TuringQuantumOrgan(pipeline=SharedTuring)
         -> same canonical computation / verification / custody / replay
       heal_organ
         -> Salamander canonical authorised control plane -> AL HARAS
         -> bounded registered requalification -> independent redispatch verifier
         [closed if credential provider absent; every action still needs approval]
```

EUCLID supplies its existing capability selection and delegation; TURING retains
Program semantics and mathematical execution. This is the actual supported
intelligence relationship in this service composition. It does not add an
invented reverse intelligence client to the typed mathematical facade, duplicate
EUCLID cognition, or make exact arithmetic depend on a routing service.

## Verified responsibility/dependency inventory

| Consumer / owner | Actual responsibility and boundary | Classification / evidence status |
| --- | --- | --- |
| Typed TURING facade/native adapter | Contracts, exact estimates, finite optimization and jobs | Mathematical package runtime; unchanged, no new hard platform dependency |
| ProductionOrganism/SystemRelations | Composes existing owners and one custody lifecycle; binds service tenant and optional out-of-band provider | Local runtime composition; actual shared-root/installed-consumer tests |
| EUCLID -> AL HARAS | GuardianRequest + token -> typed tenant/operation/payload-bound verdict; delegation remains separate | Local runtime dependency; real denial, expiry, replay, malformed-response and cross-tenant tests |
| EUCLID -> TURING in ProductionOrganism | Existing intelligence routing/delegation invokes specialist with SharedTuring injected | Local runtime dependency; canonical result/certificate/replay, routing and concurrency tests |
| Standalone TuringQuantumOrgan without injection | Existing backend admission and direct execution | Retained compatibility surface, NOT equivalent to the governed shared-root certificate/custody path |
| EUCLID -> Salamander control plane | Registered bounded requalification, authenticated action, named postcondition verifier | Real canonical constructor/provider tests and installed-root recovery test; absent provider remains closed |
| SharedSalamander -> Intelligence.salamander | Legacy diagnosis/proposal with actual success/failure custody | Existing local surface; proposal is never promoted to applied recovery merely because it was recorded |
| SharedTuring -> VQCPipeline | Canonical validation/certificate/custody/readback/replay | Existing engine, serialized shared-run state; real tamper/restart and bounded-concurrency evidence |
| Remote security/intelligence/recovery service endpoints | Transport authentication, versioned wire schemas and deployment deadlines | Not introduced or qualified. Local imports do not establish a remote API |
| Additional typed TURING-to-EUCLID intelligence consumption | Would require a specific consumed capability and validated result semantics | Proposed extension only; not needed to pretend the existing routing composition is a new cognition algorithm |

`DEFAULT_PEERS` is a sharing/lineage graph, not an authorization policy.
Historical redirects in `july_compat.py`, the listener hook in
`turing_core/ten_thousand.py`, and proposal-only
`euclid/organ_adapters/vqc_intelligence.py` do not prove that unrelated capability
integrations are active. Candidate ranking is not the finite-domain VQE contract.

## Package/deployment boundaries

- TURING retains only its existing NumPy, SymPy and Kellogg runtime declarations.
  Platform qualification dependencies are separately hash-resolved; they are not
  additions to the mathematical wheel.
- The existing `hyba-pythia-mining` platform distribution owns the inspected local
  production composition, EUCLID, Salamander and AL HARAS. It declares TURING and
  Kellogg as dependencies. Its duplicate Kellogg package declaration was removed
  after actual wheel inspection found 38 overlapping files. Qualification rejects
  overlap before independently installing this three-wheel distribution set.
- Source integration tests and installed consumers validate this selected local
  composition. Do not additionally co-install overlapping standalone owner wheels
  and assume a supported deployment. Separate-service deployment remains an
  owner decision with its own authentication/version/lifecycle qualification.
- Descriptors at `packaging/euclid-engine` and `packaging/salamander` declare their
  independent 1.0.0 distributions; EUCLID's runtime version is 17.0.0. Matching
  version labels are not protocol compatibility. These directories mark legacy
  documentation deprecated; declarations are not evidence of registry publication.

## Failure, ownership and operational limits

A production root binds its explicit custody tenant. A valid token for another
customer cannot admit work into this root. Healing uses that tenant, not the
creator's delegation identity. Standalone EUCLID callers that do not bind a tenant
retain the historical creator fallback; that is not an enterprise isolation claim.

Credential provisioning is explicit: without a provider the actuation plane is
closed. With one, constructor readiness means the canonical authority is bound,
not that future tokens or repairs are approved. Every action still goes through
AL HARAS and postcondition verification. Service operators own credentials,
policy, retention, supervision and deployment approval.

SharedTuring serializes its run/replay state and SharedEuclid its dispatch/evidence
cursor to prevent cross-run certificate/custody mixing in the tested local use.
This is bounded concurrency evidence, not universal race freedom or a hard timeout
contract. Synchronous dependency calls expose no general forced cancellation.
No automatic retry, fallback authority or fabricated healing is introduced.

See [contracts](dependency-contracts.md), [security boundaries](security-boundaries.md),
[host integration](capability-integration.md) and the existing
[qualification ledger](../TURING-qualification.md). No frontend, commercial rule,
engine replacement, merge, tag or publication is part of this change.
