# Actual dependency contracts and failure semantics

This records existing Python boundaries, not invented public/network APIs.
Paths are monorepo-relative. See the [map](capability-architecture.md) for scope.

## AL HARAS: security decision ownership

**Location:** `al_haras/{guardian,models,entitlements,audit}.py`;
`euclid/runtime.py:dispatch_specialist`;
`aethel/enterprise/system_relations.py:SharedALHaras`.

- Input: `GuardianRequest(tenant_id, operation, resource, payload, actor, ...)`
  and a signed subscription token supplied separately. Output: `GuardianVerdict`
  with allowed/reason, tenant/operation/payload identity, evidence and policy version.
- Configuration: trusted issuer/key IDs, HMAC keys, `GuardianPolicy`, operation
  allowlist, payload budget and audit destination. Default operations do not admit
  TURING dispatch or Salamander requalification; an approved explicit policy is
  required. Tests use fixture policies, not commercial entitlements.
- Authentication: `SubscriptionClaims` schema `al-haras.subscription.v2` binds
  tenant, actors, capabilities and validity window. `jti`, when supplied, enables
  one-use tracking in the authority instance. Key rotation primitives are not a
  demonstrated vault/rotation procedure or durable cluster replay protection.
- Failure: missing guardian denies EUCLID specialist dispatch; missing, invalid,
  expired or out-of-scope tokens deny before specialist effects. Guardian errors
  propagate rather than authorising a fallback. EUCLID rejects a non-GuardianVerdict, non-boolean allow, mismatched tenant,
  operation or payload hash, or missing reason/evidence/policy identity before
  specialist dispatch. These binding checks are not remote authentication;
  trusted in-process guardian ownership remains an assumption. No remote timeout/cancellation contract exists.
- Retries: do not replay an effectful dispatch merely because the response was
  lost. A consumed one-use token may already be spent. Dispatch has no general
  durable request-idempotency guarantee. Audit/custody failure is not proof that
  earlier effects did not occur. Never turn an exception into ALLOW.
- Lifecycle/provenance: composition owns guardian/key/audit lifetime; record
  decision evidence and policy identity, not credentials. `SharedALHaras` delegates
  and adds shared custody; it is not independent authentication.

## Salamander: authorised actuation, not proposal-as-recovery

**Location:** `salamander/{authority,control_plane,models}.py`;
`euclid/runtime.py:{_compose_actuation_plane,heal_organ}`.

- Input: `ActionRequest` binds action ID, kind, registered handler, tenant,
  target, actor, reason, bounds, requirements and idempotency key. Output:
  `ActionResult` with status/timing/evidence references, verified flag and error.
  `ActionVerification` names a verifier; successful verification requires evidence.
- Composition: `build_authorized_control_plane(registry, guardian, token_provider,
  ...)` binds the canonical AL HARAS authorizer. Its provider accepts ONE
  `ActionRequest`; EUCLID's public provider accepts `(tenant, actor)`. The adapter
  now translates those signatures at composition. Canonical execution fetches the
  credential once through the authorizer; legacy explicit-token planes retain
  their existing signature path. Provider failure becomes authorization denial
  through the canonical authorizer before requalification, not an orphan action.
  Constructor-bound status is not a promise that a future credential is valid.
- Configuration/authentication: real guardian, out-of-band provider, explicit
  `salamander.requalify` policy, registered bounded action plus independent
  postcondition verifier. Constructor success alone is not credential readiness.
  ProductionOrganism now passes an explicitly supplied provider and its custody
  tenant into EUCLID. Without a provider, actuation still refuses. Tenant identity
  is not inferred from creator identity on this production path.
- Validation: the registry binds a canonical authorizer; receipts bind the action
  and are consumed for dispatch. Unverified postconditions remain UNVERIFIED;
  they are not a successful heal. EUCLID's current requalification probes and
  redispatches the specialist; it is not arbitrary repair, mathematical
  revalidation, or a licence to mutate TURING algorithms.
