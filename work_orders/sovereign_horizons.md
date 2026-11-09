# Sovereign horizons: implementation work orders

Status: planning. Baseline: `8fddfd17eb776a95e0eec1d1514dd48290c905b4` (default branch, 2026-11-09). This document translates requested objectives into work; it does not assert that any capability, assessment, certification, or government affiliation exists. No horizon is complete. The imported copy has not been compared with this baseline.

## Work-order status

| Work order | Status |
|---|---|
| H1.1 | in-progress |
| H1.2 | not-started |
| H1.3 | not-started |
| H3.1 | not-started |
| H3.2 | not-started |
| H2.1 | not-started |
| H2.2 | not-started |
| H5.0 | blocked |
| H5.1 | blocked |
| H5.2 | blocked |
| H4.1 | not-started |
| H4.2 | not-started |

## Delivery and evidence rules

- Execute phase order: this document; H1; H3; H2; H5; H4. Track dependencies and blockers rather than marking an untestable or unavailable deliverable complete.
- Each work-order completion record must identify source commit, environment and dependency versions, exact commands, raw outputs, exit status, limitations, artifact hashes, reviewer, and CI run URL. A later record or CI artifact may point to the tested commit; do not try to embed a commit's own hash in its contents.
- For each capability, plan invariant, property-based, adversarial, edge, unit, integration and end-to-end tests. Record a class as blocked/not applicable with reasons rather than inventing results. Production release requires the applicable seven classes and at least 90% measured coverage for the agreed scope; coverage is not proof of correctness.
- Prepare capability report, evidence pack, honest security questionnaire, SBOM and vulnerability snapshot, control matrix, independent assessment status, runbook and rollback, approved support commitments, refusal list, executive evidence pack and analyst evidence pack. External accreditation, penetration testing, customers, contracts and analyst ratings require actual external parties; mark unavailable items blocked.
- SHA-256 detects changes but does not authenticate evidence. Signed artifacts and the verification endpoint are blocked until a vetted ML-DSA-65 implementation, key custody, verification and applicable validation are independently established. Do not use the repository's demonstration signer as ML-DSA evidence.
- Proofs and test results are limited to their exact statements, assumptions and tested scope. Random tests do not prove universal properties. RTL timing, a GDSII file, and simulations do not by themselves prove physical side-channel resistance or fabrication.
- The specification is a proposed target; an unattainable or ambiguous acceptance criterion is reported as a blocker, never satisfied by a weaker result presented as equivalent. Approval is required before redefining a target.

## H1.1 — Lean formal library

- Horizon: H1 — formal methods and hardware.
- Specification: Formalize the proposed golden-ratio, Zeckendorf, braid and cyclotomic arithmetic results with explicit definitions and assumptions.
- Deliverable: `lean/Chronus/` Lean library, pinned build configuration, theorem imports, and statement/scope notes.
- Test: `lake build`, theorem-import checks, and checks rejecting `sorry` and unapproved axioms in the scoped library; verify any claimed connection to implementation separately.
- Acceptance criterion: All stated results compile without proof placeholders under the pinned toolchain; `phi_squared_eq_phi_plus_one` and precise cyclotomic arithmetic laws are among them. Binet/Zeckendorf and braid statements must define their domains and representation precisely. This does not prove implementation or hardware correctness.
- Dependencies: None. Existing `formal/ChronusUnivalence.lean` includes a `sorry`; it is not a completed proof.
- Estimated scope: Large. Status: In progress. An initial closed-identity proof slice is available; the remaining theorems and correspondence proof are not complete.

## H1.2 — Lane non-interference

- Horizon: H1 — formal methods and hardware.
- Specification: Establish a precisely scoped lane-isolation non-interference property, including the actual modeled execution and observation channels.
- Deliverable: Model, assumptions, proof or model-checker configuration, and a mapping to the implementation under test.
- Test: Check the property in the selected model; deliberately introduce a known leakage path and confirm the check detects it; inspect assumptions and reachable states for vacuity.
- Acceptance criterion: Proof or exhaustive finite-state check succeeds for the stated model and mutation fails. This does not establish absence of leakage in unmodeled microarchitecture, physical channels or deployed systems.
- Dependencies: H1.1 infrastructure if Lean is selected; independently establish implementation/model correspondence.
- Estimated scope: Large. Status: Not started.

## H1.3 — SkyWater layout evaluation

