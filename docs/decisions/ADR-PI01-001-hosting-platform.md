# ADR-PI01-001: Evaluate Container Apps versus AKS

Status: Proposed; platform decision pending evidence and accountable approval.
Linked program: [PI-01](../programs/PI-01-azure-operational-hardening.md).

## Context

The repository already contains [Container Apps Bicep](../../deploy/azure/main.bicep)
and [Azure deployment preparation](../../deploy/azure/README.md). This establishes an
infrastructure candidate, not evidence of a live qualified deployment. The preparation
notes separate hosted control-plane operation from a verified hardware host and remote
worker qualification. HTTP health is not mining readiness.

Existing domain responsibility is governed by
[Owner Declarations](../../OWNER_DECLARATIONS.md). Infrastructure placement must not
transfer THESEUS, CHRONUS, OVID, AL HARAS, EUCLID, PYTHIA or SALAMANDER authority.

## Decision rule

Evaluate AKS suitability; do not presume migration. Keep Container Apps as the current
repository hosting baseline while collecting requirements. Admit AKS only when:

1. A necessary operational requirement is documented and backed by evidence.
2. Container Apps cannot satisfy it within the approved constraints; the specific
   limitation is demonstrated, not assumed.
3. AKS can satisfy it through a tested candidate, including security and recovery.
4. Incremental cost, staffing, complexity, failure surface and rollback are justified.
5. The accountable architecture/program owners approve the ADR and evidence.

## Alternatives

- Harden the existing Container Apps control-plane candidate.
- Adopt AKS for explicitly justified workloads.
- Use a hybrid control plane plus separately qualified hardware workers.

Evaluate device access/protocols, durable state and replica safety, network boundaries,
identity, observability, lifecycle, recovery objectives and total operational cost.
Moving a control application to AKS does not itself qualify a remote mining protocol,
physical device, pool acceptance, hashrate or profitability.

## Evidence required to decide

Requirement and constraint matrix; executed candidate results; identity/access and
rotation tests; state/restart/failure tests; device/worker boundary evidence where relevant;
cost and staffing model; migration/rollback/configuration-restoration drill; retained
limitations and independent approvals.

If no requirement justifies AKS, do not introduce it in PI-01. If evidence is incomplete,
retain status Proposed/UNVERIFIED rather than marking the platform decision Accepted.
No infrastructure deployment, external ingress, live mining or spending is authorized
by this ADR.
