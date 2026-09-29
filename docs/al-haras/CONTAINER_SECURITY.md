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

On restart, AL HARAS loads and verifies the complete local chain before accepting
traffic, recovers the durable tail hash and refuses startup on malformed JSON or
chain corruption. Every append re-reads the durable head while holding an
exclusive cross-process lock, preventing independent workers from forking the
chain. Preserve the ledger volume and treat any gap or hash mismatch as an
integrity incident. `ACTION_REQUESTED`,
`ACTION_ACKNOWLEDGED`, and `RECOVERY_VERIFIED` remain distinct states.