- Horizon: H1 — formal methods and hardware.
- Specification: Evaluate a SkyWater 130 nm layout flow for an identified RTL module, targeting netlist, layout, design-rule and timing evidence.
- Deliverable: Reproducible flow configuration, input versions, netlist/layout artifacts and DRC/LVS/timing reports, subject to tool and PDK availability and licensing.
- Test: Run the complete flow on the named RTL; inspect DRC/LVS outputs and static timing; separately verify cycle-count behavior across modeled inputs.
- Acceptance criterion: Flow completes and passes the chosen sign-off checks with no undisclosed waivers; cycle-count verification reports its assumptions. Static timing alone cannot prove constant cycles, constant power or tape-out readiness. Actual fabrication requires foundry acceptance and additional sign-off.
- Dependencies: Suitable RTL, pinned tools and permitted PDK; not dependent on H1.1.
- Estimated scope: Large. Status: Not started; physical-design environment required.

## H3.1 — Holographic code simulator

- Horizon: H3 — quantum error-correction research.
- Specification: Explore a defined HaPPY-style tensor-network code on an explicitly specified finite tiling.
- Deliverable: Research simulator and documented network construction, tensor, boundary conditions and parameter calculation.
- Test: Compare reproducible small instances against independently specified published examples with identical constructions; include tensor and encoding validity checks.
- Acceptance criterion: Specified reference instances match with full citations and exact construction correspondence. Arbitrary boundary sizes and expected code parameters must not be invented.
- Dependencies: Reference constructions and available numerical libraries.
- Estimated scope: Large. Status: Not started.

## H3.2 — Erasure recovery evaluation

- Horizon: H3 — quantum error-correction research.
- Specification: Evaluate whether a defined code instance can recover from boundary erasures, including the proposed 50% target.
- Deliverable: Reproducible recovery experiments, decoder, fixed seeds, raw results and methodological limitations.
- Test: Check recovery of specified logical states over enumerated small-instance patterns where feasible and a stated sample of larger patterns; include counterexamples and a correct baseline.
- Acceptance criterion: Report successes, failures and exact sampling domain. A sample of 100 patterns cannot establish recovery for every 50% erasure or a universal threshold. If the proposed target fails or is not well-defined, keep it blocked.
- Dependencies: H3.1 and a specified recovery criterion.
- Estimated scope: Large. Status: Not started.

## H2.1 — Two-party private-computation research

- Horizon: H2 — privacy-preserving computation.
- Specification: Evaluate a two-party computation of a simple function with private inputs, with the proposed cyclotomic representation as a research question.
- Deliverable: Clearly labeled research prototype, protocol specification, explicit threat model and independent test vectors using an established cryptographic construction where feasible.
- Test: End-to-end correctness, malformed-message and tampering tests, plus external cryptographic review of privacy, composition and parameters.
- Acceptance criterion: Correctness and adversarial tests pass and review supports the precise privacy claim. Absence of plaintext in transcripts does not prove privacy; do not claim production security from the prototype.
- Dependencies: Explicit ring, corruption model, protocol, implementation and cryptographic review.
- Estimated scope: Large. Status: Not started.

## H2.2 — Verifiable computation receipt

- Horizon: H2 — privacy-preserving computation.
- Specification: Explore a proof that a specified computation followed an agreed relation without disclosing private inputs.
- Deliverable: Proof-system selection, formal relation, generator and independent verifier, receipt specification and test vectors.
- Test: Valid proof acceptance; tampered result, statement and proof rejection; interoperability; independent soundness and zero-knowledge review.
- Acceptance criterion: A vetted proof system establishes the stated relation under documented assumptions. A signature or tamper detection alone is not a STARK or a proof of protocol compliance.
- Dependencies: H2.1, proof-system selection and external cryptographic review.
- Estimated scope: Large. Status: Not started.

## H5.0 — Legal and ethical review

- Horizon: H5 — governance review.
- Specification: Obtain an appropriately scoped independent legal and ethical review before considering the proposed autonomous-use work.
- Deliverable: Review status, scope, reviewing body, governing standards, outcome and authorized decision, or an explicit blocker.
- Test: Inspect the review record for an identifiable reviewer, scope, date and decision; a placeholder is not a review.
- Acceptance criterion: A genuine completed review is recorded. Current status: **BLOCKED — no review has been provided**.
- Dependencies: Qualified independent reviewers and authorized decision makers.
- Estimated scope: Small for status documentation; external review scope and duration unknown.

## H5.1 — Autonomous-use proposal

- Horizon: H5 — autonomous-use proposal.
- Specification: Requested autonomous engagement policy work.
- Deliverable: No implementation under this work order. A separately authorized non-weapon policy-verification use case may be proposed for review.
- Test: Not applicable while blocked; no prototype or test may be represented as completed.
- Acceptance criterion: Blocked; H5.0 completion does not authorize implementation of targeting or engagement functionality here.
- Dependencies: H5.0 and a separately defined, permissible non-weapon scope.
- Estimated scope: Undetermined. Status: Blocked.

