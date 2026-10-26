# Historical, unapproved adapter experiment — NOT a current service contract

Hermitten belongs to a separate avoided-cost data commercial model. It is not
an integration dependency, acceptance criterion, release gate or blocker for
TURING/VQC. The previously proposed endpoints and tariff/spending semantics in
this file were assumptions, not an approved external interface. They are withdrawn
as an activation contract. No receiver conformance or financial transaction was
established. Existing `billing.py` helpers and their double-backed tests are
retained solely for compatibility/history; production composition does not import
or instantiate their receiver. They do not select a future billing provider.

TURING/VQC's architectural direction is contractually agreed usage-based billing.
Current billing is DEFERRED: no rating, chargeable unit, rate, invoice, payment,
billing schedule or provider is approved here. A future separately authorised
change must bring the actual commercial decisions and owner-approved interface,
versioned metering contract, entitlement rules, idempotency/reconciliation semantics,
security qualification and signed acceptance. Do not infer those from this code.

Operational completion records remain immutable, retained and non-financial.
Their legacy `unit` identifier is a technical completion counter, not an approved
chargeable unit. New events explicitly carry `billing_scope: deferred` and
`chargeable: false`; historical events are not rewritten. Retained legacy account
labels and outboxes are not evidence of an account at any external provider.
