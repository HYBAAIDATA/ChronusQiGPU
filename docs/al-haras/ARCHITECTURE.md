# AL HARAS — Portable CYBER Module

AL HARAS is an importable Python package and a fail-closed security boundary for
HYBA containers. The same package is committed independently to Enterprise and
PYTHIA; neither repository imports the other.

## Runtime contract

```text
request
→ tenant + actor identity
→ signed subscription entitlement
→ tenant + actor + capability verification
→ operation + payload-bound policy
→ repository-local intelligence evidence
→ Guardian verdict
→ hash-only, tamper-evident audit record
```

Client payloads are evaluated in memory and are not written to the AL HARAS
ledger. The ledger records a SHA-256 digest, policy version, subscription
identifier, outcome and intelligence-evidence digest.

## Authority boundaries

- Authentication is not authorization.
- A subscription entitlement grants named capabilities to one tenant and named
  actor/service identities.
- Intelligence evidence informs a Guardian decision; it does not grant authority.
- An `ALLOWED` verdict is not evidence that a downstream action executed.
- Local JSONL is a durable container spool, not a WORM or independent-witness claim.
- Missing keys, expired tokens, wrong tenants and unavailable required intelligence
  fail closed.
- Entitlement and policy preflight completes before repository-local intelligence
  is invoked.
- Every boundary denial, including unavailable intelligence, emits a receipt.
- A persistent ledger is validated at startup and resumed from its durable tail.
  Corruption prevents startup; POSIX file locking serializes container processes.

## Package surface

```python
from al_haras import ALHaras, GuardianRequest
from al_haras.runtime import GuardianAPI, build_guardian
```

The framework-neutral `GuardianAPI` is used by FastAPI in Enterprise and by the
standard-library control API in PYTHIA.