## H5.2 — Engagement receipt proposal

- Horizon: H5 — autonomous-use proposal.
- Specification: Requested engagement-verification receipt work.
- Deliverable: No implementation under this work order. A separately scoped non-weapon verification problem may be considered.
- Test: Not applicable while blocked; no prototype or test may be represented as completed.
- Acceptance criterion: Blocked; a cryptographic receipt cannot independently establish the truth of sensor inputs, proportionality or legal compliance.
- Dependencies: H5.0 and a separately defined, permissible non-weapon scope.
- Estimated scope: Undetermined. Status: Blocked.

## H4.1 — Physical leakage evaluation

- Horizon: H4 — side-channel research.
- Specification: Investigate power and emissions behavior for a specified device and workload, including the proposed power-flattening target.
- Deliverable: Threat model, measurement protocol, device/setup description, raw traces and an experimentally evaluated prototype if feasible.
- Test: Repeat controlled measurements with calibration, noise characterization, suitable statistical leakage testing and independent review. A software model is identified as simulation, not a physical trace.
- Acceptance criterion: Actual measured results and uncertainty are reported against a precisely defined 0.01% metric; no claim of TEMPEST compliance, Gaussian emissions or attack immunity follows automatically. If hardware or qualified assessment is unavailable, the target remains blocked.
- Dependencies: Representative hardware, instrumentation and specialist review.
- Estimated scope: Large. Status: Not started.

## H4.2 — Scheduling experiment

- Horizon: H4 — side-channel research.
- Specification: Investigate whether instruction scheduling reduces measured leakage for a defined workload and device.
- Deliverable: Experimental scheduler, workload, reproducible baseline and comparative traces.
- Test: Compare scheduled and unscheduled runs under the H4.1 protocol with repeatable measurement and leakage analysis.
- Acceptance criterion: Publish observed effect, uncertainty and failures for the tested conditions; do not infer constant power or resistance to unmeasured attacks.
- Dependencies: H4.1 measurement environment.
- Estimated scope: Large. Status: Not started.

## Completion record template

Work order / status / tested commit / environment / command / exit code / raw artifact and SHA-256 / CI run / reviewer / limitations / remaining blockers. Never mark production, certification, or a horizon complete solely because code exists or a test count is high.

## H1.1 partial delivery record

- Tested files commit: `bcdd4c76d3e4822b487e9735d69ac3845ed44a18` (the tests were run on the identical local files immediately before that commit).
- Environment: Linux x86_64; Lean 4.15.0 and Lake 5.0.0-1165156.
- Command: from repository root, `bash lean/check.sh`. Exit status: 0. Output: `lean/local-check-output.txt` at the tested commit. Output SHA-256: `a1f9d7a8344620897fcb7ec72497094a54020b09fd5e6fe9955a683167164dc3`. No CI run was checked.
- Scope: kernel-checked closed identities for phi squared, phi times its represented inverse, and zeta to the fifth power; imported theorem checks and a concrete negative check. The theorem axiom reports contain no axioms.
- Limitations: not the universal ring axioms, a quotient isomorphism, a Zeckendorf or Pisot proof, a braid proof, code equivalence, independent review, the seven-class evidence pack, or production qualification. The work order and horizon remain incomplete.

## Baseline reconciliation — blocked

- Baseline: `8fddfd17eb776a95e0eec1d1514dd48290c905b4`. The complete Notion import was not diffed against the Git tree; the import report records 34 failed pages including the root Dockerfile. The source ZIP is not available here. Reconciliation details: `evidence/baseline/import-reconciliation.txt`; SHA-256 `11163ed9f1989418e6c85318da95ebe9700c2908d6cc0faa16a5824ab8056bf8`.
- The full baseline suite could not be run: a shell clone of the private repository lacked credentials (exit 128); `evidence/baseline/git-clone.log`, SHA-256 `2e554a39e2bb4414b5e2c3f5a90ebc87b405b5b8231d692704ec6df4580e8f60`. GitHub MCP access does not supply credentials to the shell.
- Partial only: `/data/chronus-venv/bin/python -m pytest -q tests/test_prime_codec.py` in `/data/chronus-baseline`, a synthetic package containing only the two baseline codec and test files with stub package initializers; exit 0, 8 passed. Output: `evidence/baseline/pytest-isolated.log`, SHA-256 `478d38eb52494067e3bcd9a4bb323f7a33c8407927ff7ca238cefb97ac44fcbc`. This is not a full repository test, integration test, CI result or production qualification.
