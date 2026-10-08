# PR140 bounded remediation — QC HOLD

No new architecture or release is introduced. Capabilities are preserved; explicit reference execution now requires an operator-configured scoped approval registry. No registry is shipped enabled. `CHRONOS_REFERENCE_APPROVALS_FILE` points to operator configuration using schema `chronos.reference_approvals/1`. Each named approval requires `approved: true`, `mode: reference`, explicit non-wildcard `capabilities`, `approved_by`, `purpose`, and finite future `expires_unix`. Callers explicitly enter `reference_execution(approval_id)`. Revocation and expiry are checked on each guarded call, including warm cached calls. This is an application policy boundary, not a cryptographic owner identity service or a sandbox against arbitrary Python/environment modification.

## Guarded surfaces

- Numerical H4 public geometry functions: `chronus.h4_600` scope.
- Legacy FP64 PYTHIA lattice functions: `pythia_search.fp64` scope. The exact dataclass/quantum walk contracts remain available without reference mode.
- Numerical Poincare loader/order: `poincare_11d_order` scope.
- Grover-style heuristic schedule methods: `mining.GroverStyleSearch` scope. Actual Merkle verification and SHA primitives are not relabelled quantum or removed.
- All public structured ground backends, including interval-certified FP64 representatives: `structured_ground.interval_or_fp64`. Direct interval solver entry points also require approval.
- Structured matvec returning float projections: `structured_matvec.float_projection` scope.
- Legacy GoldenRuntime planning/search/mining and scaled search: `golden_runtime.legacy_search`. The guard executes before the planner's broad exception/fallback machinery.
- Sealed resident Hendrix execution rejects any active reference session before issuing production mining receipts.

## Mathematical classification

Exact residual/inertia certificates can bound the error of a numerical representative. They do not make that representative an exact eigenvector. Default production requests do not execute those backends. Their reference capability remains callable under approval, while a strict exact public ground-state replacement remains UNAVAILABLE and must be handed off. No capability deletion or exhaustive zero-counter closure is claimed.

## Evidence boundary and outstanding gates

Individual changed files were recovered at `75b91ffda34d004cd331fe8ba64dd1272f732229`. Local test/build dependencies include the previously retained source snapshot: this is not a complete canonical checkout of the live head. Final verification must distinguish file-bound local results from exact-head/full-product qualification. No older test result is rebound by editing a commit field.

The previously reported platform failure and import-audit findings remain blockers, not baseline exemptions. Other direct numerical APIs and canonical consumer migration are not exhaustively closed. CI remains UNAVAILABLE. Scripted local pool records prove local protocol integration only; external live-pool acceptance, physical accelerator execution and deployed THESEUS/OVID custody remain UNAVAILABLE.

The final bounded pass ends with STOP and a machine-derived NOT_CERTIFIED handoff if any mandatory gate is failed, unavailable or unverified. This PR must not grow to replace unrelated canonical lanes.
