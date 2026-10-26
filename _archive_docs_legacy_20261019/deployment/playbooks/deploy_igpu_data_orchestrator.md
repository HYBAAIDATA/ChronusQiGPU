# IGPU Data Orchestrator deployment playbook

## Goal

Deploy the IGPU data orchestrator in an enterprise or hyperscaler environment in a way that makes the evidence boundary explicit and avoids overstating production claims.

## Prerequisites

- a Kubernetes cluster or equivalent orchestration environment
- persistent storage with enough capacity for the planned cold-data tier
- identity and policy controls for tenant- and role-scoped access
- a validated environment for software execution and a separate environment for live hardware execution

## Sequence

1. Deploy `igpu-operator.yaml`.
2. Validate the `igpu-core` service is reachable and the evidence gate is enabled.
3. Deploy the data ingestion service and confirm the `aethel` storage path is available.
4. Use the benchmark harness to validate cold-tier savings assumptions.
5. Connect the causal intelligence service once the environment has passed full software proof gates.
6. Only then expose enterprise BI or regulated data products.

## Operational checks

- Confirm the storage layer rejects partial or corrupted writes.
- Confirm the digest chain is retained for every ingest step.
- Confirm the environment emits a clear evidence classification for each run.
- Ensure there is no silent promotion from theoretical or software-verified claims to live deployment claims.

## Rollback

If any evidence gate fails:

- stop the service
- isolate the affected workload from external traffic
- replay the last known-good state from the journal
- restore the last valid checkpoint before re-enabling traffic
