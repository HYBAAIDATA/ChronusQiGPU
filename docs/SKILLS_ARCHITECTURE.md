# Expert capability architecture

```text
MCP client
  ├─ existing exact-math tools (unchanged)
  └─ governed skill tools
       ├─ contracts and preflight validation
       ├─ explicit candidate router (cost/risk/time budgets)
       ├─ AL HARAS authorizer (deny by default)
       ├─ append-only SHA-256 audit chain
       ├─ bounded skill execution
       └─ outcome/evaluation tracker
            └─ EUCLID / TOE / SALAMANDER source modules
```

`hyba_mcp/skills/` is a static registry, not a prompt router. Every registered
ID maps to one module, input schema, output schema, source signature, and
limitations. Routing considers only the explicit `skill_id` or `candidates`
provided by a caller and chooses the lowest-cost candidate satisfying
`max_cost`, `max_risk`, and `max_seconds`. There is no implicit cross-domain
fallback; callers may provide an explicit `fallback_chain` (or `candidates`)
for routing among registered skills, but a failed invocation is never retried
with a different skill or different semantics.

Each invocation validates arguments, asks the injected authorization adapter,
requires durable audit configuration before allowing an invocation, and records
the decision and result in an append-only hash chain. The audit file is
JSON-lines; each record includes its sequence, prior hash, canonical SHA-256,
identity, inputs, outputs, latency, success, and authorization result.

Numeric and diagnostic skills run in a spawned child process with POSIX CPU and
address-space limits and a parent-enforced timeout. On platforms that cannot
enforce those OS limits, execution is denied rather than silently downgraded.
The authorization capability is a trusted adapter call and runs in-process;
its default behavior is denial. This sandbox does not create an OS filesystem
or network namespace, and must not be used to execute arbitrary user code.

`record_outcome` retains in-process latency, success rate, and Brier-score
summaries. It is evaluation telemetry, not a benchmark certification; no
cross-process learner or hidden feedback authority is introduced.

## Authority and composition

Skills are advisory. SALAMANDER proposals never execute. Mining guidance cannot
replace hash-pipeline consensus. Forecasts and factor rankings do not authorize
actions or prove causal effects. Composite skills are not automatically
created: callers may compose registered skills, but each result remains subject
to its own contract and permission decision.
