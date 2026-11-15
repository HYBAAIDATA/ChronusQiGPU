<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:8d28b93674b07baa0c4ec09e20fd47eaa74bb52c08ab7233ef4d068b1f24b052 -->

## Search integration and readiness

The live entrypoint uses the authored geometric/Galois candidate engine and TURING exact-state lane scheduling. Install both internal distributions for a local mining run:

```bash
python -m pip install ./packages/turing '.[mining]'
python deploy/hyba-mine/bist.py
```

The Docker build includes the TURING wheel. Both the canonical entrypoint and the unattended runner refuse a pool connection if the packaged known-answer self-test fails.

| Component | Role in live execution |
|---|---|
| TURING exact superposition and swarm | Two-amplitude register evolves the lane schedule |
| TURING Cayley dynamics | Three discrete coupling stages (3, 2, 1); resetting each cycle bounds coefficient growth |
| TURING discrete tunnelling | Exact transfer coefficient contributes to the traversal stride |
| Hendrix | Exact F_257 logarithm contributes to the traversal stride |
| Dodecahedron/icosahedron overlay | 32 disjoint nonce lanes: 12 face-labelled lanes and 20 vertex-labelled lanes |
| Lucas/PV structural acceleration | Exact period-516 reduction and a readonly packed lookup compute phi^s at scale indices 10^12, 10^15, 10^18 and 10^20; live Hendrix extension-search amplitudes are checked against Lucas trace and norm parity |
| Geometric/Galois engine | Zeckendorf candidate traversal, SHA-256d oracle evaluation, checked amplitude and harmonic trace |
| Local gatekeeper | Independently reconstructs and verifies each share before submission |
| Pool acknowledgement | Only a matching outstanding submission can increment accepted/rejected counters |

The PV lookup requires two coefficient reads after integer reduction. Its full table uses 2,064 payload bytes; reduction cost grows with the input bit length. Lucas/PV provides scale arithmetic, independently of lane assignment.

The schedule is a checked permutation: it changes traversal order while retaining exact coverage. It does not predict which nonce satisfies SHA-256d. The field-collapse operation receives a hash-qualified candidate; its amplitude is calculated and checked, including hits beyond the former first-100 prefix. Harmonic consensus checks the actual Laplacian kernel, since a zero quadratic form alone is insufficient over F_257.

TURING returns an explicit obstruction for continuous adiabatic evolution. This integration uses a finite discrete cooling schedule. These checks do not establish quantum speedup, physical quantum device execution, or a profitable mining rate.

### Recovery and observability

- EOF, idle timeout, failed handshake, mining-task failure, and overdue submission acknowledgements end the session and close its socket. The deployed container's restart policy creates a fresh handshake.
- Exhausting nonce lanes advances extranonce2; exhausting its fixed width waits for new work without wrapping. Job revisions, clean jobs, extranonce changes and mask changes invalidate in-flight work as appropriate.
- `MINING_NONCE_BATCH` is now limited to 1 through `2**20` (previously up to `2**32`); configurations above the new bound must be reduced. Authored `solve_job` scan windows use the same cap. This bounds worker completion during shutdown. The default remains 65,536.
- Pool difficulty is captured per job. JSON decimal difficulty retains its exact decimal value. Malformed jobs are rejected before changing the active job table.
- Host statistics distinguish locally evaluated candidates and submitted, accepted and rejected shares. Unresolved submissions are reported when a session closes.

### Release evidence and remaining gates

The mining regression workflow defines authored-search, TURING, Hendrix and isolated image checks across Python 3.10, 3.12 and 3.13. Its configured matrix must pass on the proposed release commit. Local task results and their source manifests are retained in the Coding Agent validation record and task outputs; this document does not establish release qualification.

Production qualification still requires the image built from that exact commit to pass BIST on the mining host, successful authorized pool handshakes, observed accepted shares, an operational soak with reconnect/timeout recovery, sustained resource/hash-rate measurements, and operator review. The current mining-admin API is an in-process model and is not host telemetry or control for this miner. Do not use it as evidence that the deployment is running.


<!-- /coderabbit-ai-generated:v1 -->