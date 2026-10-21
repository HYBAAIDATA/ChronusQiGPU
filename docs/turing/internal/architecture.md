# Architecture, dependencies and failure boundaries

## Intended authority versus inspected implementation

| Component | Intended responsibility | Inspected integration disposition |
| --- | --- | --- |
| TURING | Computation, admission, pipeline, contracts, results and provenance | Implemented; incompletely qualified for release. Typed facade and canonical pipeline source inspected; no full runtime qualification in this increment |
| EUCLID | Intelligence orchestration, training/evaluation and RewardAuthority within its scope | TURING service-specific invocation/evaluation path not verified here; unavailable as a qualified service claim |
| AL HARAS | Policy, security authority, privileged authorisation | Service-control candidate #97 consumes subscription verifier; source/record evidence, broader identity/revocation/deployment qualification open |
| Salamander | Governed healing and optimisation | Outcome-boundary record explicitly incomplete; real TURING recovery voyages and factory/verifier wiring open; no service-wide self-healing guarantee |
| Commercial service | Organisations, allocation, metering/billing integration | Separate #97 pilot control library; actual HTTP/UI, SSO, containment, Hermitten reconciliation and service approval open |

Use status labels consistently: **implemented and tested** requires retained scoped execution; **implemented but incompletely qualified** means code exists but gates remain; **planned** is design only; **unavailable** means no verified callable capability in the relevant deployment. Historical reported tests are not fresh results for this branch.

## System context

```text
Enterprise / developer / researcher
          | problem + authorised access (service gate open)
          v
Service boundary [#97 candidate; not a deployed HTTP API]
          | runtime port (combined voyage not qualified)
          v
TURING [admit -> execute -> verify -> result/provenance]
```

## Component and dependency map

```text
Typed facade -> native compiler/backend -> canonical VQCPipeline
                                          | representation planner / registry
                                          | exact engines (Kellogg where bound)
                                          | certificates / witnesses
                                          + optional custody / replay adapters

Intended adjuncts: EUCLID intelligence | AL HARAS policy | Salamander recovery
Their named responsibility is not evidence of an integrated service path.
```

## Data flow

```text
Program + settings -> immutable artifact/request bindings -> admitted execution
-> canonical result + certificate + witness -> API envelope
-> [explicitly configured custody] -> recovered bundle -> binding/replay checks
Service candidate: verified completion -> usage candidate -> outbox -> receiver ACK
No usage candidate proves an invoice or payment.
```

## Failure boundaries

```text
Invalid input -> reject, no changed computation
Domain/resource mismatch -> refuse, no hidden approximation
Wait timeout -> work may continue; reconcile original job
Missing custody / integration -> gated or unavailable, not success evidence
Result/certificate mismatch -> fail; quarantine evidence
Missing independent recovery proof -> no certified healing claim
Missing provider job -> no measured-QPU claim
```

## Custody naming conflict

[Owner declarations](../../../OWNER_DECLARATIONS.md) D9 places authoritative durable state with OVID and rebuildable projections with THESEUS. Older implementation documents use the names in the reverse sense. Existing adapters still carry historical names. This portal distinguishes declared ownership from inspected path names; it does not claim a prose update migrated executable custody. Resolve with owning maintainers before customer architecture signoff.

## Evidence references

- [Pipeline record](../../TURING_PRODUCTION_PIPELINE.md) and [caller contract](../../TURING_VQC_CALLER_CONTRACT.md).
- [Salamander boundary record](../../SALAMANDER_OUTCOME_BOUNDARY.md), explicitly not production closure.
- [Service candidate #97](https://github.com/PhiEnterprise1/EuclidPhiEnterprise/pull/97), inspected at `2c1e8aef61f0b3607cb30f582ea975988f9774be`; not merged as a dependency here.
