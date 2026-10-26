# Host integration: governed TURING capability

## Supported local deployment contract

Use the existing platform distribution (`hyba-pythia-mining`) with its TURING and
Kellogg dependencies for this shared capability composition. The mathematical
TURING wheel alone does not install the platform. Do not bolt on independently
packaged overlapping copies of the platform-owned EUCLID/Salamander/AL HARAS
modules and assume a supported installation. No new distribution is introduced.

The host supplies actual AL HARAS authority/policy, custody signing material,
service tenant, creator/delegation identity and an out-of-band credential provider.
The provider has the existing signature `provider(tenant_id, actor_id) -> str`.
It must provide a token entitled for the exact operation, tenant, actor and time.
Never put it in the request or result payload. A one-use token's `jti` cannot be
reused across effects; provider refresh/revocation policy belongs to the host.
No token issuer, policy allowance, vault or commercial entitlement is fabricated.

`examples/governed_capability.py` is a callable integration example using these
real inputs. It invokes the actual `ProductionOrganism` and EUCLID router; it is
not a mock service, unauthenticated endpoint or replacement TURING optimizer.

For a long-lived host, create one production root for its configured custody
tenant, call `start()` once and `stop()` in `finally` (or use the context manager).
Use `service.euclid.route_specialist(...)` for capability routing or
`dispatch_specialist("turing", ...)` for explicit owner dispatch. The admitted
`run-program` payload is the existing native Program mapping with optional
backend preference. The result retains owner/admission/result semantics and adds
the existing canonical `pipeline_report` on the shared-root path. Inspect both
AL HARAS admission and the canonical result/report; an ALLOW decision alone is
not a successful computation.

## Explicit identity and recovery

- `tenant` binds shared custody, dispatch admission and requalification. A token
  valid for a different tenant is still denied by this root.
- `creator_id` owns EUCLID delegation rights; it is not implicitly the customer
  identity on the shared-root path. Standalone EUCLID without a tenant binding
  retains its historical creator fallback; do not mistake that for tenant isolation.
- `subscription_token_provider=None` leaves privileged Salamander actuation closed.
  Providing a callable binds the real authority, not automatic permission. Each
  `heal_organ` still requires a non-empty actor, an approved operation/token,
  registered bounded action and independent verification.
- `status()["salamander_actuation"]` distinguishes configured/constructor-ready
  actuation from absence. It does not attest future credential validity, authorize
  arbitrary repairs or mean every failure is self-healing.
- The supported recovery action requalifies an existing organ using its read-only
  probe and independent redispatch check. Legacy diagnosis proposals remain
  unapplied without their separate authorized actuator; do not change `applied`
  to satisfy a success expectation.

## Failure and concurrency contract

Invalid credentials, foreign tenants and malformed/unbound guardian responses
cannot dispatch the specialist. Dependency exceptions propagate or produce explicit
refusal; there is no fallback to unguarded mathematical execution. Canonical
certificate or custody failure prevents successful acceptance on the shared path.
No automatic resubmission or generic hard interruption of synchronous handlers is
promised. A timeout at a serving layer is not evidence that an effect never ran.

SharedTuring serializes run/replay state; SharedEuclid serializes calls and its
evidence cursor. Tested concurrent callers preserve per-program identity and
certificates. This is not a universal deadlock-free or distributed idempotency
claim. Stop the root before retiring its custody environment. Serving, transport,
health supervision and deployment policy belong to the host, not this library.

## Reproduce installed qualification

Build from a clean source tree; do not reuse a stale `build/lib` tree from before
changing package ownership. Build the existing platform wheel and TURING/Kellogg
artifacts, and export TURING's locked research requirements. The integration-only
`experiments/platform-qualification.txt` is hash-resolved from its `.in` file and
the existing platform dependency ranges; it does not alter TURING runtime deps.

Run `experiments/qualify_capability_installation.py --help` for the explicit wheel,
resolution, consumer-test and output arguments. It rejects overlapping wheel
ownership, installs into an independent environment, checks module origins and
dependency consistency, then runs `tests/test_turing_production_capability.py`
outside the checkout without its source conftest. It records artifact/input hashes,
step outcomes and reviewed JUnit. It never uploads or approves a release.

CI runs mathematical package checks on Python 3.11/3.12/3.13 and the platform
composition/install checks on 3.12/3.13, consistent with the platform's declared
minimum. Local source-archive reports remain `development_only`. Remote CI,
security review, deployment credentials, owner sign-off and release/publishing
approval are separate evidence, not inferred from a local installation test.
