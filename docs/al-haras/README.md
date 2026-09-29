# AL HARAS Documentation

- [Architecture](ARCHITECTURE.md)
- [Subscription and routing](SUBSCRIPTION_AND_ROUTING.md)
- [Container security runbook](CONTAINER_SECURITY.md)
- [Threat model](THREAT_MODEL.md)
- [Exact math-folding reference](MATH_FOLDING.md)

## Evidence boundary

This change supplies a portable package, repository-local adapters, API routes,
subscription enforcement, tenant binding, hash-only audit evidence and tests.
It does not establish external certification, independent penetration testing,
HSM/FIPS validation, immutable external storage, or production authorization.