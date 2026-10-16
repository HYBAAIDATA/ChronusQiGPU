# Salamander consolidation — read/write capability composition

## Corrected architectural distinction

Only `repository-review` is read-only. Salamander now also equips `source-repair`, a write-capable native adapter that routes through the existing host-configured validator and `RepairTransaction` before source publication. Review results never grant write authority. Permission boundaries and validation are not restrictions on intelligence: they prevent documents, guessed metrics, auto-heal flags and unverified commands from controlling production changes.

## Host wiring corrected

`SalamanderEngine(repo_root=..., source_validator=...)` retains one actual `SalamanderAgenticController`; its scanner and optimizer are the engine's existing public attributes. `agentic_heal` and codebase-healing dispatch use that controller, instead of creating a fresh validator-less controller pointed at the default root. `source-repair` submits target/replacement/snippet to the same optimizer/transaction. Failed/missing evidence leaves original bytes untouched. No callback/shell authority was added.

Skill-loader exceptions now surface during engine construction/reload. Invalid loader results cannot silently replace equipment. This removes a real hidden-integration-failure mode. The autonomy module imports the canonical `aethel.cassini.CassiniVerifier` directly rather than the broad compatibility facade/repeated identical fallback. No Cassini operator was changed or substituted.

## Consolidation

The existing PR68 branch contains PR66 as its ancestor, PR67's trusted graft importer/tests, complete six-source catalogues/locks and capability protocol/manifests, plus native review, native source-repair and corrected host composition. PR67 is now a redundant source slice for this combined delivery, not another required merge. Original evidence remains retained with its original scope. PR65 is independent and is NOT incorporated by this consolidation.

## Executed, not assumed

134 local cases passed, four explicitly excluded. This continuation imports actual full module bodies and runs the real SalamanderEngine constructor—no extracted-method dispatcher. Package initializers, full checkout/conftest and installed artifacts remain excluded by the disclosed namespace harness. Source-repair positive tests actually publish fixture bytes using explicitly labelled validator contract doubles; they do not execute real isolated regression tests. The runtime is write-capable, but a production validator is still an outstanding host integration. `unshare -Urnm true` exited0: availability is not sandbox qualification.

## Real merge blocker

Fresh combined-status reads at PR66 d4bed8f28bd5b139d2e82e72ca6284f403d8dc68 and pre-consolidation PR68 eed2f497cac2340dd702baa62b26cc2797767508 returned FAILURE for `chronus/mla1517/gates`: incomplete or invalid mandatory assurance evidence. This is no longer merely missing check-run visibility. The source rollup requires all twelve mandatory gates, matching source commits/digests and actual artifacts, and rejects FAIL/ERROR/SKIP/NOT_RUN/stale/missing evidence. We have not diagnosed the exact CI artifact failure, run all gates or changed statuses to success. Do not disable gates or manufacture results to merge.

## Unfinished delivery, explicitly owned

All-source executable integration is NOT complete. Catalogue entries include fixtures, guidance and provider-specific workflows—not interchangeable executable tools. Outstanding work includes licensed per-artifact promotion, service-specific tool/account/policy contracts, real sandboxed regression execution, full installed-engine/system qualification, complete assurance artifacts, and byte-preserving publication of large Claude API files through authenticated Git execution. No competitor model evaluation or AGI/ASI certification has run. No merge, main push, deployment, mining or provider invocation occurred.

## Capability elevation — Native fabric, isolated repair, and mathematical substrate

In October 2026, the capability architecture was elevated from fixed point-to-point wrappers to an extensible, policy-enforced capability execution fabric (`Intelligence/capability_fabric.py`):
1. **Profile-Enforced Policy Gatekeeper**: Dual execution profiles (`INTERNAL_RESEARCH` vs `SHARED_RESTRICTED`). Write, spawn, recovery, and registry-mutating capabilities are strictly barred from execution under `SHARED_RESTRICTED` via fail-closed authorization checks.
2. **Cryptographically Anchored Execution Receipts**: Every execution produces an immutable `CapabilityExecutionReceipt` binding input digest, output digest, duration, findings, and status into a verifiable SHA-256 receipt.
3. **12-Stage Closed-Loop Isolated Repair**: (`Intelligence/isolated_repair.py`) executes repairs inside disposable temporary environments (`tempfile.TemporaryDirectory`). Pre-change defect reproduction is mandatory (refuses repair if baseline defect is absent); candidate must pass AST syntax parsing, sandbox defect probe, and regression validator before atomic publication.
4. **Outcome Learning Ledger**: Real repair outcomes (both committed successes and rolled-back failures) are recorded with empirical confidence updates. Self-certified success is rejected as learning evidence.
5. **Mathematical Research Substrate**: (`Intelligence/mathematical_research.py`) provides formal conjecture representation, lemma dependency DAG tracking, and strict separation between numerical experimentation and formal mathematical proof (Section 12 protocol).
6. **Reproducible Test Evidence**: 156 passed, 5 skipped (Windows unprivileged symlinks/fifo), 0 failed across full regression battery (`tests/test_capability_fabric.py`, `tests/test_isolated_repair.py`, `tests/test_mathematical_research.py`, `tests/test_salamander_agentic.py`, `tests/test_salamander_host_composition.py`, `tests/test_salamander_repair_boundary.py`, `tests/test_salamander_verified_repair.py`, `tests/test_repository_review.py`, `tests/test_skill_manifest_anchor.py`, `tests/test_skill_graft.py`).

