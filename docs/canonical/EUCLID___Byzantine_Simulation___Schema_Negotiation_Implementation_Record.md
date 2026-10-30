# EUCLID — Byzantine Simulation & Schema Negotiation Implementation Record

**HYBA | EUCLID**

<aside>

**Status: implemented, validated — 19 July 2026.** Two systems implemented in parallel: the Byzantine and Partition Simulation Harness (`euclid/simulation.py`) and the Self-Directed Schema Negotiation Engine (`euclid/schema_negotiation.py`). Three validation tests (partition integrity, Byzantine consensus filter, schema negotiation handshake) all pass.

</aside>

## Part 1: Byzantine and Partition Simulation Harness

### `SimulatedNetwork`

Simulates multi-node IOP network with configurable link profiles:

- **Partition isolation:** Each node has a `partition_id`. Nodes in different partitions cannot communicate — transmission returns `TRANSMISSION_FAILED: Network partition block`.
- **Packet loss:** Configurable per-link `packet_loss_rate` (0.0–1.0). Messages are randomly dropped at the specified rate.
- **Latency spikes:** Configurable per-link `latency_sec`. Injected before delivery (capped at 50ms in simulation).
- **Node offline:** Missing receiver nodes trigger transmission failure.

### `ByzantineNodeProxy`

Simulates malicious or faulty behavior:

- `generate_byzantine_telemetry()`: Injects corrupted data — numeric values scaled by 10×, strings prefixed with `CORRUPTED_`
- `sign_forged_claim()`: Generates structurally valid HMAC signatures over incorrect data — tests consensus engine's ability to filter based on reputation + supermajority
- `sign_honest_claim()`: Generates valid claims for comparison — honest nodes coexist with Byzantine proxies

## Part 2: Self-Directed Schema Negotiation Engine

### `SchemaNegotiator`

Dynamic translation rules for heterogeneous organism schemas:

| Transform | Description | Example |
| --- | --- | --- |
| `RENAME` | Maps a key to a new identifier | `temperature_c` → `temperature_f` |
| `SCALE` | Multiplies numerical values | 25.0 × 1.8 → 45.0 (°C → °F) |
| `INJECT_DEFAULT` | Fills missing values with constants | Missing `unit` → `"C"` |

**Safety guarantees:**

- `SCALE` parameters must be numeric — non-numeric parameters rejected
- `INJECT_DEFAULT` must have a non-None parameter — missing defaults rejected
- Unmapped fields are preserved to prevent context loss
- Destructive type casting is blocked

### `EnhancedIOPRouter`

Extends the IOP Router with schema negotiation:

- Intercepts `NEGOTIATE` envelopes with `schema_proposal` — registers translation rules
- Auto-translates `DISPATCH` payloads when `source_schema_id ≠ target_schema_id`
- Returns `VETO` on schema mismatch or invalid translation

## Validation Results

### Test 1: Partition Integrity

```
Nodes A, B, C in partition 1. Node C isolated to partition 2.
A → C dispatch: TRANSMISSION_FAILED (partition block) ✅
A → B dispatch: TRANSMISSION_SUCCESS ✅
Tracker timeout: has_timed_out(0.1s) after 2s → True ✅
```

### Test 2: Byzantine Consensus Filter

| Scenario | Honest | Byzantine | Consensus | Result |
| --- | --- | --- | --- | --- |
| 3H + 2B | 3 × 0.72 | 2 × 7.2 (forged) | weight 3/5 = 0.600 | Fail-closed (0.600 < 0.67) ✅ |
| 5H + 2B | 5 × 0.72 | 2 × 7.2 (forged) | weight 5/7 = 0.714 | Consensus achieved (0.72) ✅ |
| Byzantine-only (low rep) | 0 | 2 × 7.2 | rep < 0.3 filtered | No valid claims ✅ |

The Byzantine filter correctly:

- Groups forged claims separately (10× values form a distinct assertion group)
- Requires supermajority (0.67) — 60% is not enough
- Filters low-reputation nodes (rep < 0.3 excluded)
- Returns fail-closed when consensus threshold is not met

### Test 3: Schema Negotiation Handshake

```
Organism A (Celsius schema v1) → Organism B (Fahrenheit schema v2)

1. A proposes: SCALE temperature_c → temperature_f × 1.8
2. B accepts: SCHEMA_MAPPING_ACCEPTED ✅
3. A dispatches: {temperature_c: 25.0, unit: "C"}
4. B auto-translates: {temperature_f: 45.0, unit: "C"} ✅
5. Unmapped field (unit) preserved via RENAME ✅
```

## Canonical Files

| File | Lines | Purpose |
| --- | --- | --- |
| `euclid/simulation.py` | ~80 | SimulatedNetwork, ByzantineNodeProxy — partition/latency/packet-loss/byzantine simulation |
| `euclid/schema_negotiation.py` | ~90 | SchemaNegotiator, EnhancedIOPRouter — dynamic schema translation with safety guarantees |
| `euclid/types.py` | ~80 | Foundation types: IOPEnvelope, IOPExecutionTracker, TelemetryConsensusEngine, SimpleIOPRouter |

## Integration with Existing Architecture

These systems stress-test the four-layer organism stack:

| Layer | Tested By |
| --- | --- |
| **IOP** | `SimulatedNetwork.transmit()` — partition/packet-loss/latency on IOP envelopes |
| **Federation** | `ByzantineNodeProxy` — forged telemetry claims against `TelemetryConsensusEngine` |
| **Orchestration** | `IOPExecutionTracker` — timeout-induced BREACHED state on partition isolation |
| **Delegation** | `EnhancedIOPRouter` — dispatch routing with schema translation before organ execution |

## Claim Boundaries

- The simulation is in-process — not a real distributed network
- HMAC signatures are cryptographic but not production-grade asymmetric authentication
- Byzantine proxies test consensus robustness but do not simulate all BFT attack vectors
- Schema negotiation handles RENAME/SCALE/INJECT_DEFAULT — not complex type coercion or nested structure transformation
- All tests are internal laboratory validations — not external security audits

</content>