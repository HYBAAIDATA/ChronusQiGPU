# Capability trust boundaries and security qualification

## Assets, principals and trust assumptions

Protect customer inputs/results, tenant and actor identity, entitlement keys,
privileged recovery actions, and decision/custody provenance. Treat request data,
external dependency responses and serialized artifacts as untrusted. The current
inspected integration is local Python composition with trusted implementations;
it does not establish an authenticated remote-service perimeter. An in-process
caller with arbitrary object/code access can bypass wrapper entry points.

AL HARAS owns actual entitlement/policy decisions. TURING independently owns
input/admission validation and mathematical/certificate integrity. EUCLID owns
creator-scoped delegation; Salamander owns bounded actuation and postcondition
verification. Shared custody owns storage integrity/lifecycle. No owner supplies
all of these guarantees merely by being present.

## Threat/control/evidence record

| Threat / boundary | Existing specific control | Evidence / unresolved requirement |
| --- | --- | --- |
| Unauthorised specialist call | AL HARAS signed tenant/actor/capability/time claims, operation policy; EUCLID delegation gates | Real guardian + TURING allow/deny/expiry/tenant tests. Local facade and SharedTuring are not customer authentication endpoints; the serving layer must prohibit bypass |
| Duplicate/replayed privilege | Optional AL HARAS `jti`; Salamander bound one-use receipts, scoped idempotency/fingerprints and in-doubt records | Local replay and real authorizer regressions; shared durable nonce store and multi-instance/restart semantics need deployment evidence |
| Forged/malformed dependency response | Canonical local guardian, Salamander receipt/audit validation, independent action verifier; SharedTuring result/certificate checks | EUCLID trusts guardian verdict attributes; it is NOT qualified to consume arbitrary remote verdicts. Define authenticated schema/binding checks before that trust boundary changes |
| Credential disclosure | Token provider is out-of-band; canonical actuation fetches once; fixture token absent from action/EUCLID evidence | New real-chain test; full logs/errors/dumps and provider-failure redaction review remain open. Do not put credentials in request payloads |
| Customer/organisation crossover | Explicit tenant/actor claims and creator-scoped rights | Creator ID used as heal tenant; service identity mapping, storage ACLs and cross-customer deployment isolation need owner agreement/testing |
| Unauthorised or unsafe healing | Missing guardian/provider closes actuation; canonical registry requires AL HARAS receipt and postcondition verifier | No proposal-as-recovery assumption. The default root does not provision an actuation credential; actual supported recovery policy still needs approval |
| Changed mathematical result or provenance | Existing canonical boundary verification, certificate binding and shared readback/replay | Existing foreign-certificate/result-substitution tests reused. A specialist handoff alone is not equivalent evidence |
| Dependency outage, blocked handler, uncertain effect | Errors/refusals remain failures; bounded recovery and in-doubt tracking exist in Salamander | No universal synchronous deadline/cancel guarantee. Agree supervision, bounded retry and reconciliation before service deployment; do not fall back to unguarded execution |
| Dependency substitution / vulnerable artifact | Existing package and release evidence records | Installed enterprise dependency closure, required SCA/SAST/secret/license scans, authenticated artifact/version policy still open. A source import is not supply-chain approval |

## Required deployment decisions, not invented controls

The platform/security owners must specify trusted dependency identity and artifact
integrity, key provisioning/rotation/revocation, tenant-to-creator mapping, audit
retention/access, least-privilege operation policies, transport authentication if
services are selected, and durable replay/idempotency scope. They must also
validate outage/incompatibility and rollback behavior for the chosen deployment.
No vault, TLS/mTLS, cross-organisation isolation, signed release, or automatic
self-healing is asserted here without implementation evidence.

Intelligence outputs can propose or route; they cannot manufacture AL HARAS
permission, mathematical validity, or postcondition evidence. Privileged effects
must stay behind the actual security/actuation owners even when intelligence is
unavailable. Security-critical operations fail closed; other recovery uses only
documented, verified bounded behavior. Missing integration is a visible limitation,
not a successful mock or an implicit downgrade.

See [contracts](dependency-contracts.md), [architecture](capability-architecture.md)
and the [qualification ledger](../TURING-qualification.md). Private vulnerability
reporting remains governed by [SECURITY.md](../SECURITY.md); this document does
not create a new mailbox, service commitment or release approval.
