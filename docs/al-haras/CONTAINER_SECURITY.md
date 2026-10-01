# Container Security and Data-Custody Runbook

## Required environment

```text
AL_HARAS_SUBSCRIPTION_KEYS={"2026-01":"<minimum-32-byte-secret>"}
AL_HARAS_ISSUER=hyba-subscriptions
AL_HARAS_DATA_DIR=/var/lib/hyba/al-haras
AL_HARAS_POLICY_VERSION=al-haras.policy.v1
AL_HARAS_CAPABILITY=hyba.security
AL_HARAS_MAX_PAYLOAD_BYTES=1048576
AL_HARAS_SUBSCRIPTION_URL=/contact?product=hyba-security
# Corrupt-spool recovery: rename damaged ledgers aside and resume on a fresh
# chain whose first record is the recovery event (default true). Set to false
# to fail startup hard instead.
AL_HARAS_AUDIT_QUARANTINE=true
# Optional L-HRAS Guardian layer (see docs/al-haras/GAP_ANALYSIS.md).
# Point at an L-HRAS config.toml (l_hras/config.example.toml); the trust
# root, threat model, policy bundle, and threshold provenance live there.
# Enabling without a valid config fails closed with a 503.
AL_HARAS_ENABLE_LHRAS=false
AL_HARAS_LHRAS_CONFIG=/etc/hyba/lhras/config.toml
```

PYTHIA additionally sets:

```text
AL_HARAS_REQUIRE_INTELLIGENCE_EVIDENCE=true
```

## Container controls

1. Run as a non-root UID with a read-only root filesystem.
2. Mount `AL_HARAS_DATA_DIR` as the only writable AL HARAS volume.
3. Set the audit directory to mode `0700`; records are created mode `0600`.
4. Inject subscription keys from a secret manager, never an image layer or Git.
5. Deny cross-tenant volume mounts and network namespaces.
6. Bound request bodies at the reverse proxy and AL HARAS policy.
7. Export ledger records to customer-controlled evidence storage; do not call the
   local JSONL spool immutable/WORM.
8. Rotate keys by adding the new key id, issuing new entitlements, then removing
   the old key only after its final entitlement expiry.
9. Use a Linux/POSIX volume: persistent mode requires `flock`-compatible locking.
10. Never place the ledger on storage that ignores POSIX advisory locks.

## Recovery

The guardian is built lazily on the first request that reaches it. At that
point AL HARAS loads and verifies the complete local chain; when
`AL_HARAS_AUDIT_QUARANTINE` is enabled (the default), a malformed or corrupt
spool is renamed to `<file>.corrupt-<timestamp>`, a fresh chain is opened, and
its first record is an `audit_quarantined` recovery event pointing at the
quarantined file. With quarantine disabled the same corruption fails startup.
On platforms without POSIX `flock` (for example a Windows dev host) the PYTHIA
wiring falls back to an in-memory chain and `public_status` reports
`audit_durable: false`; treat that mode as non-production evidence only.

Each append verifies only the durable tail record under an exclusive
cross-process lock — cost stays constant in ledger length and independent
writers cannot fork the chain — while the `records` property still re-verifies
the entire chain on read. Preserve the ledger volume and treat any gap, hash
mismatch, or `audit_quarantined` event as an integrity incident.