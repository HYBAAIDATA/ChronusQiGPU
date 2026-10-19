# 02 — Schema Version Lineage

## Constants

| Symbol | Value | Meaning |
| :--- | ---: | :--- |
| `THESEUS_FORMAT_VERSION` | `1` | Custody envelope / on-disk record format |
| `OVID_TRANSFORM_V1` | `1` | Fold/unfold algorithm lineage |

## Rules

1. **No silent reinterpret.** Bytes written under format `N` are read only by decoders that explicitly support `N`.
2. `format_version` is stored on every `CustodyEnvelope`.
3. `ovid_transform_version` is stored when payload was produced via Ovid registry; unknown versions raise `SchemaVersionError`.
4. Migrations are **explicit** functions (future format 2+), never “try decode as v1 then v2.”
5. Journal records carry the same version fields for recover-time validation.

## Lineage policy

```
v1 (current) ──explicit migrate──► v2 (future)
       │
       └── reject if reader.max < record.version
```

## Canonical bytes

`canonical_manifest_bytes(envelope)` produces a stable UTF-8 JSON encoding (sorted keys, no whitespace variance) used for HMAC input. Changing canonicalization requires a new `format_version`.
