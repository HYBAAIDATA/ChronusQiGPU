# Sovereign client journey: implementation and qualification ledger (2026-11-16)

**Scope:** [HYBAAIDATA/ChronusQiGPU](https://github.com/HYBAAIDATA/ChronusQiGPU), `main` reviewed at `55ce7bd5`.
This is a code/evidence map, not a deployment certificate. The attached proposal's
Ministry of Defence tenant, Secret accreditation, `chronus.sovereign` URLs,
10,000-node scaling and illustrated FLOP totals are **examples, not production
observations**. No agency client, clearance, bill, HSM or fleet is asserted.

## Reuse the authoritative implementations: do not fork the journey

| User journey step | Existing authority and implementation | Verified gap / posture |
|---|---|---|
| Identity and access | AL HARAS: `service/auth_middleware.py`, `service/dependencies.py` | JWT/role boundary exists; legacy static tokens and permissive development options must not be enabled in production. |
| Tenant onboarding | `service/routers/ciaas.py`, `service/instant_provisioning.py`, `service/ciaas_store.py` | Existing instant contract/webhook flow; store uses in-memory administrative tenant profiles and contains reference seed tenants. Do not provision a second record or invent API keys. |
| Jurisdiction / security clearance | AL HARAS sovereign governance register in `security/al_haras/sovereign.py` | Eligibility, authorisation to process classified workloads, personnel/operational accreditation and jurisdiction checks **UNVERIFIED**. A declared `sovereign_profile_enabled` is not independent accreditation. |
| Tenant custody | THESEUS: `storage/durable.py`; OVID transformation and `storage/theseus.py` | SQLite/WAL integrity/continuity interfaces exist; prove deployment durability, backup, restore, and access separation independently. |
| Workload submission | `service/routers/workloads.py`, execution adapters, qualification gates | Receipt scope can be process-local. No published evidence here of real sovereign workload admission or classified execution. |
| Scaling | `fleet/coordinator.py`, `fleet/scale.py`, `fleet/phase.py`; CIaaS ECA in `service/instant_provisioning.py` | Fleet scale-up is subject to signed grants, tier selections and measured admission. ECA quota is not a running node. Never call `provision_node` or assume M3 Ultra capacity based on the proposal. |
| Consumption accounting | `service/routers/billing.py`, workload store | Fixed the initial 100-record truncation; explicit complete-ledger reporting, CCU availability and quality. Existing CCU is recorded, not independent FLOP metering. |
| Hermiten commercial settlement | `service/ciaas_store.py`, `service/routers/ciaas.py` | Existing **25% value-share** formula retained; default/example dollar amounts are not verified commercial savings. Do not introduce the proposal's unsupported 20% or GBP tariffs. |
| Remote Hermiten usage delivery | `service/routers/billing.py` (opt-in) | Configurable HTTPS adapter with tenant-scoped account lookup, role check, stable idempotency key, THESEUS intent + acknowledgement journal. **DISABLED** until a real provider contract, credentials and tenant mapping are supplied. Receipt is not an invoice. |
| Forensic replay | `storage/durable.py` (`reconstruct`, `verify_journal_continuity`, `verify_store`) | Test custody and restart recovery, but do not equate a signed local receipt or a reference-only mock with an independently verified classified workload. |

## Safe billing operation

`GET /billing/usage` scans all paginated workload records for the authenticated tenant
(up to the explicit 100,000-record bounded scan; above that it fails instead of
under-reporting). It reports complete vs missing recorded CCU separately and
labels FLOPs, hardware evidence and billing proof as unavailable where necessary.
The Ed25519 aggregate receipt remains **process-local**, not an invoice.

`POST /billing/hermiten/usage/{workload_id}` is the **same billing router**,
not a new billing system. It is role-limited to the authenticated tenant's
`tenant_admin`/ `system_admin` identity and accepts only a completed local
workload with recorded CCU and a receipt *reference*. It does **not** convert
CCU into TFLOPs, apply invented tariffs, generate invoices or treat
a reference as a verified device measurement.

Required configuration (all mandatory; no default live URL):

- `CHRONUS_HERMITEN_USAGE_ENABLED=1` — owner-approved explicit remote-delivery enablement.
- `CHRONUS_HERMITEN_USAGE_ENDPOINT` — verified provider-specific `https://` endpoint.
- `CHRONUS_HERMITEN_API_TOKEN` — distinct service-to-service provider credential.
- `CHRONUS_HERMITEN_ACCOUNT_MAP` — trusted JSON mapping from tenant IDs to existing external accounts, e.g. `{"tenant_approved":"external_account_id"}`. Neither caller claims nor fake account IDs are accepted.
- `CHRONUS_THESEUS_DB_PATH` — durable tenant-custody SQLite/WAL path on an appropriately controlled persistent volume.

The delivery contract here is `chronus.hermiten.usage/v1`, requiring a provider
acknowledgement containing the exact bound `account_id` and a nonempty
`usage_receipt_id`. **The live Hermiten contract is not independently
verified**; keep delivery disabled until it is agreed and tested against the
real service. Provider-side deduplication of the `Idempotency-Key` is
mandatory before enabling retries. A journalled intent does not itself prove
the provider accepted usage. Provider acknowledgement is journalled separately.
Operationally, any 503 after provider acknowledgement may need reconciliation
using that stable key. Never store the provider API token in THESEUS.

## Explicit unresolved production gates

1. **AL HARAS:** Demonstrate clearance and jurisdiction authorisation from
   trusted records. Require external government/security accreditation where
   applicable; no default SECRET admission.
2. **Tenant durability:** The `CIaaSStore` is in-memory and has seeded
   reference tenants. Demonstrate persistent tenant identity/contract/account
   mapping with replay and restart tests before public provisioning.
3. **Credentials:** Verify external KMS/HSM possession, secure secret
   handoff, tenant isolation and rollback; no fictitious HSM custody.
4. **Fleet:** Authorised signed grant, measured worker join, healthy worker,
   tier capacity, customer isolation and release gate before any node claim.
5. **Metering and economics:** Trustworthy CCU provenance, raw measured
   FLOPs/GB-hours where required, unit mapping, contracted rate card, approved
   benchmark for savings, reconciliation and tax compliance.
6. **Provider:** Real Hermiten API contract, production endpoint, independent
   credentials, account mapping, idempotent acknowledgements and invoice
   reconciliation before billable use.
7. **Execution:** End-to-end real workload, exact result verification,
   THESEUS restart/replay, custody attack tests and operator acceptance.
8. **Production:** Green CI, CodeQL, audited deployment TLS, runtime
   observations, operational alerting and sign-off. **Production qualification:
   UNVERIFIED.** Repository tests and simulated exercises cannot certify it.

## Validation

Run `pytest -q tests/test_billing_sovereign_journey.py
tests/test_e2e_journeys.py tests/test_ciaas_rbac.py
tests/test_instant_provisioning.py`.

The integration test uses an explicit test double for the unconfigured
external provider. Its result demonstrates protocol logic, **not**
connection to a live provider or a live sovereign tenant. No example
customer or hardware metric is treated as a measurement.

## CIaaS security and claims hardening (2026-11-16)

The existing `/v1/auth/token` endpoint was able to create privileged
tokens without an authenticated caller. It now requires an AL HARAS
`system_admin` principal. The same requirement protects
`GET /v1/tenants` and regular `POST /v1/tenants/onboard`.
No new identity store was introduced. The token endpoint is an
administrator-only helper and **is not an OIDC/OAuth2 identity provider**.

Tenant reads, pricing, capacity, entitlement mutation and settlement
previews now enforce that the authenticated principal is entitled to
the requested tenant. Changing CCE or calculating a settlement is
restricted to tenant/system administrators; role possession alone
does not permit cross-tenant access.

The previous `CIaaSStore.get_pods_fleet()` returned fixed node counts,
100% bus saturation, 130 Tb/s bandwidth, zero stalled packets and
a one-cycle healer as if measured. It now returns the declared
alpha–delta topology but marks actual node counts, health and
performance as **UNVERIFIED**. The prior sovereign profile returned
`FULLY_COMPLIANT` with 14/14 NCSC principles despite the independent
AL HARAS register showing zero assessed. It now uses the AL HARAS
register and distinguishes no assessment from certified compliance.
An execution backend appearing in discovery is not hardware proof.

The existing `POST /v1/fabric/clusters/register` and
`POST /v1/fabric/pools/schedule` were success-shaped placeholders
that never admitted a signed fleet worker or dispatched a verified
workload. They now require system-admin authority and fail closed
with `503 fleet_execution_unverified` until linked to the existing
`FleetCoordinator` and authorised signing/grant path. This **does not
remove** fleet scheduling or signed scale grants; it prevents
false execution evidence through the HTTP façade.

The `POST /v1/billing/hermiten/settlement` caller-input preview retains
the existing **25%** value-share computation but now returns
`CALCULATED_UNVERIFIED`, no invoice and no fabricated settlement
certificate. The economic terms and independently verified
comparative baseline remain external commercial evidence requirements.

### Evidence and acceptance

The source and updated regression assertions are committed in
PR #125. GitHub Actions jobs have had unavailable runner logs, including
on the unchanged `main` baseline. Accordingly, **test execution,
real-world deployment, HSM operation, Hermiten API connectivity,
fleet dispatch and sovereign accreditation are not verified here**.
Do not treat a simulated test fixture or hard-coded reference
capacity as accepted production performance.

The shared `CIaaSStore.calculate_hermiten_settlement()` now uses
`Decimal` cent arithmetic and rejects non-finite or negative amounts.
It returns the **25% calculated value-share preview**, not a
provider-authorised reconciliation, with
`settlement_status=CALCULATED_UNVERIFIED` and no proof certificate.
The result is deliberately not a financial settlement receipt.
