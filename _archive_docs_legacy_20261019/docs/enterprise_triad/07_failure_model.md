# 07 — Failure Model (Typed Errors)

All custody failures map to typed exceptions in `aethel.enterprise.errors` (and substrate `aethel.errors` where overlapping).

| Error | When |
| :--- | :--- |
| `AuthorityBoundaryError` | Caller/owner attempts cross-authority operation (e.g. demand Chronus-owned digest change, geodesic absorbed path) |
| `UnrecoverableCustodyError` | No intact replica; heal impossible |
| `ResourceExhausted` | Payload/records/tenant byte quota exceeded |
| `ConcurrencyConflict` | Generation or idempotency conflict |
| `SchemaVersionError` | Unknown or unsupported format/transform version |
| `AuthenticityError` | HMAC verify failed |
| `ReadOnlyModeError` | Mutation under read-only degradation |
| `EngineUnavailable` | Geodesic/Intelligence engine not present (outside custody) |

## Principles

1. **No bare `Exception`** at the enterprise API boundary for declared modes.
2. **No silent empty success** on missing geodesic or failed auth.
3. Telemetry never invents counters to “look healthy.”
4. Messages may include `record_id` / tenant but not secret key material.
