# Jobs, errors and results

## Process-local job lifecycle

The typed native job states are `queued`, `running`, `succeeded`, `failed` and `cancelled`. A single worker executes jobs within a live native backend instance. Registry capacity is bounded; no durable scheduler or restart recovery is implied.

## Safe handling

| Condition | Required response |
| --- | --- |
| Invalid parameters/configuration or unsupported capability | Correct the request; do not retry unchanged |
| Compilation/admission refusal | Surface the reason and supported domain |
| Wait timeout | Retain the job ID; the computation may still be running |
| Cancellation accepted | Confirm the queued job is cancelled |
| Cancellation declined | Treat work as potentially running; do not promise termination |
| Execution/result validation failure | Retain diagnostic report and provenance; investigate |
| Idempotency conflict | A key refers to different request content; correct caller logic |
| Unknown job after restart | Do not infer failure or resubmit without external reconciliation |

## Interpreting results

The typed result wraps the canonical pipeline report. Inspect both aggregate verdict and stage evidence. A computation can pass while a differential check is gated or an unrequested custody stage is skipped. Neither establishes enterprise durable acceptance.

Preserve exact values, request/artifact bindings, actual configuration and runtime versions. Do not replace them with rounded display values in audit records. See [mathematical evidence](../mathematics/foundations.md).
