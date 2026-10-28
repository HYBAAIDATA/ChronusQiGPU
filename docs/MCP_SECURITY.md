# MCP security and evidence integrity

HYBA/EUCLID retains authority. Narrow AI receives zero credit, decision rights,
or proof standing. Exact identity checks and SHA256d target comparisons remain
the validity owners; signing evidence never grants consensus or execution rights.
`theorem_proven` is deliberately always false, not an unused success flag.

## Trust boundary

The stdio server and in-process client are local tool interfaces, not AL HARAS
authorization implementations. Run them only under a governed host/gateway with
tenant isolation, least privilege, access leases, resource limits and protected
audit storage. Do not expose stdio through an unauthenticated network bridge.
Manifest status markers are guidance, not containment. Failed validation or a
missing scaler never grants access or fabricates a successful result.

Inputs matching `n` are bounded to 0–10000 inclusive. Scaler complexity must be
finite and within [0,1]. These are per-call safeguards, not global quotas: hosts
still need request-size, rate, concurrency, session-duration and memory limits.
The client retains evidence in memory until session close.

## Pack format and signing procedure

Packs contain session ID, tools called, evidence count, full handshake and tool
arguments/outputs, sovereignty fields, timestamp and `signature_algorithm`.
Evidence can contain sensitive operator data: apply retention, encryption at rest
and access controls; HMAC does not encrypt anything.

Canonical JSON uses Python `json.dumps(value, sort_keys=True,
separators=(",", ":"), allow_nan=False)` encoded as UTF-8. Default ASCII escaping
is retained. Field order and whitespace in a transported JSON document do not
matter after parsing; preserve all values and numeric types.

1. Build the payload excluding `evidence_digest` and `evidence_signature`,
   with `signature_algorithm` set to `HMAC-SHA256`.
2. Set `evidence_digest` to lowercase hex SHA-256 of the canonical payload.
3. Set `evidence_signature` to lowercase hex HMAC-SHA256 of the canonical
   payload **including the digest**, using the private session key.
4. Verify using a trusted out-of-band key. `verify_evidence_pack` recomputes
   both values and uses `hmac.compare_digest`; missing/invalid tags, algorithms,
   malformed packs and wrong keys fail closed. Never accept a digest alone.

The HMAC covers actual evidence, not merely its count. A forged payload with
a recomputed public digest still fails authentication without the private key.
This is symmetric authentication, not an asymmetric digital signature or
non-repudiation: anyone who possesses the key can create a valid pack. It
authenticates the client's record, not independently attested server execution.

## Session key management and verification

`start_session()` creates a random 128-bit ID via `secrets.token_hex(16)` and
a private random 256-bit key via `secrets.token_bytes(32)`. The default key is
ephemeral; verify with `client.verify_evidence_pack(pack)` while the session is
active. It checks both the key and the active session identity.

For verification after close, supply a per-session key from an approved secret
manager and retain it separately under the operator's key-retention policy:

```python
import secrets
from hyba_mcp.client import HybaMCPClient, verify_evidence_pack

key = secrets.token_bytes(32)  # Provision/retain securely out of band in production.
client = HybaMCPClient()
session_id = client.start_session(signing_key=key).session_id
client.call_tool("cassini", {"n": 15})
pack = client.end_session()
assert verify_evidence_pack(pack, key, expected_session_id=session_id)
```

Keys must be `bytes` of at least 32 bytes; length checks do not guarantee entropy,
so do not use passwords or literal example keys. Never serialize keys into packs,
logs, source, manifests, session reprs, or untrusted tool arguments. Persist any
session-to-key mapping in the trusted secret store, not alongside public evidence.

Starting a second session while one is active is rejected to avoid accidental
loss of its key/evidence. `end_session()` releases the client's session and key
references even if packaging fails. Python immutable bytes cannot guarantee
memory zeroization; caller-held keys remain the caller's responsibility.
New default sessions rotate keys automatically. After suspected compromise,
revoke trust in affected packs, provision fresh keys, and investigate custody.

Authentication alone does not stop replay. The consumer must bind the trusted
session ID, enforce freshness with its own clock/timestamp policy, track accepted
session/digest pairs, and reject replays. A valid HMAC is never AL HARAS approval.
Legacy digest-only packs are unauthenticated and must not be promoted by merely
recomputing their digest.
