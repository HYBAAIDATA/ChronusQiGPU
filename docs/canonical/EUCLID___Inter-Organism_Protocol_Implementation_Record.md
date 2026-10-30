# EUCLID — Inter-Organism Protocol Implementation Record

**HYBA | EUCLID**

<aside>

**Status: implemented, validated — 19 July 2026.** The Inter-Organism Protocol (IOP) is the architectural layer above Federation. It establishes standardized contracts across *heterogeneous* organism types — different models, internal registries, or hardware profiles — using schematized envelopes, cryptographically signed SLAs, Macaroon-style capability tokens, and an asynchronous event-driven lifecycle.

</aside>

## Architectural Position

```
┌─────────────────────────────────────────────┐
│        INTER-ORGANISM PROTOCOL (IOP)         │
│  (heterogeneous cross-organism contracts)    │
│  ┌───────────────────────────────────────┐   │
│  │ IOPEnvelope  IOPContract  IOPRouter   │   │
│  │ CapabilityToken  CapabilityRegistry   │   │
│  │ IOPExecutionTracker                   │   │
│  └───────────────────────────────────────┘   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────┴──────────────────────────┐
│              FEDERATION                      │
│  (homogeneous multi-organism coordination)   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────┴──────────────────────────┐
│           TASK ORCHESTRATOR                  │
│  (goal → subtask DAG → execution)            │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────┴──────────────────────────┐
│           GOVERNED DELEGATION                │
│  (organ registry → arbitration → gates)      │
└─────────────────────────────────────────────┘
```

## Structural Pitfalls Addressed

IOP is designed against the concrete pain points of first-generation multi-agent frameworks:

| Pitfall | LangGraph / AutoGen / CrewAI | IOP Solution |
| --- | --- | --- |
| **Semantic Drift** | Raw text prompts between agents; a minor prompt shift breaks parsing | Schematized `IOPEnvelope` — strictly typed, never unstructured text |
| **Epistemic Blindness** | Agent B says "done" → Agent A trusts it | `IOPContract` with cryptographic provider signature + `evaluate_completion()` auto-breach detection |
| **Implicit Over-Privilege** | Broad shell/filesystem access without caveats | `IOPCapabilityToken` — Macaroon-style tokens with caveat-based attenuation |
| **Synchronous Chatty Protocols** | Blocking chat loops create latency and state-sync bottlenecks | `IOPExecutionTracker` — async event-driven lifecycle, no blocking |

## Component 1: IOP Envelope — Eliminating Semantic Drift

### `IOPMessageType`

Six strictly typed message kinds — never unstructured text:

- `NEGOTIATE` — SLA handshake: "can you do X under bounds Y?"
- `DISPATCH` — Task execution request with capability token
- `RESOLVE` — Task success with cryptographic state proof
- `VETO` — Fail-closed rejection with categorized reason
- `ADVERTISE` — Capability announcement
- `ACKNOWLEDGE` — Protocol acknowledgement

### `IOPEnvelope`

Every envelope carries: `message_id`, `sender_id`, `receiver_id`, `message_type`, structured `payload` (dict, never raw string), optional `IOPCapabilityToken`, and HMAC `signature`. Deterministic serialization via JSON with sorted keys prevents signature mismatch from key ordering.

### Validation Results

- ✅ Envelope signing and verification: HMAC-SHA256
- ✅ Tamper detection: modified payload fails verification
- ✅ Capability token binding: token attached to DISPATCH envelopes only

## Component 2: IOP Capability Token — Preventing Over-Privilege

### `IOPCapabilityToken`

Macaroon-inspired tokens with caveat-based attenuation. Unlike bearer tokens (JWT-style), capability tokens carry explicit constraints:

```python
token = IOPCapabilityToken.issue(
    token_id="cap_001",
    issuer_id="org_A",
    target_domain="math",
    caveats=["max_latency_sec < 30", "risk_level == low"],
    issuer_secret=secret,
    ttl_seconds=300,
)
```

- **Temporal bounds:** `not_before` / `not_after` enforced via `is_valid()`
- **Domain scoping:** Token is valid only for the specified `target_domain`
- **Caveat enforcement:** Router checks domain match and caveat satisfaction before dispatch
- **HMAC verification:** Token signature proves it was issued by the claimed organism

## Component 3: IOP Contract — Preventing Unverifiable Self-Reporting

### `IOPContract`

A mutually signed Service Level Agreement. The provider (Organism B) cryptographically commits to specific bounds:

| Bound | Type | Example |
| --- | --- | --- |
| `max_latency` | float (seconds) | 5.0 |
| `min_confidence` | float (0–1) | 0.7 |
| `required_evidence_source` | str | "EXTERNAL_SUBSYSTEM" |
| `state_proof_requirement` | str | "MERKLE_ROOT" |

**`is_sla_satisfied()`** — automatic breach detection. The organism does not need to manually detect the breach — the contract enforcement is automatic. Three checks: latency, confidence, evidence source. Any violation → `SLA BREACHED`.

### Validation Results

- ✅ Provider signing: `sign_provider()` produces verifiable HMAC
- ✅ SLA satisfaction: 0.015s, 0.85 confidence, EXTERNAL → PASSED
- ✅ SLA breach: 10.0s, 0.60 confidence, INTERNAL → BREACHED (all three bounds violated)

