# Fenced custody integration

The old d:\\chronus-quantum-igpu\\main.py snippet is not a maintained file in the inspected Git tree.
`chronus_live_miner.py` delegates to `chronus.execution.mining_entrypoint`.
`src/chronus/execution/main.py` is a skeleton. Myrmidon, stealth and EUCLID modules
are different contracts and are not silently rewritten. The maintained asynchronous
mining runner and fleet CLI now use explicit lifecycle/notification primitives.

The mining engine accepts an optional explicit `custody_store` and
`custody_tenant_id`. Sidecar owns fence acquisition, restart reconciliation and
shutdown seal/release. Existing default constructor and admission/target gates
remain intact. A sidecar fault requests stop; locally verified candidate evidence
is written before submission. No default etcd URL, credentials, trust registry or
tenant is inferred. Fleet CLI avoids lock-taking signal handlers and checks worker
and heartbeat survivors under one join budget. The async mining session owns
its native workers rather than relying on asyncio's implicit default executor.
Its startup and teardown use an independent monotonic deadline and a shared
five-second drain budget; a non-terminating native worker is reported in
`alive_workers` and the session records STOP_DEGRADED. Native hung kernels
cannot be preempted by Python thread cancellation; no physical worker termination
or hard kernel execution-time claim is made. The signal handler is a scalar
notification only: threading.Event.set() acquires a condition lock and is not
a reentrant signal-handler primitive. The event loop translates the scalar
notification into the shared stop and cancellation events outside the handler.

In production, inject an authenticated etcd client and authority-approved
EpochSigner and verify_anchor policy. A callable is not hardware attestation.
The single-node fencer is not an alternative to distributed consensus.
No live etcd or signer deployment was performed. Physical 1,000-GPU capacity is
Unavailable. Gate G2 tests with deterministic doubles are simulated tests, not
deployment qualification. The release gate is unchanged.

A pre-write quorum read outage is distinguished from an uncertain write outcome.
The former retains the unanchored WAL and retries within the lease and watermark
bounds; the latter invalidates write readiness until authenticated recovery
reconciles the remote anchor. Etcd adapters must expose transport connectivity
failures as ConnectionError or TimeoutError for the pre-write retry path;
unclassified exceptions fail closed. No local watermark advances on a missing
acknowledgement. SQLite storage classes, indexed epoch floor and read-back
anchor fields are checked without coercion.
