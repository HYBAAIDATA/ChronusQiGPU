# Library operations and recovery

TURING is a library, not an invented managed service. No dashboard, durable
scheduler, vault integration or hard resource sandbox is claimed here.

## Execution and ownership

Use `with TuringPipeline(...)` or call `close()` in `finally`. The facade closes
its backend, including an injected backend; do not share an owned backend
between facades unless the adapter explicitly provides safe shared ownership.
Each native backend has one worker and a bounded registry (completed jobs also
consume its registry budget). Independent instances do not share jobs or
idempotency records. There is no automatic retry or durable checkpoint resume.

`close()` rejects new submissions and drains work, including queued work. It
may block on an active computation. Queued jobs can be cancelled; Python thread
execution cannot forcibly stop a running calculation. A wait timeout does not
terminate work. Applications needing hard deadlines, memory containment or
untrusted workloads must use a supervised process boundary with explicit
termination/storage semantics, and qualify that integration separately.

## Incident runbook

1. Stop admitting new work; retain the original job ID and private diagnostic
   report. Classify validation/capability refusal versus execution/result failure.
2. On wait timeout, query the same live backend/job. Cancel queued work if
   appropriate; do not resubmit a still-running operation with a new key.
3. On result/provenance failure, do not consume the value. Retain evidence and
   escalate; never downgrade verification to obtain a successful return value.
4. Drain/close owned resources. If a supervised worker must be terminated,
   document whether it may have performed custody/storage side effects.
5. Reproduce using a minimized nonsensitive fixture, exact versions/configuration
   and artifact hashes; isolate whether the defect is mathematical, lifecycle,
   integration, dependency or packaging related.
6. Restore the previously qualified artifact set and resolution lock. Re-run its
   installed smoke/consumer suite before returning traffic or batch submissions.

## Telemetry and data handling

For an embedding application, emit allowlisted structured events containing an
execution ID, event name, status/error category, queue/execution/wait durations,
retry count (zero by default), cancellation result and resource measurements.
Measure queue wait separately from computation. Backend threads and result
certificates are not observability dashboards.

Do not serialize environment variables, raw parameters/programs, custody paths,
credentials, exception `str()` values or full diagnostic envelopes into shared
logs by default. Existing errors may contain private adapter diagnostics; treat
them as sensitive. Configure private retention/access before collecting reports.
The artifact qualifier retains step status/duration, artifact/lock hashes and
reviewable JUnit outputs, not installer output or environment dumps.

## Capacity, rollout and rollback

Record workload family, width, depth, representation, candidate count,
concurrency, hardware/OS/interpreter/dependencies, warm-up policy and repetitions.
Measure median/tail latency, throughput, peak memory and resource cleanup against
an approved prior version. Select regression thresholds before collecting release
results. Small exact smoke timings are not a throughput/capacity baseline.

Stage the real exact native engine and actual consumers; mocks are only for
controlled failure injection. Rehearse replacing the candidate with the previous
known-good wheel and dependency resolution, verify consumer outputs, then restore
the candidate only if approved. Publishing/yanking a library does not uninstall
copies already deployed. Preserve the previous verified artifacts and hashes.
Named support/security owners and an escalation route are required before rollout;
this document does not invent them or imply a service-level agreement.
