# Security and data-handling due diligence

## Scope and threat model

Treat untrusted programs, tenant-crossing reads, forged certificates, replayed capabilities, privileged recovery actions, compromised dependencies and leaked telemetry as distinct threats. Assets include input data, results, tenant identities, signing credentials, retained evidence and billing records.

| Boundary | Review / negative test required | Current documentation disposition |
| --- | --- | --- |
| Tenant -> service | Real identity/membership; cross-tenant denial and revocation | Deployment/service integration open |
| Service -> runtime | Resource/deadline/process containment, hostile input | In-process execution is not a sandbox |
| Caller -> result | Input, artifact, result, certificate and witness binding | Implemented contracts; candidate qualification still required |
| Operator -> recovery | AL HARAS authorisation, bounded action and independent outcome | No blanket Salamander assurance |
| Workload -> usage/billing | Stable identities, deduplication, ACK/reconciliation | Receiver and invoice integration open |
| Build -> distribution | Dependency scan, secrets/license review, hashes and provenance | Exact-candidate release gates required |

## Data lifecycle decisions

No default retention period, residency, encryption deployment or deletion SLA is invented. Before operation, record approved classification, purpose/legal basis, allowed locations, access, log redaction, retention, backup/restore, export, deletion evidence and exceptions. Explain whether backups retain deleted data and how access is denied pending expiry.

## Restricted operating information

Keep credentials, policy keys, customer identifiers, infrastructure inventories and incident evidence out of public builds. Secret rotation requires actual key ownership, revocation testing and recovery verification. Logs must not include tokens or sensitive input payloads by default. A pattern scan cannot prove absence of all secrets or classify all confidential material.

See [operations](operations.md), [publication governance](governance.md) and the existing [package security policy](../../../turing_universal_quantum_computer/SECURITY.md).
