# Chronus Workflow 07 — Change Control & Owner Approval

<aside>

No material canonical change is authorised unless Andre Taylor-Morris has explicitly approved it.

</aside>

## Change request must contain

Current state; proposed state; reason; affected authority/contracts; code/docs/tests impacted; risk; evidence; alternatives; compatibility/migration; rollback; requested owner decision.

## Approval classes

- **Owner approval mandatory:** architecture, authority, scope, product identity, production declaration, material claims, benchmark policy, security, release/provenance, new production backend/workload, canonical docs.
- **Operational change allowed without owner approval:** implementation work already inside an approved contract that does not alter authority, claim state, production scope, security posture or external behavior; still requires normal PR/test/evidence controls.

## Unauthorized change handling

Do not silently normalize it. Flag it, preserve provenance, mark it proposed/non-canonical, and seek owner decision.

## Canonical-document edits

Every edit must record approver, date, reason, source evidence and affected versions.