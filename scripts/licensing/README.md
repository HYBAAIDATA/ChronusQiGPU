# Lease signing tools (vendor side)

These scripts sign leases and revocation lists for the sealed-appliance
channel. They run only on HYBA's offline signing workstation. They are not
part of any distribution and are never shipped to a participant. The
verifier is `src/chronus/licensing`; the format and the order of checks are
described in [`docs/distribution/partner-distribution.md`](../../docs/distribution/partner-distribution.md).

| Script | Purpose |
| --- | --- |
| `issue_lease.py` | Validates an unsigned `hyba.lease/1` document, signs it, verifies the result end to end with the matching public key and writes the envelope as canonical JSON. Prints the SHA-256 of the output file. |
| `issue_revocations.py` | Builds and signs a cumulative `hyba.revocations/1` list, verifies it and writes it. Prints the SHA-256 of the output file. |

Both scripts refuse a private-key path inside this repository, refuse a key
file that group or others can read (POSIX), refuse to overwrite an existing
output without `--force` and exit with status 2 on any refusal or error.

## 1. Generate a signing key (offline)

On an offline workstation, with a restrictive umask, onto encrypted removable
media or into an HSM-backed export path. Never inside a working copy:

```bash
umask 077
openssl genpkey -algorithm ed25519 -aes-256-cbc -out /media/hyba-offline/hyba-lease-2026.pem
```

`-aes-256-cbc` protects the PEM with a passphrase; the scripts prompt for it.
Derive the raw 32-byte public key (base64) for the trust store:

```bash
openssl pkey -in /media/hyba-offline/hyba-lease-2026.pem -pubout -outform DER | tail -c 32 | base64
```

Trust store document (public keys only; safe to share with the build):

```json
{"schema": "hyba.trust-store/1", "keys": {"hyba-lease-2026": "<base64 of the 32-byte public key>"}}
```

The committed `src/chronus/licensing/trust_store.json` stays empty. The
production trust store is embedded at build time with
`HYBA_LEASE_TRUST_STORE=/path/to/trust_store.json` (see
[`packaging/partner/README.md`](../../packaging/partner/README.md)), so a
verifier fails closed until a build pins a key.

## 2. Custody

- Preferred: keep the key in an HSM and sign the canonical bytes there. These
  scripts read PEM files only; HSM signing must reproduce
  `chronus.licensing.canonical_bytes(lease)` and the same envelope.
- Otherwise: an encrypted PEM on offline media in a safe, used only on the
  offline workstation, with two people present for every signing session.
- Never place a private key on a CI runner, a shared drive, a ticket or in
  git. `.gitignore` ignores `*.pem` and `*.key`, but do not rely on it.
- Keep an issuance register: lease_id, serial, licensee id, kid, validity
  window and the SHA-256 printed by the tool.

## 3. Issue a lease

```bash
python scripts/licensing/issue_lease.py \
    --lease participant-01.lease-request.json \
    --key /media/hyba-offline/hyba-lease-2026.pem \
    --kid hyba-lease-2026 \
    --out participant-01.lease.json
```

Rules:

- `serial` increases for every new lease of a licensee and is never reused.
  A verifier with a state file rejects a lower serial, and a reused serial
  with different content, as `LeaseRollback`.
- Timestamps are RFC 3339 UTC with whole seconds (`2026-11-11T00:00:00Z`).
- `binding.fingerprints` are hashes collected on the participant's appliance,
  never raw identifiers. On the appliance:

  ```bash
  python -c "from chronus.licensing import collect_fingerprints, default_providers; print(sorted(collect_fingerprints(default_providers())))"
  ```

- Signed leases name the licensee: deliver them through the agreed private
  channel and do not commit them.

## 4. Revoke leases

Revocation lists are cumulative (every lease identifier revoked so far):

```bash
python scripts/licensing/issue_revocations.py \
    --ids-file revoked-lease-ids.txt \
    --key /media/hyba-offline/hyba-lease-2026.pem \
    --kid hyba-lease-2026 \
    --out revocations-2026-11-11.json
```

Deliver the newest list with every lease renewal. A verifier that uses a
state file remembers every revoked identifier it has seen, so a revoked lease
stays revoked even if a later run omits the list. Offline verification cannot
force a participant to present a list it has not received.

## 5. Rotate keys (kid)

1. Generate a new key with a new kid (for example `hyba-lease-2027`).
2. Add its public key to the trust store and ship a new build; keep the old
   kid pinned while leases signed with it are still valid.
3. Sign new leases and revocation lists with the new kid.
4. Remove the old kid in a later build once its leases have expired.

If a key is exposed, remove its kid immediately, ship a new build and reissue
every affected lease under a trusted kid. Because the trust store is embedded
at build time, removing a kid always requires a new build.