- Retry/idempotency: the control plane serialises execution and scopes keys to
  tenant/actor, checks request fingerprints, records in-doubt work and recovery
  budgets. Replay durability depends on the configured evidence ledger; the
  EUCLID composition's sink is not proof of restart restoration of every action.
  `heal_organ` generates new IDs/keys, so a second call is not automatically the
  same idempotent action. Never retry uncertain side effects without reconciliation.
- Timeout/cancellation: synchronous `execute`/`heal_organ` expose no universal
  hard deadline or forced interruption. Recovery-plan bounds do not imply that a
  blocked handler can be killed. Service-level supervision and resource ownership
  remain to be agreed before remote deployment. No fabricated fallback actuator.
- Evidence: action/authorization/postcondition references remain with their owners;
  EUCLID records its delegation evidence. Tokens must remain out of action/evidence
  payloads. Local tests check the actual provider/guardian/authorizer chain.

Separate legacy surface: `Intelligence/salamander.py` returns repair proposals;
`SharedSalamander` records actual calls/failures. Do not equate that surface with
an authorized verified `salamander.control_plane` action, or set `applied=True`
just to satisfy an obsolete expectation.

## EUCLID / TURING: intelligence versus exact computation

**Location:** `euclid/runtime.py`, `euclid/organ_adapters/specialists.py`,
`aethel/enterprise/system_relations.py:{SharedEuclid,SharedTuring}`.

- `dispatch_specialist(organ_id, request, tenant_id, actor, subscription_token)`
  returns a governed envelope: allowed/organ/operation, governance evidence and
  the owner's result when execution is admitted. EUCLID owns cognition, routing
  and creator-scoped delegation; TURING owns Program semantics, admission and
  execution. EUCLID's older program-search adapter is not its cognition authority.
  In ProductionOrganism the service is bound to the custody tenant; even a valid
  foreign-tenant token is denied before specialist execution.
- `TuringQuantumOrgan` accepts `capability-matrix` or `run-program` with native
  Program mapping and optional backend preference. Unsupported operations fail;
  backend admission refusal remains an unexecuted refusal. Backend errors are not
  converted to successful mathematics. Specialist mappings are not the typed
  facade's `OptimizationResult` or full `SharedTuring` acceptance evidence.
- `SharedTuring.run` uses the existing canonical pipeline, verifies the mathematical
  boundary and records Program/result/certificate/witness/report in the one shared
  custody fabric with readback/replay. ProductionOrganism injects this existing
  owner into `TuringQuantumOrgan(pipeline=...)`. Admitted runs return the canonical
  `pipeline_report` alongside the retained result envelope. Standalone specialists
  without injection retain direct execution. Admission refusal remains unexecuted;
  it never manufactures a certificate. A SharedEuclid handoff is supplementary
  evidence, not a replacement for verification. SharedTuring's run/replay and
  SharedEuclid's dispatch/evidence cursor are serialized per owner instance.
- Custody integrity, mathematical validity and customer authorisation are three
  different assurances. Composition owns shared storage lifetime. Local facade job
  timeout/cancellation semantics remain unchanged and cannot be assumed to govern
  synchronous EUCLID/SALAMANDER calls.
- The supported delivery composition consumes EUCLID's existing capability
  routing/delegation and preserves native Program, GuardianRequest/Verdict and
  canonical report contracts. An additional typed reverse intelligence client is
  not implemented or claimed. Remote transport authentication/deadline policy and
  broader independently deployed version combinations remain unqualified. The
  selected platform/TURING/Kellogg wheels have their own installed qualification;
  this is not proof of every standalone-distribution combination.

## Compatibility and deprecation ownership

No new public API or protocol version is minted by this change. Preserve current
module identities, native Program/certificate schemas and the typed facade's
compatibility promise. Owners must agree a tested version matrix and migration
policy before deployment across distributions/services. An import fallback or
matching version string is not protocol compatibility. Review changes to claims,
policy/schema versions, provider signatures, custody formats and failure behavior
against the existing [release policy](release-policy.md); do not silently change
consumer semantics or infer support from deprecated packaging documentation.
