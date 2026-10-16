**HYBA \| EUCLID**
<callout color="blue_bg">
	**Status: implemented, validated, internally verified — 19 July 2026.** The Federation layer — the external nervous system — is implemented as the architectural layer above delegation and orchestration. Three components govern secure multi-organism coordination: zero-disclosure chronicle verification, trust-weighted remote dispatch, and weighted supermajority telemetry consensus.
</callout>
## Architectural Position
```javascript
┌─────────────────────────────────────────┐
│           FEDERATION                     │
│  (external nervous system)               │
│  ┌─────────────────────────────────┐    │
│  │ FederatedChronicleVerifier      │    │
│  │ FederatedDispatcher              │    │
│  │ TelemetryConsensusEngine         │    │
│  └─────────────────────────────────┘    │
└────────────────┬────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│           TASK ORCHESTRATOR              │
│  (goal → subtask DAG → execution)        │
└────────────────┬────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│           GOVERNED DELEGATION            │
│  (organ registry → arbitration → gates)  │
└─────────────────────────────────────────┘
```
## Component 1: Cross-Instance Chronicle Validation
**Design challenge:** How do independent peer nodes verify remote execution integrity without requiring full disclosure of localized payload data?
**Answer: Zero-disclosure verification via checkpoint roots and HMAC signatures.** Only Merkle accumulator hashes and cryptographic signatures are exposed to the federated network — never raw execution data, internal state, or event payloads.
### `RemoteCheckpointProof`
A signed proof that a remote peer has executed tasks sequentially and without alteration in a given chronicle segment:
<table header-row="true">
<tr>
<td>Field</td>
<td>Type</td>
<td>Purpose</td>
</tr>
<tr>
<td>`checkpoint_id`</td>
<td>str</td>
<td>Unique identifier on the remote peer</td>
</tr>
<tr>
<td>`accumulator_hash`</td>
<td>str</td>
<td>Merkle accumulator sealing the segment</td>
</tr>
<tr>
<td>`predecessor_checkpoint_hash`</td>
<td>str</td>
<td>Previous checkpoint's accumulator (chain link)</td>
</tr>
<tr>
<td>`event_count`</td>
<td>int</td>
<td>Number of events in this segment</td>
</tr>
<tr>
<td>`signature`</td>
<td>str</td>
<td>HMAC-SHA256 of serialized payload</td>
</tr>
<tr>
<td>`peer_identity`</td>
<td>str</td>
<td>Public identifier of the producing node</td>
</tr>
</table>
### `FederatedChronicleVerifier`
**Genesis bootstrap:** The first proof from a peer must have `predecessor_checkpoint_hash = "0" * 64` — the genesis sentinel. This establishes the trust boundary cleanly.
**Chain continuity:** Each subsequent proof must link to the last known accumulator hash for that peer. A broken chain link is rejected — no silent acceptance of gaps.
**Peer lifecycle:** `TRUSTED → PROBATIONARY → SUSPENDED`. Suspended peers have all proofs rejected. Probationary peers are tracked but flagged.
**Verification log:** Immutable append-only log of every verification attempt with peer identity, checkpoint ID, accumulator hash, pass/fail, and reason.
### Validation Results
- ✅ Signature verification: valid proof accepted, tampered proof rejected
- ✅ Chain continuity: consecutive proofs with correct predecessor links accepted
- ✅ Genesis boundary: proofs with non-genesis predecessor on first contact rejected
- ✅ Suspended peer: all proofs from suspended peers rejected
## Component 2: Federated Organ Dispatch & Remote Integration
**Design challenge:** When all local organs in a domain are degraded or quarantined, how does the organism request dispatch to a remote peer? How does the local `WorldIntegrationGate` evaluate state transitions from untrusted infrastructure?
**Answer: Trust-weighted peer selection, EXTERNAL_SUBSYSTEM evidence, and reputation dynamics.**
### `FederatedDispatcher`
**Trust threshold:** `MIN_TRUST_WEIGHT = 0.6`. Peers below this threshold are rejected for dispatch — the organism will not delegate to untrusted infrastructure.
**Dispatch pipeline:**
1. Trust assessment — peer must exceed minimum trust weight
2. Envelope packaging — domain + task payload
3. Network transmission — via `FederatedNetworkInterface` (abstract; swappable for REST/gRPC in production)
4. EXTERNAL_SUBSYSTEM validation signal construction — the result originates from outside local scope
5. Integration gate verification — via `validate_integration()` on `WorldIntegrationGate`
6. Reputation adjustment — +0.05 on success, −0.20 on failure
**Reputation dynamics:** Trust evolves with observed behaviour. Successful dispatches slowly build trust. Failures rapidly erode it — the asymmetry penalizes unreliability.
**Integration model:** The `validate_integration` method on `WorldIntegrationGate` (added via `extend_gate_with_federation`) handles federation differently from local execution:
- **Truth gate:** Carries `EXTERNAL_SUBSYSTEM` evidence from the validation signal
- **Causal gate:** Carries `EXTERNAL_SUBSYSTEM` — organ and domain provenance from remote peer
- **Coherence gate:** Internal heuristic — local system verifies result integrity
- **Feedback gate:** Internal heuristic — local system did not observe remote execution, accepts with honest limitation noted
### Validation Results
- ✅ Trust-weighted dispatch: peer with trust 0.75 dispatches successfully
- ✅ Low-trust rejection: peer with trust 0.40 is rejected before transmission
- ✅ Reputation penalty: failure reduces trust by 0.20
- ✅ Result integrity: remote result `{'result': 49, 'method': 'remote_math'}` integrated correctly
## Component 3: Consensus on Truth Layer Telemetry
**Design challenge:** When multiple peer nodes report contradictory values for the same external integration point, how do we resolve the discrepancy?
**Answer: Weighted supermajority voting with cryptographic claim verification.**
### `TelemetryClaim`
A signed claim carrying: `peer_id`, `telemetry_key`, `observed_value`, `timestamp`, `signature`. Claims are HMAC-signed — only verifiable by peers with the shared secret.
### `TelemetryConsensusEngine`
**Three-stage resolution:**
1. **Cryptographic filter** — verify claim signatures against registered peer secrets; discard forged claims
2. **Reputation filter** — discard claims from peers below `MIN_REPUTATION` (0.3)
3. **Weighted supermajority** — group assertions by value, weight by peer trust; require ≥ 0.67 of active weight to establish consensus
**Fail-closed:** If no supermajority emerges, the state remains unresolved. The system does not invent a value — it reports "no consensus" and awaits further evidence.
**Reputation dynamics:** Peers that consistently provide outlier claims see their reputation erode through manual `update_reputation()` — consensus outcomes inform trust adjustments.
### Validation Results
- ✅ Supermajority threshold: 3 equal-weight peers with 2 agreeing = 0.667 weight ratio, below 0.67 → correctly fails to achieve consensus (fail-closed)
- ✅ Three-way split: 0.33 ratio → correctly fails
- ✅ Signature verification: forged claims are discarded
- ✅ Reputation filter: claims from peers below MIN_REPUTATION are excluded
## Canonical Files
<table header-row="true">
<tr>
<td>File</td>
<td>Lines</td>
<td>Purpose</td>
</tr>
<tr>
<td>`euclid/federation.py`</td>
<td>\~700</td>
<td>Complete federation layer — verifier, dispatcher, consensus, gate extension, health report</td>
</tr>
<tr>
<td>`euclid/delegation.py`</td>
<td>\~800</td>
<td>V2 delegation with Merkle checkpoints, veto recovery, EvidenceSource (federation dependency)</td>
</tr>
<tr>
<td>`euclid/task_orchestrator.py`</td>
<td>\~300</td>
<td>Task Orchestrator (the layer below federation)</td>
</tr>
</table>
## Design Decisions
### HMAC vs. Asymmetric Crypto
The pseudocode specifies `cryptography.verify_signature()` with public keys. The implementation uses HMAC-SHA256 with shared secrets. This is a conscious simplification for the laboratory environment:
- HMAC is deterministic and dependency-free
- Asymmetric crypto (Ed25519) is architecturally correct for production but requires the `cryptography` library
- The architectural interface is identical — only the primitive implementation differs
- Production migration: swap `hmac.new().hexdigest()` for `Ed25519.sign()` / `Ed25519.verify()`
### Network Abstraction
`FederatedNetworkInterface` is an abstract simulation. Production replacement: REST client, gRPC stub, or WebSocket handler. The simulation allows testing the full federation pipeline without requiring network infrastructure.
### Consensus Threshold
0.67 supermajority is intentionally strict. With 3 equal-weight peers, all 3 must agree to reach supermajority (1.0 \> 0.67). With 5 peers, 4 must agree (0.8 \> 0.67). This is appropriate for a security-sensitive coordination layer where false consensus is more dangerous than deferred resolution.
## Claim Boundaries
- Federation is simulated in-process — not a distributed deployment
- HMAC signatures are cryptographic but not production-grade asymmetric authentication
- Network communication is abstracted — no real REST/gRPC listener exists
- The trust registry is local — no distributed PKI or certificate authority
- Telemetry consensus is deterministic weighted voting — not Byzantine Fault Tolerance
- Federation is the external nervous system specification — not a deployed multi-node network
## Next Architectural Layer
Federation completes the three-layer organism architecture:
1. **Delegation** — internal nervous system (single task → organ)
2. **Orchestration** — goal coordination (multi-step goal → organs)
3. **Federation** — external nervous system (multi-organism coordination)
The next boundary beyond federation is the **Inter-Organism Protocol** — standardized contracts for federation across heterogeneous organism types, trust bootstrapping for unknown peers, and cross-implementation chronicle compatibility.
\</content\>