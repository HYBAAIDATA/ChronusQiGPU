# Owner directive — agent-owned production readiness; real-workload parity, not benchmarking

**Issued:** 28 October 2026. **Owner:** HYBA repository owner. **Implementation agents:** Perplexity (CHRONUS), Sider (TURING) and Copilot (Tensor/Kellogg) have been designated by owner. **Shared CI owner:** GitHub Copilot (#96). **Independent QC:** ChatGPT in the owner conversation, no GitHub account/assignee implied.

**Status:** Approved workstream acceptance policy, **not** proof of production readiness, benchmark claim, physical backend certification, or permission to change the canonical architecture. Read the underlying Notion constitution and report conflicts for owner resolution. The three issue trackers are [CHRONUS #91](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/91), [TURING #92](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/92), [Tensor/Kellogg #93](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/93); independent [QC #94](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/94).

## One accountable implementation agent per system — through closure

Each owner receives one bounded subsystem lane and owns **implementation through completion**: discover and reconcile actual source and canonical workflows; implement corrections; keep functioning capabilities intact or demonstrably replace them; wire public/composed runtime and required security/transform/custody integrations; execute unit/property/adversarial/clean-installed/restart tests; conduct the final actual-workload parity voyage; address independent QC defects; produce a reproducible closure dossier. The implementation agent must not self-certify. A PR merge or documented module is not a production pass.

The repository owner has named Perplexity for #91, Sider for #92 and Copilot for #93. GitHub Copilot owns #96, the independent shared CI-green lane. Leave GitHub assignees unset unless the owner supplies verifiable GitHub usernames; do not invent identities. ChatGPT is the designated independent QC reviewer, with review work controlled by this conversation and issue #94.

## What production-ready means here

Production readiness is a **scope- and profile-specific, independently verified result**, not a universal maturity adjective. A system may be ready for the verified CPU/software profile without claiming an untested Metal/OpenCL/physical-QPU/ASIC/fleet profile. For the approved target profile, gates require:

1. Canonical authority and functional requirements reconciled; no hidden source forks or unapproved owner-boundary changes.
2. Correct mathematical/operational semantics verified with independent oracle and known-answer/negative/property tests; unsupported domains fail closed.
3. Real production composition/entry points, AL HARAS admission/tenancy, OVID transformation contracts where used and THESEUS durability/provenance.
4. Clean installed distribution artifacts, exact commit/package hashes, fresh-process checkpoint/restore/replay and safe rollback.
5. Demonstrated actual representative end-to-end workloads, independently checked for **parity of outputs, state, semantics and required failure behavior**, with predeclared tolerances; no substitute synthetic dashboards or staged mock success.
6. Resource bounds and operational safety under those workloads (actual memory, latency, timeout, cancellation, error handling, backpressure when relevant), plus runtime and profile evidence. These measurements are **operational telemetry**, not comparative benchmarking or a speed claim.
7. Independent QC `QC_PASS` at the exact candidate SHA/artifact and explicit owner approval before the system's workflow/status is promoted to `PRODUCTION_READY` or released.

Where mandatory evidence is missing, mark the specific profile `QC_HOLD`/`GATED`/`UNAVAILABLE`; don't fabricate passing status or reduce the specification merely to force green.

## Final validation = real workload parity; no benchmark substitute

**CHRONUS — heterogeneous execution / independent virtual GPU class:** execute actual mathematical graphics QSDL, tensor kernel, and canonical sealed Hendrix/SHA256d workloads through the composed CHRONUS public path. Independently validate images/scene semantics as quality-contract permits, tensor numerical/exact results, exact SHA256d hashes/candidates, stale cancellation, routing/device identity, durable receipt and replay. Test native software GPU without physical device and physical augmentation only where bound hardware is actually available. Goal: **correct, reproducible parity**, not winning a GPU race.

**TURING — independent VQC class:** run actual declared Bell, GHZ, bounded exact-MPS/non-Clifford and expectation/evolution programs through the public VQC. Independently validate gate matrices, normalized state/expectations, quantum-vs-classical entropy distinctions, entanglement and representation equivalence. For genuinely sampled measurements, validate expected distributions with predeclared confidence and seed/repetition contracts rather than requiring individual random outcomes to coincide. Prove custody/restore/replay and unsupported-domain refusal. Software VQC execution does not prove physical QPU or generic dense 10,000-qubit execution.

**Tensor/Kellogg — canonical logical tensor / exact mathematics class:** use actual representative complex matrix/tensor operations, TT/MPS/MPO and quantum operator/contraction, PULVINI/Ovid fold-and-reconstruct where authorized, and CHRONUS backend dispatch under typed precision/residual/memory contracts. Independently compare exact mathematical results or measured bounded errors, complex phase, metadata and restored state. Backend identity and no-silent-substitution are mandatory. Tensor TFLOPS never become mining hashrate.

**Cross-plane voyage:** admit an authenticated tenant, execute a real typed Tensor/Kellogg workload via CHRONUS, run TURING declared VQC with separately governed execution, version transformations through OVID, persist receipts/checkpoints via THESEUS, restart in a fresh process and independently validate reconstructed results. Check denial, corruption, loss, version mismatch, cancellation and cross-tenant isolation. Record both observed failures and successes.

For each parity voyage save exact real input and provenance, source SHA, installed package/wheel/container digest, contract and allowed precision, backend and device identity if relevant, independent oracle, output hash and semantic verification, raw result, timestamp/environment, custody identity and fresh-process replay result, negative evidence and exact reproduction commands. “Real workload” means actual non-fabricated operational or scientific input executed through the production entry point; the independent reference used to verify correctness is **not a competitor benchmark**.

## Competitive benchmarking — separate and only with competitors

- A **benchmark** under this workstream means a deliberately constructed **external competitive comparison** against an identified third-party product in a properly comparable workload class. Keep it in a separately approved evidence/claim dossier, **not** in the parity acceptance gate.
- Match the same actual input/problem, output correctness, relevant semantics, precision, quality, workload volume, timing scope, hardware profile and statistical protocol; preserve setup costs, raw runs, negatives and falsification conditions. No changed oracle or work-count trick.
- If there is no genuinely comparable competitor/product/class, record `NO_COMPARABLE_COMPETITOR`, make **no competitive performance claim**, and do not rebrand internal CPU/reference correctness tests as benchmarks.
- The three systems are **distinct product classes** with non-overlapping authoritative semantics; never claim “no equal”, universal superiority, quantum advantage or hardware equivalence merely because their classes differ. Unique architecture is a positioning statement, not comparative evidence.
- Existing canonical Notion benchmark/claim-promotion workflows are not secretly rewritten by this handover. Reconcile any required separate claim gate with the owner before promotion. Operational telemetry required for reliable deployment still must be measured.

## Transition and QC decision contract

`AGENT_ASSIGNED → SOURCE_RECONCILED → IMPLEMENTED → CLEAN_INSTALL_VERIFIED → REAL_WORKLOAD_PARITY_PASS → RECOVERY_SECURITY_PASS → QC_PASS → OWNER_APPROVED → PRODUCTION_READY (verified profile)`.

The arrows represent **evidence gates**, not assumed future results. Use explicit `BLOCKED`/`FAIL`/unavailable states for incomplete phases. Agents must keep fixing and resubmitting until QC accepts all mandatory checks for the target profile. No automatic deployment, package publication or status promotion; unsupported hardware-specific, market, physical-QPU and pool-acceptance claims stay unpromoted.

## Agent assignments and delivery lanes — owner decision (28 October 2026)

| Lane | Named executing agent | Tracking | Completion requirement |
| --- | --- | --- | --- |
| CHRONUS | **Perplexity** | [#91](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/91) | Implementation through independently verified production qualification |
| TURING | **Sider** | [#92](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/92) | Implementation through independently verified production qualification |
| Tensor/Kellogg | **Copilot** | [#93](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/93) | Implementation through independently verified production qualification |
| Repository-wide CI | **GitHub Copilot** | [#96](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/96) | All required workflows execute and pass, with exact-head evidence |
| Independent QC | **ChatGPT** | [#94](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/94) | Review source and exact artifacts, real-workload parity, security, recovery; owner decision remains final |

**Copilot on Tensor/Kellogg and GitHub Copilot on CI are separate responsibility lanes.** These are the owner's named AI agents; no GitHub usernames, notification deliveries or authenticated GitHub assignments have been inferred. Green CI is a necessary shared engineering gate but not a substitute for correctness, real workloads or QC. [CI workflow instructions](09_GITHUB_COPILOT_CI_GREEN.md).

