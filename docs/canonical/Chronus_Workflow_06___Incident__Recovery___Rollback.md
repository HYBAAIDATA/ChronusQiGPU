# Chronus Workflow 06 — Incident, Recovery & Rollback

## Trigger classes

Incorrect result; backend mismatch; device loss; performance regression; security/tenancy violation; provenance break; corrupt artifact; deployment failure; evidence inconsistency; unsupported claim promotion.

## Response

1. Freeze affected promotion/release.
2. Preserve raw evidence and logs.
3. Identify exact artifact, workload, backend and policy state.
4. Quarantine affected result/device/release as appropriate.
5. Reproduce against reference path.
6. Diagnose and bound blast radius.
7. Select fix, rollback or disablement.
8. Re-test applicable production gates.
9. Owner approval before restoring high-stakes capability where required.
10. Record incident, root cause, evidence, corrective action and recurrence prevention.

## Non-negotiable

Recovery must not erase the evidence that caused the rollback.