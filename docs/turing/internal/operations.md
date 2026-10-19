# Operations, release and incident runbooks

## Existing runbooks remain authoritative

Keep [package operations](../../../turing_universal_quantum_computer/docs/operations.md), [release policy](../../../turing_universal_quantum_computer/docs/release-policy.md) and [qualification ledger](../../../turing_universal_quantum_computer/TURING-qualification.md) in place. This page adds service handover gates, not duplicate release commands.

## Incident procedure (candidate; tabletop/rehearsal pending)

**Scope:** suspected wrong result, data exposure, lost job state, unsafe recovery, or artifact mismatch. **Permission:** designated incident/release/security owners; named assignments pending. **Prerequisite:** safe access to exact candidate identifiers and sanitised evidence.

1. Stop promotion and new affected workload admission through the owning control boundary. Do not assume a UI flag stops running work.
2. Record incident identity, time, affected tenants/versions, job/request IDs and observed symptoms; preserve access-controlled evidence without credentials.
3. Distinguish execution failure, timeout, custody failure and billing ambiguity. Never rerun billable/irreversible work merely because a wait expired.
4. Escalate to computational, security, service and billing owners as applicable through approved channels (not defined by this page).
5. Apply only an authorised, bounded recovery plan. Restore the last approved artifact/configuration; independently verify computation, access and custody postconditions.
6. Reconcile in-flight work, usage events and receiver ACKs; preserve dispute/correction history.
7. Record impact, decision authority, postconditions, customer communications and follow-up defects before reopening admission.

**Verification:** independent representative computation plus negative policy tests and evidence/replay checks on the restored candidate. **Failure:** if restoration or integrity is uncertain, remain unavailable and escalate; do not self-certify recovery. **Audit:** retain approver, actions, old/new hashes and verification evidence.

## Release and rollback

Run the existing exact-candidate gates, retain artifact hashes and obtain human approval. Documentation builds do not authorize upload, tag, registry publication or deployment. A rollback rehearsal and package withdrawal are different operations; neither overwrites an existing package version. Known issues, owners, mitigation and expiry must remain visible.

No full repository gauntlet, operational soak, incident rehearsal or production rollback was performed by this documentation increment.
