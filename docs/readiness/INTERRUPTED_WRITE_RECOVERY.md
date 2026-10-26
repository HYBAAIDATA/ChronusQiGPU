# Interrupted-write recovery qualification

## Implemented

- Every new file-write intent retains its complete semantic request before durable placement: producer, provenance, domain links, format and transform contracts, and custody reference. Exception handling preserves that request and the original error.
- `TheseusFileRegistry.resume_write_intent` validates tenant containment, payload length/digest, mathematical placement and replicas, and object identity. It completes the original operation through the normal file registry; it does not invent an accepted share, successful execution, or replacement content.
- A separately authenticated THESEUS recovery receipt binds the failed intent, exact request digest, completed version, and original error. The intent becomes committed only after this receipt verifies. Existing blobs and history are not deleted.
- Mining startup automatically resumes new-format retained requests. Legacy requests remain fail-closed unless explicitly reconstructed.
- `scripts/recover_mining_write_intents.py` supports offline legacy mining-receipt recovery. It requires a matching retained causal event and verifies referenced mining records. Previously unavailable context is labelled as reconstructed, not presented as original provenance. Run with the service stopped, a private storage snapshot, existing operator keys, bounded quotas, and an explicit `--apply`.

## Observed live repair

The operator-local Braiins validation run exhausted the underlying 64 MiB custody quota. Its seven abandoned write intents were retained, not removed. After the custody quota was explicitly aligned with the admitted tenant limit, all seven writes were completed through authenticated recovery. Full file reconciliation returned zero unresolved entries; database verification and mining-lineage verification passed. Pre-repair storage snapshots, causal sources, quota failures, and signed recovery records remain available.

This repairs interrupted-write restartability. It does not establish accepted external pool shares, sustained performance, GPU hardware execution, Docker qualification, or whole-repository/CI release readiness. Those are separate gates. A 10 EH/s configuration ceiling is not evidence of achieved hash throughput.

## Tests

Failure injection covers four durable custody boundaries, corrupt payloads, conflicting requests, wrong roots, unsupported legacy inference, automatic strict startup, and failure while recording the recovery receipt. The original error remains inspectable after successful recovery. The strict miner still requires a fresh Stratum identity after restart.
