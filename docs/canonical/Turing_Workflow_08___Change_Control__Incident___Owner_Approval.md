# Turing Workflow 08 — Change Control, Incident & Owner Approval

<aside>

No material canonical Turing change is authorised unless Andre Taylor-Morris explicitly approves it.

</aside>

## Approval-required changes

Identity/scope/authority; VQC semantics; representation authority; Turing↔Chronus/Ovid/Theseus contracts; production status; quantum/hardware claims; benchmark methodology; security/custody/release policy; new production backend/capability; canonical docs.

## Incident triggers

Incorrect measurement; representation mismatch; backend disagreement; checkpoint/replay failure; evidence/provenance break; security incident; unsupported claim promotion; production regression.

## Response

Freeze promotion → preserve raw evidence → reproduce on reference → isolate affected representation/backend/release → diagnose → fix/rollback/disable → rerun applicable gates → owner approval before restoring high-stakes capability where required → record root cause and recurrence prevention.

## Unauthorized change

Flag as non-canonical proposal, preserve provenance, and seek owner decision. Never silently normalize it into current architecture.