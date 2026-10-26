# 03 — Provenance & Authenticity

## Two distinct properties

| Property | Mechanism | Detects |
| :--- | :--- | :--- |
| **Integrity** | SHA-256 `content_digest` over payload bytes | Accidental corruption, bit rot |
| **Authenticity** | HMAC-SHA256 over **canonical manifest** | Tampering when key is secret |

Integrity alone does **not** prove a record came from an authorized writer. Authenticity alone does not replace content addressing for heal.

## Custody events

Each mutating action appends a `CustodyEvent`:

- `event_type`: put | delete | heal | recover | backup | restore | deny
- `record_id`, `generation`, `ts`, `content_digest`, optional `note`
- Events are queryable via `provenance(record_id=...)`

## Hooks to AL HARAS

- Theseus emits evidence through `SecurityHook.after_put` / `after_heal`.
- `AlHarasEvidenceAdapter` **only forwards** structured evidence; it does not evaluate guardian policy packs inside Theseus.
- Policy decision (allow/deny) is `before_put` return value from the external authority.

## Key material

- HMAC key is provided by the composition root (caller/environment).
- Missing key in authenticated mode → fail-closed at compose/put.
- Key rotation implies re-MAC (explicit maintenance), not silent dual-accept.
