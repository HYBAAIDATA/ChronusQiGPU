# AL HARAS Threat Model

| Threat | Implemented control | Residual boundary |
|---|---|---|
| Token forgery | HMAC-SHA256 and constant-time verification | Key custody is external |
| Cross-tenant use | Exact tenant binding in signed claims | Subscription issuer must authenticate enrolment |
| Actor spoofing | Exact actor/service identity binding in signed v2 claims | Identity proofing remains issuer-owned |
| Expired subscription | Explicit validity window | Clock integrity is platform-owned |
| Capability escalation | Exact capability and operation allowlists | Policy administration is external |
| Oversized payload | Tenant and policy byte ceilings | Reverse-proxy limit still required |
| Sensitive audit leakage | Hash-only payload recording | Application logs outside AL HARAS |
| Ledger mutation | Startup verification and hash-chain validation | Local JSONL is not independent WORM |
| Concurrent writers | POSIX exclusive lock and durable-tail reload per append | Requires lock-compatible storage |
| Intelligence outage | `503` or fail-closed evidence requirement | Availability depends on local runtime |
| Repository compromise | Branch review, CI, secret scan | Independent supply-chain assessment pending |

No claim of invulnerability, certification, physical hardware verification or
independent sovereign authorization is made by this module.