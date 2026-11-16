# Chronus release decision — PR #93 close-out candidate

**Decision:** **EVIDENCE-GATED CANDIDATE — NOT YET PRODUCTION-ADMITTED**

Review date: 15 November 2026  
Candidate branch: `closeout/triad-production-posture-20261115`  
Pull request: #93

## What is closed in source

PR #93 closes the principal source/documentation gaps required for the maintained CHRONUS–OVID–THESEUS triad:

- restart-durable THESEUS custody and continuity;
- versioned OVID transform/materialisation;
- triad restart/reconstruction composition;
- migrated tensor capability surface under maintained Chronus namespaces;
- explicit fail-closed OpenCL, CUDA and Metal tensor backends;
- historical test/benchmark migration registers;
- removal of self-certifying release paths;
- exact-commit, attested product-gate admission contract;
- current production documentation and claim boundaries.

## What controls admission

Production admission is not a boolean embedded in source. It requires:
1. exact release SHA;
2. successful current CI for the declared software scope;
3. verified artifact attestation;
4. all mandatory product gates PASS;
5. device/deployment evidence for each advertised physical or operational capability.

## Current CI state

The initial PR #93 Actions/CodeQL runs terminated across unrelated jobs before usable job logs were available. GitHub's job-log endpoint returns Azure `BlobNotFound` for sampled jobs. The breadth and timing are consistent with runner/artifact infrastructure failure rather than a meaningful product verdict.

Therefore:
- no red run is being relabelled as a code failure without step evidence;
- no green result is being inferred;
- the candidate remains evidence gated until an exact-current run can execute.

## Product-specific open environment gates

These do not invalidate implemented source, but they cannot be manufactured in repository CI:
- current physical accelerator performance on the target device;
- real customer-held external key custody;
- multi-region replication/failover and declared RTO/RPO;
- customer/environment acceptance where contractually required;
- external accreditation or certification where claimed.

## Merge rule

Merge only when the software/repository checks for the exact PR candidate are successfully executed or an equivalent retained exact-current execution record is reviewed. After merge, production admission remains profile-specific and gate-controlled; a merge is not itself an external deployment or hardware certificate.
