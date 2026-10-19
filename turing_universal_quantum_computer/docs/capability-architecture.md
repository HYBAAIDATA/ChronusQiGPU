# Capability architecture and verified dependency map

## Decision and scope

TURING delivers computational intelligence capability. AL HARAS is its intended
security dependency, Salamander its self-healing/optimisation dependency, and
EUCLID its intelligence dependency at the capability-delivery boundary. These
are architectural responsibilities, not optional feature labels or a claim that
all runtime wiring is complete. The platform provisions and governs access;
customers need not assemble the internal packages. Customer entitlements and
contractual limits are separate from implementation details. No new pricing,
service guarantees or external-device requirements follow from this decision.

Keep the existing `hyba-turing-vqc` identity, mathematical substrate,
`VQCPipeline`, typed facade, finite-domain contracts and canonical verification.
A local mathematical library operation is not automatically an authorised
enterprise service operation. Conversely, validity of a mathematical result is
not contingent on an entitlement or an intelligence service being available.

## Evidence scope

Inspected PR #96 at `356ab419dae197f407989da82feaa2f149da08e7` and matched the
relevant local source files to remote content. The accompanying narrow change
adapts EUCLID's existing `(tenant, actor)` token provider to Salamander's existing
`ActionRequest` provider; it does not introduce a new security authority.
Repository paths below are relative to the monorepo root. Documentation and
class names are intent until an actual call path and evidence support them.

## Actual call graph

```text
Local mathematical package (no enterprise boundary implied)
  TuringPipeline -> native_adapter -> canonical VQCPipeline

Enterprise composition (in-process, not a verified remote service protocol)
  ProductionOrganism -> CompositionRoot -> shared THESEUS/OVID custody
    -> ProductionSystemRelations
       -> SharedALHaras -> ALHaras guardian (security decisions)
       -> SharedSalamander -> Intelligence.salamander.SalamanderEngine
       -> SharedTuring -> VQCPipeline -> verification/certificate/custody/replay
       -> SharedEuclid -> EuclidRuntime (intelligence/delegation owner)
          dispatch_specialist -> AL HARAS -> creator-scoped delegation
            -> TuringQuantumOrgan -> TURING backend selection + execution
          heal_organ -> Salamander authorised control plane
            -> AL HARAS -> registered bounded action -> postcondition verifier
            [closed unless guardian AND token provider are configured]
```

**Important:** the EUCLID specialist path is not the `SharedTuring` path. Its
`turing_euclid_handoff` custody record does not establish a full canonical
certificate/custody/replay acceptance. A separate successful SharedTuring startup
check does not change that distinction.

## Responsibility and dependency inventory

| Consumer / owner | Actual boundary and responsibility | Classification / status |
| --- | --- | --- |
| TURING typed facade / native adapter | Existing exact engine, validation, finite optimization, jobs and mathematical provenance | Local runtime; implemented. No direct AL HARAS, Salamander or EUCLID client on this path |
| `ProductionOrganism` / `ProductionSystemRelations` | Binds owners and one shared custody lifecycle; guardian required at construction | In-process composition dependency; implemented, not a network API |
| `EuclidRuntime.dispatch_specialist` -> AL HARAS | `GuardianRequest` plus out-of-band token -> verdict, then delegation gates | Local runtime dependency; real allow/deny and TURING dispatch tests exist |
| `SharedALHaras` -> guardian | Delegates actual security decisions and records their custody evidence | Implemented adapter; does not itself confer identity or customer isolation |
| `EuclidRuntime` -> `TuringQuantumOrgan` | Intelligence chooses/delegates; TURING admits and executes the Program | Implemented. Current direction is EUCLID consuming TURING, not a verified typed TURING client consuming EUCLID intelligence |
| `EuclidRuntime.heal_organ` -> `salamander.authority` | Authorised bounded requalification with independent redispatch verifier | Implemented seam; provider mismatch corrected and real-owner local tests added. Not wired by default production root |
| `SharedSalamander` -> `Intelligence.salamander.SalamanderEngine` | Legacy diagnosis/repair proposal and custody of outcomes/failures | Existing local runtime surface. A proposal record is not verified recovery or a substitute for the control plane |
| `SharedTuring` -> `VQCPipeline` | Preserves engine ownership; validates before shared custody, then readback/replay | Implemented; existing real custody and substitution-rejection tests reused |
| Capability-delivery TURING -> EUCLID intelligence | Intended consumption of intelligence with owner/version/result provenance | Architectural relationship; precise typed consumption and service contract unresolved |
| Remote security/intelligence/recovery endpoints | Authentication, transport, schemas, deadlines and deployment versions | Not verified by this work. Do not infer a service dependency from a local import |

`DEFAULT_PEERS` in `aethel/enterprise/system_relations.py` is a data lineage/sharing
map. It is not an authorization policy or proof that every named integration is
active. Historical redirects in TURING's `july_compat.py`, a listener-registration
hook in `turing_core/ten_thousand.py`, and the proposal-only
`euclid/organ_adapters/vqc_intelligence.py` are separate surfaces; their presence
does not establish governed typed-facade intelligence consumption. The latter's
candidate ranking explicitly requires independent verification and is not the
native finite-domain VQE optimization contract.

## Packaging, versions and deployment assumptions

- TURING's declared runtime dependencies remain NumPy, SymPy and
  `hyba-kellogg-tensor`; research/test tooling is development-only. No speculative
  hard dependency has been added to the mathematical wheel.
- The descriptor at `packaging/salamander/pyproject.toml` declares
  `hyba-salamander-self-healing` 1.0.0 and bundles `salamander*` and `al_haras*`;
  it declares PyYAML and cryptography, not a separate AL HARAS product dependency.
- `packaging/euclid-engine/pyproject.toml` declares
  `hyba-euclid-intelligence` 1.0.0 with NumPy, Kellogg, TOE and THESEUS ranges;
  `euclid.__version__` is 17.0.0. Package/runtime version labels are not an agreed
  cross-component compatibility matrix. Both packaging directories mark legacy
  documentation deprecated; descriptors are evidence of declarations, not proof
  of an approved release or complete installable enterprise dependency closure.
- This inspection is of one monorepo, not a verified set of separately deployed
  repositories. If owners select separate services or distributions, agree
  protocol/schema versions, authentication, tenant identity, supported version
  combinations, startup/shutdown ownership, and independent installed-system
  tests before changing dependencies. Preserve a stable service boundary if one
  is established; do not replace it with forced package imports.

## Incomplete work and release effect

1. Default `ProductionOrganism.start()` composes EUCLID without a subscription
   token provider. Requalification must remain closed; do not report active
   self-healing. Agree credential ownership and creator-to-customer tenant mapping
   before enabling it (`heal_organ` currently uses `creator_id` as tenant).
2. Decide and test the governed service execution path: direct specialist backend
   results versus the existing canonical SharedTuring certificate/custody chain.
   Do not duplicate that engine or silently upgrade handoff evidence.
3. Define the specific EUCLID intelligence result TURING consumes, preserving
   owner, schema/version and evidence. Cognition mappings are not `Estimate`
   objects or exact coefficients without an explicit verified transformation.
4. Close the trust, packaging and compatibility requirements in
   [dependency contracts](dependency-contracts.md) and
   [security boundaries](security-boundaries.md) before claiming the full governed
   capability is production-qualified. These gaps do not invalidate separately
   verified local mathematics or automatically prevent a narrower library release;
   the release owner must approve an accurate supported scope.

No frontend, new commercial rules, package reorganisation or engine replacement
is part of this change. Integration decisions stay visible in the existing
[qualification ledger](../TURING-qualification.md).
