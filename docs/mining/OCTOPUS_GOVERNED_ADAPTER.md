# Governed Octopus execution adapter

`chronus.mla1517.mining.octopus_adapter.GovernedOctopusAdapter` connects the
600-lane executor to an existing `GovernedProductionMiningCoordinator`
(the neutral public alias of `M3PythiaProductionMiningCoordinator`). M3 names
a governance milestone, not a CPU/GPU model or vendor.
It is opt-in and does not replace the default production search loop.

## Binding

Use a fully configured, connected M3 coordinator in synchronous submission
mode (`asynchronous_submission=False`, the coordinator constructor default).
Its AL HARAS authorization, THESEUS storage, live-pool identity approval,
chain observer, proof adapter and transport must already be configured.
No adapter flag creates any of these authorities.

```python
from chronus.octopus_execution import OctopusExecutionEngine
from chronus.mla1517.mining.octopus_adapter import GovernedOctopusAdapter

engine = OctopusExecutionEngine(shadow_dir=operator_evidence_directory)
adapter = GovernedOctopusAdapter(coordinator, engine)

# Shadow qualification: real current job, no submission call.
receipt = await adapter.search_current_job(window=600)

# Live intent, only after the coordinator's own production gates permit it.
# This does not enable approvals or credentials and is NOT an upload/rollout step.
receipt = await adapter.search_current_job(window=600, request_submission=True)
```

The adapter:
- serializes campaigns with the coordinator's search lock;
- refreshes/adheres to the existing hashrate governor and charges executed work;
- binds the runtime-config seed, worker limit, per-arm budget and window into a
  secret-free SHA-256 policy digest retained in the campaign and causal event;
- refreshes the Stratum-owned session/generation/target identity;
- reserves and consumes work through the canonical nonce lease ledger;
- derives the header and extranonce from the real proof adapter, not fixtures;
- limits a materialized campaign to at most `2^20` nonces;
- runs the current CPU-reference/emulator executor with explicit provenance;
- discards stale-generation winners and checks their lease membership;
- independently rebuilds the header, digest and negotiated target before submission;
- records plan, execution, candidate and outcome boundaries in the causal ledger;
- delegates submission to M3, retaining AL HARAS, THESEUS custody, chain-tip,
  duplicate, proof and single-writer gates;
- requires transport wire-write evidence and literal `True` acknowledgement
  before reporting `ACCEPTED`;
- records lost acknowledgement after a write as `OUTCOME_UNKNOWN` and never retries;
- waits for its worker before releasing a cancelled campaign's nonce lease.

`submitted_live` describes an observed wire write, not pool acceptance.
`accepted` is a separate boolean. Rejected or unknown writes are not successes.
The synchronous `OctopusExecutionEngine.run_campaign(approval_flag=True)` API
alone remains shadow-only: a boolean is not a transport or authority.

## Qualification boundaries

Adapter tests use local protocol fixtures with real SHA256d proof checking and
real nonce-lease allocation. They do not establish external pool acceptance,
physical accelerator execution, profitability, hostile-code isolation, or
publication approval. Existing M3 custody/authorization tests qualify the
underlying submission boundary independently.

Do not attach this adapter to a coordinator with an independent asynchronous
submission worker: the current coordinator carries pending correlation on the
instance. The adapter rejects that configuration rather than risking mixed
custody lineage. The existing default search/submission pipeline is unchanged.


## Operator policy

`/api/v1/config` accepts `execution` and `intelligence` sections alongside the
existing pool, solver, hashrate, window and campaign configuration:

```json
{
  "execution": {"mode": "independent"},
  "intelligence": {"seed": 1337, "max_workers": 4, "max_nonces_per_arm": null},
  "hashrate": {"target_hs": 0, "ceiling_hs": 10000000000000000000},
  "window": 200000
}
```

`independent` uses the Chronus software-defined GPU. `auto` prefers a supporting
physical adapter and records software fallback when allowed. `scale_stack`
forbids software fallback; an installed but non-executable physical adapter does
not satisfy it. Octopus itself currently executes its explicitly labelled CPU
reference route, not an unimplemented physical route. Config mode does not
magically turn that executor into hardware acceleration.

Target zero means full achievable rate **under** the ceiling. A positive target
may lower the rate; neither value creates throughput. The configured ceiling
may be reduced but not raised above 10 EH/s. Each independent deployment needs
an assigned slice of an aggregate fleet cap; cross-host coordination has not
been qualified here. New writes use private, atomic config files. Untrusted
persisted configs are revalidated and cannot preserve live approval after an
invalid section. Missing policy authority revokes cached live intent.

These controls do not prove the solve-first target has been completed. Current
nonce ordering still requires exact SHA256d execution/recheck. TOE retains its
full reasoning interfaces and is not globally restricted to mining's adapter
boundary. See `OWNER_DECLARATIONS.md` D10 and the canonical principle map.
