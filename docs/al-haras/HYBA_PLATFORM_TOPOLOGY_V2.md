# HYBA Platform Topology v2 — TOE + Millennium Maths + Salamander

## Intent

HYBA is the consolidated system boundary. TOE is the shared reasoning runtime;
Salamander is the adaptive resilience control plane for anomaly detection,
bounded self-healing and self-optimization; AL HARAS and L-HRAS provide security
governance and policy; Millennium Maths is a separate, bounded mathematical
analysis service. Millennium is not the mission-data plane, identity authority,
policy engine or action authority. Salamander coordinates existing authorities
rather than replacing them.

This is a target topology and integration contract, not a claim that every
service is deployed or connected.

## Topology

```text
                 HYBA TRUST / GOVERNANCE PLANE
       identity • tenant • purpose • classification • policy
                              |
MISSION / DEFENSIVE            v              MATHEMATICAL RESEARCH
SOURCES ---> HYBA INGRESS ---> EVIDENCE GRAPH <--- Millennium Maths API
                  |             |                    ^
                  |             v                    |
                  +--------> TOE Problem              | only bounded
                               |                      | math payloads
                               v                      |
                        TOE Runtime / Machine --------+
                         |       |       |
                      predictive causal counterfactual
                         |       |       |
                     topological + geometric lenses
                               |
                    reconciliation / uncertainty
                               |
                 AL HARAS + L-HRAS policy gate
                               |
                  analyst review / approved workflow
                               |
                   receipt + audit + verified outcome
                               |
                      bounded TOE feedback
```

The drawing is logical, not a requirement for a single process or network
deployment. Security controls surround every edge; they are not a final
post-processing box. Source authorization and data minimization happen before
TOE or the mathematical service is called.

## Ownership boundaries

- **HYBA ingress/evidence graph:** source provenance, event identity, tenant and
  purpose scope, classification, data quality, retention, deduplication and
  evidence lineage.
- **TOE:** domain-neutral `Problem` contract, reasoning cycle, causal/uncertainty/
  planning/arbitration/explanation capabilities, tenant-scoped runtime receipts.
- **Five forms:** the shared assessment vocabulary (predictive, causal,
  counterfactual, topological, geometric). They are lenses over a common
  evidence context, not five autonomous authorities.
- **Millennium Maths API:** explicitly requested, bounded mathematical probes
  and mathematical research. Requests must not contain mission observations,
  classified evidence, identifiers, secrets, or operational topology.
- **AL HARAS / L-HRAS:** authorization, security governance, defensive policy,
  audit controls and escalation. Neither TOE nor mathematical outputs grant
  authority.
- **Analyst / approved workflow:** accountable decision for consequential use.

## Millennium Maths API contract

The existing repository API is exposed by
`millennium/millennium_reasoning_service.py`, with a `/millennium` router and
bounded endpoints including aggregate, Hodge topology, Yang–Mills finite-volume
gap, Riemann prime-distribution probes, P vs NP, Navier–Stokes, BSD and
Poincaré. The new client is `millennium_math_adapter.MillenniumMathsAPI`.

- Configure the trusted service origin through `MILLENNIUM_API_BASE_URL`.
  HTTPS is required except local loopback HTTP for development.
- Optional bearer token comes from `MILLENNIUM_API_TOKEN`; deploy behind the
  service's real authentication and network policy.
- Endpoint paths are allow-listed; request size, response size and timeout are
  bounded. The client does not accept arbitrary URL paths.
- The adapter reports explicit unavailability when no endpoint is configured
  or a request fails. It must not silently switch to fabricated results.
- Mathematical API calls are separate from mission assessment inputs. Never
  forward source records to this API merely because a mathematical probe is
  available.
- Preserve evidence class, scope and the service's `proof_claim` field. A
  finite probe, numerical result or literature review is not a proof of an open
  Millennium problem. A missing `proof_claim` field defaults to false.

## Evidence graph and five-form reconciliation

Every assessment has one stable assessment ID and a common evidence graph.
Nodes represent source observations, normalized facts, hypotheses, TOE outputs,
mathematical outputs and analyst decisions; edges encode provenance,
transformation, support, contradiction or review. Each derived node retains its
parent references, model/service version, timestamps, assumptions and status.
Do not merge a mathematical diagnostic into mission evidence as if they had the
same semantics. Cross-domain links must be explicit and reviewable.

For each intelligence form, return a typed status: `available`,
`insufficient_evidence`, `not_supported`, `degraded` or `unavailable`.
Conflicts and missing evidence remain visible. A missing result is not a
negative finding. The first topology implementation should be replay/shadow
only, with test fixtures that include disconnected graphs, contradictory
sources, stale events, duplicate events and unavailable services.

## Fail-closed requirements

1. Reject absent tenant/purpose and malformed problem contracts.
2. Reject untrusted Millennium origins, unsupported endpoint names and oversized
   requests/responses.
3. Never pass mission payloads to the Millennium API; only allow-listed,
   non-sensitive mathematical parameters.
4. Mark the whole assessment degraded/unavailable if required TOE receipts or
   audit writes fail; preserve partial service status explicitly.
5. No autonomous consequential action from TOE or Millennium outputs.
6. No cross-tenant evidence, receipts, memory or feedback.
7. Keep API availability, mathematical evidence quality and mission readiness
   as separate statuses.

## Delivery gates

1. Adapter contract tests and existing TOE/millennium suites pass.
2. Configure and verify a real trusted API endpoint and authentication.
3. End-to-end evidence graph and five-form reconciliation tests pass.
4. Threat model, tenancy tests, audit failure tests and dependency outage drills
   pass.
5. Predictive forecasts pass held-out temporal validation with calibration and
   false-alarm metrics before operational use.
6. Human review, rollback and incident response are demonstrated.
7. Release readiness is asserted only after documented acceptance evidence.


## Salamander: adaptive resilience and operational awareness

The HYBA advisory bridge is `hermes.offerings.salamander_platform_adapter.SalamanderPlatformAdapter`, exposed through `NationalSecurityOffering.observe_with_salamander(...)`. It converts normalized telemetry into canonical `HealthObservation` values and calls the injected `AutonomicControlPlane.observe(...)`; it deliberately cannot construct an action registry or authorize/execute recovery. The real control plane must be injected with its existing AL HARAS authorization boundary.

The canonical implementation is `salamander.control_plane.AutonomicControlPlane`
with typed contracts in `salamander.models`. The integration contract is
documented in
[`SALAMANDER_ADAPTIVE_RESILIENCE_INTEGRATION.md`](SALAMANDER_ADAPTIVE_RESILIENCE_INTEGRATION.md).
Do not create a parallel self-healer inside the offering.

Salamander is responsible for:

- **Anomaly detection:** identify abnormal service behavior, correlate signals
  and evidence, rank plausible causes, and preserve uncertainty.
- **Self-healing:** select only registered, policy-authorized, bounded and
  reversible recovery actions; verify service health independently afterward.
- **Self-optimization:** improve declared operational objectives through replay,
  held-out evaluation, shadow/canary rollout and rollback on regression.
- **Coordination:** distinguish proposal, authorization, dispatch,
  acknowledgement and post-action verification in the evidence trail.

The "Jack and Chloe" design metaphor means fast, technically informed response
under pressure—not unchecked autonomy. Missing/stale telemetry remains unknown;
a high anomaly score is not proof of an attack; a handler's success response is
not proof that recovery worked. Consequential actions and changes to security
policy require explicit authorization.

Millennium Maths remains a separate sidecar for non-sensitive mathematical
probes. It must not receive mission telemetry or operational incident payloads.
