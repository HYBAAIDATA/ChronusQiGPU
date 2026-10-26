# Live shadow audit follow-up

This is a live Linux-process shadow run, not Docker qualification or a production approval.

## Observed evidence

- Real Stratum subscribe/authorize and job receipt succeeded for Braiins and ViaBTC. Each probe built an 80-byte header with a negotiated target. Neither protocol probe submitted a share.
- The supervised independent software-fabric miner consumed real Braiins jobs. One captured heartbeat reported 57,984 hashes and 609 executions, with 291.2 H/s measured over its 30-second window. These are snapshot values, not a guaranteed rate or hardware benchmark.
- No pool-accepted share has been established. The runtime was intentionally configured without live submission authority.
- Dedicated Salamander remained armed without its required MMIO device. Embedded mining recovery ran on an identity mismatch, but its causal audit import failed.
- TOE mining advice was unavailable or incomplete. No claim of complete TOE end-to-end integration is made.
- Custody, submission authorization, and Guardian configuration were unavailable in this non-strict run. An HTTP readiness success did not establish production readiness.

## Repairs

- Correct Salamander's causal-coordinate import to the canonical `mining.causal` module. Add a regression asserting the recovery/evidence hash link in the causal ledger.
- Preserve fail-closed behavior when authoritative pool state is missing; assert no successful recovery audit is generated.
- Add explicit scope, strict/non-strict governance mode, dependency requirements, and `production_qualification: not_established_by_this_probe` to readiness responses. Existing readiness semantics are preserved rather than silently reinterpreted as release approval.

## Focused validation

Readiness/API and recovery tests: 20 passed, 1 skipped, 2 subtests passed. This does not replace the unresolved whole-root qualification, Docker execution, hardware integration, full TOE path, fault-recovery exercise, or accepted-share evidence.

## Audit packaging

The first externally delivered audit ZIP contains redacted logs, probe source/results, heartbeat telemetry, HTTP captures, a screenshot of the actual local endpoint, and SHA-256 checksums. Its SHA-256 is `e746d101acdd99441b3a88453328afdb12ecd227253b672a86b8976095b3fa38`.

Checksums detect later changes; they are not an independent witness or pool signature. Credentials and local administrative keys are excluded. Before/after captures must remain separate. No production/publication-ready verdict is issued.
