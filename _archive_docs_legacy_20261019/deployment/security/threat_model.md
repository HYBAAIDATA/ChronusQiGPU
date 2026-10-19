# Threat model for enterprise adoption

## Scope

This document defines the production security posture for the PhiEnterprise IGPU stack in enterprise, hyperscaler, and government deployments.

## Security goals

- protect data provenance and integrity
- keep operator authority and proof authority separate
- enforce explicit evidence gates before production use
- fail closed when hardware, pool, job, or evidence is missing
- prevent an intelligence layer from mutating a valid proof boundary

## Trust boundaries

### 1. Data ingestion boundary

- All ingestion enters via the `toe.unified.data_layer` contract.
- Input and output payloads are content-addressed through digest verification.
- Invalid or partially written records are rejected before they can become canonical state.

### 2. Storage / topology boundary

- `aethel/` provides the storage substrate and Cassini-based integrity checks.
- A payload is only accepted when it satisfies the configured integrity gate.
- Journal replay must validate every digest before state is exposed.

### 3. Intelligence boundary

- `toe/bridge.py` and the intelligence package may model, order, and explain operations.
- They do not own SHA256d or final proof semantics.
- Their outputs must remain advisory unless the governance layer explicitly approves them.

### 4. Execution boundary

- Hardware execution is treated as a real operating capability only when device evidence is present.
- CPU execution and synthetic performance claims must be labeled explicitly.
- The system never upgrades a run from unavailable to successful without a measured execution result.

## Threats and controls

### Threat: forged provenance

Control:
- enforce digest chaining and append-only journal semantics
- verify metadata before exposing state
- reject any record whose digest or proof context is missing

### Threat: weak evidence presentation

Control:
- maintain separate evidence classes: source verified, software execution verified, hardware execution verified, pool verified, unverified
- never conflate theoretical performance with measured throughput

### Threat: privilege escalation through intelligence actors

Control:
- authoritative proof remains with the mining / validation path, not the intelligence layer
- keep policy, entitlement, and mediation boundaries separate

### Threat: abuse via synthetic or unverifiable claims

Control:
- every metric must bind to an execution record or observed pool result
- failed gates must produce a fail-closed result, not a synthetic success

## Regulatory posture

For government and regulated enterprise adoption, include:

- audit logs with immutable record metadata
- role-scoped access to sensitive datasets
- provenance for each material model decision
- clear separation of duties between operators and evidence approvers
- retention, export, and consent controls driven by policy engine and tenant policy

## Minimum operational requirements

- mTLS for service-to-service traffic
- secret management via a dedicated external provider
- KMS-backed encryption at rest
- namespace isolation per tenant or workload type
- log immutability and retention policy
- explicit incident response and rollback procedure
