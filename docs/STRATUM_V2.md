# Stratum V2 Mining Protocol

PYTHIA now contains a standards-based binary Stratum V2 **Mining Protocol**
implementation in `mining/stratum_v2.py`.

## Implemented

- Six-byte SV2 framing: little-endian `extension_type`, `message_type`, and
  U24 payload length.
- Correct channel-routing bit enforcement.
- `SetupConnection`, `SetupConnection.Success`, and `SetupConnection.Error`.
- Standard and extended mining-channel opening.
- Channel targets, extranonce prefixes, and negotiated extranonce sizes.
- Standard and extended share submission.
- `NewMiningJob` and `NewExtendedMiningJob` parsing.
- `SetNewPrevHash`, `SetTarget`, `SetExtranoncePrefix`, and share success/error
  handling.
- Exact extended-job Bitcoin header assembly from coinbase prefix/suffix and
  merkle path.
- Sequence numbers, job freshness checks, channel ownership checks, and
  fail-closed malformed-frame handling.

The client is more flexible than V1 because it supports binary standard and
extended channels, negotiated extranonce space, separate job activation, and
per-channel targets rather than V1's JSON-RPC notification model.

## Security boundary

Remote SV2 requires an authenticated Noise session under the SV2 security
specification. The implementation therefore takes a `SecureChannel` adapter
and refuses a channel that does not advertise `secure=True`. It does **not**
downgrade to plaintext TCP, substitute TLS for Noise, or label a test transport
as a pool connection. The official Stratum V2 Reference Implementation (SRI)
Noise transport can be adapted to this interface.

This is intentional production behavior: a binary codec without authenticated
transport is not a production pool client.

## Protocol scope

The Mining Protocol is the core V2 successor to Stratum V1 and can operate
without Job Declaration or Template Distribution. Those are separate SV2
subprotocols with separate roles and message families. PYTHIA does not claim
those roles are implemented merely because Mining Protocol frames exist.

## Canonical runtime integration

There is still only one miner. Pool endpoints carry an explicit protocol:
`stratum+tcp://` / `stratum+ssl://` select V1 and
`sv2://` / `stratum2+noise://` select V2. Both feed the same
`StratumRuntimeState`, `StratumProofAdapter`, PYTHIA work identity,
nonce-space leasing, CHRONUS execution, local SHA256d validation, bounded
submission queue and literal pool-outcome learning.

Canonical V2 production use is restricted to **extended mining channels** so
the negotiated extranonce namespace maps exactly onto PYTHIA's existing
collision-free work partitioning contract. Standard-channel support remains in
the codec for protocol completeness but is not a second mining execution path.

The runtime loads its authenticated transport from
`PYTHIA_SV2_CHANNEL_FACTORY=module:callable`. The factory must return a
`SecureChannel` with `secure=True`; absence, import failure or an insecure
channel makes that V2 endpoint unavailable. Failover may then try the next
configured endpoint, but the runtime never downgrades that endpoint to V1,
plaintext TCP or TLS.

No live credentials or pool-accepted share is fabricated by the contract
tests; live acceptance requires a literal pool response.