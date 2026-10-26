# HYBA Security Subscription and Routing

## Public discovery

| Route | Access | Purpose |
|---|---|---|
| `GET /api/v1/security/status` | Public | Configuration state; never exposes keys |
| `GET /api/v1/security/subscribe` | Public | Returns the configured subscription URL |

## Subscribed evaluation

`POST /api/v1/security/evaluate`

The existing `POST /api/v1/toe/collapse` route is also subscription-gated. It
performs the same preflight before invoking `toe.bridge.TOEBridge` and returns a
Guardian receipt alongside TOE output and execution evidence.

Required headers:

```text
Authorization: Bearer <signed-entitlement>
X-HYBA-Tenant: <tenant-id>
X-HYBA-Actor: <authenticated-principal>
```

Required JSON:

```json
{
  "operation": "security.evaluate",
  "resource": "container/client-data",
  "payload": {},
  "observation": {}
}
```

PYTHIA requires `observation` and obtains intelligence evidence from its local TOE
bridge. Enterprise obtains evidence from its local intelligence adapter. The
portable package never calls across repositories.

Response semantics:

- `200`: Guardian allowed the request.
- `400`: malformed or incomplete boundary input.
- `402`: subscription required; response includes `subscription_url`.
- `403`: entitlement or policy denied the request.
- `503`: required repository-local intelligence was unavailable.

## Entitlement format

Version 2 entitlements are tenant-bound, actor-bound, capability-scoped and
time-bounded signed documents. `X-HYBA-Actor` is accepted only when that exact
identity is present in the signed entitlement; it is no longer a standalone
trust assertion.

HMAC-SHA256 is the implemented application-token boundary. Production key
custody, rotation and issuance remain control-plane responsibilities and do not
constitute HSM/FIPS validation.

Entitlement verification, tenant/actor binding, operation policy and payload
ceiling checks all execute before the Enterprise intelligence or PYTHIA TOE
provider is invoked.