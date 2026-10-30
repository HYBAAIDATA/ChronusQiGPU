# CHRONUS — Canonical Operations Manual & Production Constitution

<aside>

**CANONICAL / OWNER-CONTROLLED.** This is the governing operational manual for Chronus. It must be consulted before any material Chronus architecture, capability, workload, benchmark, claim, packaging, release, deployment, security, authority, evidence, or production-readiness change. No person or agent may modify, supersede, reinterpret, or promote a conflicting record without explicit approval from Andre Taylor-Morris.

</aside>

## Authority hierarchy

1. Owner authority — Andre Taylor-Morris.
2. Executable truth — repository code, tests, runtime evidence, signed artifacts, benchmark outputs, device-bound evidence.
3. This manual and its mandatory workflows.
4. Current owner-approved architecture register.
5. Supporting specifications and historical records as provenance only where they do not conflict with current authority.

## Canonical identity

Chronus is HYBA's heterogeneous execution, acceleration, device-routing, Virtual iGPU, and compute-fabric plane. It governs execution across CPU, iGPU, GPU, remote accelerator, FPGA/ASIC, cloud and future HYBA hardware where implemented and evidenced.

## Authority boundaries

- Turing: independent VQC; its workloads may execute through Chronus.
- OVID: versioned transformation / fold-materialise authority.
- THESEUS: durable custody / replicas / continuity / recovery / journal / provenance.
- Geodesic: search/indexing outside custody.
- PULVINI: folded representation/state capability, separately attributable.
- AL HARAS: security/governance/evidence authority.
- Salamander: bounded healing/recovery/optimisation/promotion/rollback.

## Shared THESEUS operational-record service

Chronus must use THESEUS as the durable custody/provenance plane for production workload manifests, routing decisions, device/backend identity, execution receipts, numerical validation, timing/resource measurements, failures, recovery evidence and benchmark artifacts where those records are required to persist.

Chronus remains authoritative for heterogeneous-execution semantics. THESEUS preserves the records; it does not decide whether a backend result is correct. AL HARAS governs security/authorisation of custody operations. OVID may transform/fold/materialise state under an explicit contract where used.

Tensor and iGPU/GPU workload services use the same custody plane so a production result can be traced from workload contract → backend/device → execution → validation → durable evidence → replay/recovery.

See [THESEUS — Canonical Custody, Operational Records & Continuity Service](https://app.notion.com/p/THESEUS-Canonical-Custody-Operational-Records-Continuity-Service-3f0bcc6fa4998106bbd3f0438cfa393e?pvs=21).

## Owner approval required

Explicit owner approval is mandatory for changes to product identity, architecture, authority, subsystem ownership, production status, deployment profiles, material claim state, benchmark methodology, release/provenance policy, security policy, new physical production backends, new production workload families, or this manual.

## Mandatory preflight

Before change: consult this manual; identify affected contract and current evidence state; compare proposal to executable truth; create a proposal where owner approval is required; implement only after approval; re-run applicable workflow; preserve provenance.

## Evidence doctrine

`MEASURED`, `UNAVAILABLE`, `MISSING`, `GATED`, `REFUTED` and approved scientific claim states remain distinct. Device presence is not device execution. Performance claims require matched work, semantics, precision and quality. Negative results remain in the record.

## Deployment profiles

Developer · Edge · Enterprise · Sovereign · Hyperscaler. Hyperscaler means multi-tenant control plane, elastic accelerator pools, regional placement, quotas, metering and failure-domain isolation — not a fabricated GPU SKU.

## Workload families

Tensor, Render/QSDL, Turing execution support, Scientific, Geodesic/Search, AI/Inference/Training, Mining, and future owner-approved workload families.

## Constitutional rule

If code, Notion, a PR description, an agent memory, or another record conflicts with this manual, the conflict is raised for owner review. Conflicting material must not silently become canonical.

[Chronus Workflow 01 — Production Workload Admission & Promotion](Chronus%20Workflow%2001%20%E2%80%94%20Production%20Workload%20Admissio%203f0bcc6fa49981a191bcc8a423e28d79.md)

[Chronus Workflow 02 — Hardware & Accelerator Certification](Chronus%20Workflow%2002%20%E2%80%94%20Hardware%20&%20Accelerator%20Certi%203f0bcc6fa49981cfb54ecce36cab9a70.md)

[Chronus Workflow 03 — Benchmark & Claim Promotion](Chronus%20Workflow%2003%20%E2%80%94%20Benchmark%20&%20Claim%20Promotion%203f0bcc6fa49981f9a501c3ddbeb65507.md)

[Chronus Workflow 04 — Release, Artifact & Provenance](Chronus%20Workflow%2004%20%E2%80%94%20Release,%20Artifact%20&%20Provenan%203f0bcc6fa49981e7ad37f18235679bb0.md)

[Chronus Workflow 05 — Deployment Admission by Profile](Chronus%20Workflow%2005%20%E2%80%94%20Deployment%20Admission%20by%20Prof%203f0bcc6fa49981e1bfc2cbeb5144f068.md)

[Chronus Workflow 06 — Incident, Recovery & Rollback](Chronus%20Workflow%2006%20%E2%80%94%20Incident,%20Recovery%20&%20Rollbac%203f0bcc6fa49981b0bb28caa7aad60adb.md)

[Chronus Workflow 07 — Change Control & Owner Approval](Chronus%20Workflow%2007%20%E2%80%94%20Change%20Control%20&%20Owner%20Appro%203f0bcc6fa4998132b7b1c12ce9b153a1.md)

[Chronus Workflow 08 — Weekly Operational Risk Review](Chronus%20Workflow%2008%20%E2%80%94%20Weekly%20Operational%20Risk%20Revi%203f0bcc6fa4998196a304ec190ff50525.md)