## Component 4: IOP Execution Tracker — Asynchronous Event Routing

### State Machine

```
PROPOSED ──(negotiation accepted)──→ ACTIVE ──(dispatch)──→ RUNNING
    │                                                         │
    ├──(rejected/timeout)──→ TERMINATED                       ├──(SLA satisfied)──→ COMPLETED
    │                                                         ├──(SLA breached)──→ BREACHED
    │                                                         └──(explicit stop)──→ TERMINATED
```

### `IOPExecutionTracker`

- Event-sourced: every state transition is recorded as an immutable `IOPExecutionEvent` with predecessor-linked hash chain
- `transition()` enforces valid transitions — invalid transitions are rejected
- `evaluate_completion()` automatically transitions to BREACHED if SLA bounds are violated
- `has_timed_out()` checks whether execution exceeded the SLA latency bound
- `to_dict()` exports full tracker state for audit

### Validation Results

- ✅ Valid lifecycle: PROPOSED → ACTIVE → RUNNING → COMPLETED
- ✅ Invalid transition blocked: COMPLETED → RUNNING rejected
- ✅ SLA auto-breach: violations transition to BREACHED automatically

## Component 5: Semantic Capability Advertising

### `CapabilityRegistry`

Organisms advertise domain expertise, confidence thresholds, and supported schemas WITHOUT disclosing internal `OrganRegistry` topology — no organ count, no organ identities, no degradation states exposed.

### `CapabilityAdvertisement`

| Field | Purpose |
| --- | --- |
| `supported_domains` | Which research domains this organism can handle |
| `min_confidence_threshold` | The minimum confidence this organism commits to |
| `max_latency_commitment` | The maximum latency this organism commits to |
| `supported_schemas` | Protocol versions supported (e.g., "IOP/v1") |
| `current_load` | Self-reported load (0.0–1.0) — enables least-loaded routing |

Advertisements are HMAC-signed and have a configurable TTL (default 60s). `get_capable_peers()` returns fresh advertisements from organisms that support a given domain at a given confidence, sorted by load.

## Component 6: IOP Router — End-to-End

### `IOPRouter`

Handles inbound envelope routing with cryptographic verification and capability enforcement:

1. **Verify cryptographic integrity** — envelope signature against peer secret
2. **Route by message type** — NEGOTIATE → contract creation, DISPATCH → capability validation + execution, RESOLVE → tracker completion, VETO → breach logging
3. **Outbound dispatch** — `dispatch_to_organism()`: negotiate → issue capability token → dispatch → evaluate SLA

### Validation Results

- ✅ Negotiation: contract created and signed by provider, ACKNOWLEDGE returned
- ✅ Dispatch: capability token validated, task executed, RESOLVE returned with proof hash
- ✅ Outbound dispatch: full pipeline from contract to SLA evaluation
- ✅ Untrusted sender: VETO returned for unknown peer
- ✅ Health report: status, active contracts, registered peers

## Complete Architecture Stack

| Layer | Module | Function |
| --- | --- | --- |
| **IOP** | `euclid/iop.py` | Heterogeneous cross-organism contracts |
| **Federation** | `euclid/federation.py` | Homogeneous multi-organism coordination |
| **Orchestration** | `euclid/task_orchestrator.py` | Goal → subtask DAG → execution |
| **Delegation** | `euclid/delegation.py` | Organ registry → arbitration → gates |

## Design Decisions

### JSON-LD Readiness

The `IOPEnvelope.payload` is a structured dict with deterministic serialization. Adoption of JSON-LD `@context` fields is architecturally compatible — add a `@context` key to the payload without changing the envelope structure. This allows semantic interoperability with standards-based systems.

### HMAC for Signatures

Consistent with the Federation layer, IOP uses HMAC-SHA256 for all cryptographic operations. Production migration to Ed25519 requires swapping `hmac.new().hexdigest()` for `Ed25519.sign()` / `Ed25519.verify()` — the interface is identical.

### Capability Token TTL

Default 300 seconds. Tokens are short-lived by design — long-lived tokens create a larger window for misuse. The router can refresh tokens mid-session via a new NEGOTIATE cycle.

## Claim Boundaries

- IOP is a laboratory specification — not a deployed cross-organism network
- HMAC-SHA256 signatures are cryptographic but not production-grade asymmetric authentication
- The network layer is simulated — no real REST/gRPC listener exists
- Capability tokens use shared secrets, not PKI
- The IOP Router's `dispatch_to_organism()` simulates the full pipeline — production requires actual network transport
- IOP is the heterogeneous contract layer — not a deployed multi-organism runtime

## Architectural Invariant Checklist

- [x]  **No Unstructured Instructions** — IOP messages are strictly typed; payload is always structured dict
- [x]  **Cryptographic Bound Alignment** — Contracts are mutually signed; no execution without pre-validated SLA
- [x]  **Asynchronous Execution States** — Sender registers a tracker and yields; no blocking
- [x]  **Strict Privilege Boundaries** — Capability tokens with caveats prevent unauthorized domain access

</content>