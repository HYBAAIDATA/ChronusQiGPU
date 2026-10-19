# Customer and administrator task contracts

## Availability warning

This is an authenticated-customer **documentation design**, not proof of a deployed customer UI. Screenshots and click paths are deliberately absent until the real interface and permissions are approved. Do not fabricate screens. The following task contracts require deployment-specific instructions before handover.

| Task | Required role / prerequisite | Procedure to agree | Expected result | Failure / recovery |
| --- | --- | --- | --- | --- |
| Onboard organisation | Authorised commercial and platform operators; approved scope | Verify identity/terms, configure tenant/policies, validate isolation | Audited organisation and tested access | Deny incomplete approval; escalate to owner |
| Invite users / assign roles | Deployment-authorised admin; membership integration | Use actual identity workflow; least privilege; test negative access | Correct tenant and role | Revoke incorrect grant; retain audit |
| Provision capacity | Authorised operator; approved capacity definition | Admit allocation within verified envelope | Audited logical/physical allocation as actually supported | Reject excess/ambiguous capacity; reconcile |
| Create project / submit work | Authorised analyst; implemented project/API boundary | Validate domain, submit once, record identity | Admitted job with provenance | Surface refusal; no blind resubmission |
| Monitor / interpret results | Authorised job reader | Inspect state, exact values, verdict/stages and evidence | Scoped interpretation | Preserve diagnostics; support review |
| Review usage / statements | Authorised finance/customer reader | Reconcile job -> event -> receiver -> statement | Traceable usage, not assumed invoice | Quarantine duplicates/disputes; billing owner |
| Export / retention | Authorised data owner; approved policy | Export via verified method, check integrity, apply policy | Verified export / authorised retention | No deletion claim without evidence |
| Suspend / offboard / terminate | Authorised admin/operator | Revoke access, reconcile in-flight work, export and delete per agreement | Tested denial and retained receipts | Resolve running work and backup/deletion exceptions |

## Acceptance before customer handover

Each deployed task must add exact prerequisites, actual steps/API, expected response, error codes, recovery, support route and matching redacted screenshots. Validate with both authorised and unauthorised roles. No customer capability becomes implemented by filling in this table.
