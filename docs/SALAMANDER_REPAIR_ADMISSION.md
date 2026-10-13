# Salamander repository-healing admission — scoped repair

## Outcome and fixed baseline

Task SALAMANDER-HEAL-20261013. Repository PhiEnterprise1/EuclidPhiEnterprise, main baseline 6688e83c22d36dc16dfd5516e9e7d81959c84438. This work repairs unsafe repair-admission paths; it does not certify repository-wide production readiness or implement a production sandbox.

## Reproduced defects and changes

The agentic optimizer wrote live source before running a callback or shell command. A callback returning True, 1 or a nonempty string authorized publication. A shell command could create a marker and authorize a candidate without any bound test evidence. The resonance optimizer directly mutated the live file and treated its structural score as success. The separate self-repair entry point accepted an auto-apply flag and an unrelated passing test as sufficient to change source. Dependency proposal generation also appended requirements before any approval; it is now read-only.

Both repair entry points now delegate to the existing RepairTransaction primitive. Baseline and candidate bytes remain separate until a host-supplied validator returns exact digest-bound, nonempty, isolated regression evidence. Without that validator, source is unchanged. Legacy command/callback arguments are rejected, not executed. An auto-apply flag alone cannot authorize a write. The live resonance-mutator bypass is blocked; independently generated candidates can still enter the transaction gate.

The shared transaction now excludes tests, nested test directories, test-named files and conftest.py from automatic repair. Existing scope remains Intelligence, core_engine and pythagoras Python files only. Symlinks, outside targets, protected mining paths, stale source, failed evidence and syntax errors are refused. Requirements changes no longer install dependencies from the repair-application path; dependency/environment changes require human review.

The self-repair cycle can receive a host-configured validator. Default CLI and engine paths configure none and therefore remain diagnosis/proposal-only. No flag was enabled or production runtime activated. Three existing tests were strengthened to reject callbacks/commands rather than bless them as sandbox evidence; unrelated assertions were preserved.

## Observed validation

37 new parameterized gate cases on the baseline: 36 failed, 1 passed (exit 1). Eight are behavioral bypass counterexamples; the other 28 enforce the new validator API, so they are not 28 independent runtime defects.

Patched: 37 new cases plus 14 selected existing cases passed, 51 total (exit 0). Black check at line length 100, Flake8 with repository-applicable ignores, Ruff E9/F and compileall each exited 0. Exact commands, tool versions and source hashes are in salamander_repair_admission_validation.json.

Real retrieved original modules were tested in an isolated namespace. Full package initialization, actual conftests and installed artifacts were excluded. The 14 compatibility cases retain original test bodies, apart from the three deliberate admission-contract corrections. Production-directory scans and engine-dependent cases were not executed.

Positive validator cases use an explicitly labelled unit contract double. They prove receipt admission and atomic-publication behavior, NOT an OS sandbox, independent review, or production healing. No actual production validator is available in this environment.

## Production-closure queue, in order

1. **Trusted execution and approval (P0):** configure a bounded OS-enforced repair executor with an immutable test manifest, no production secrets, no network/mining, controlled mounts and baseline/candidate differential tests. Connect per-change AL HARAS approval, approved scope and identities; an in-process callback is not this executor.
2. **Truthful healing evidence (P0):** SelfRepairEngine.apply_repair currently marks proposals applied and increments success without an actuator or outcome probe. Replace that with registered approved actions and independently verified outcomes. The wiring inspector's import availability, predetermined edges and dictionary-only receptors are not measured active wiring; qualify actual connections before reporting recovery.
3. **Durable custody (P1):** replace or qualify the local pickle-backed Veritas ledger, which is not canonical Theseus custody or independent verification. Bind test manifests, source hashes, executor identity and approval receipts. Publication and audit persistence are not jointly atomic today; post-commit audit failure is explicitly reported, not called rollback.
4. **Defect-driven intelligence repair (P1):** repair the measured memory-capacity overrun and learning-evidence snapshot loss; correct executor failure propagation and outcome learning. Use differential tests, not confidence scores or synthetic success labels.
5. **Exact-operator repairs (P1):** independently review PR #65; repair reproduced VQE non-Hermitian admission and QAOA endpoint coercion. Generated Salamander mathematical recipes remain proposals, not proven exact operators. Millennium finite examples do not establish general Yang–Mills or Poincare theorems.
6. **Whole-system release gates:** run repository/installed-package tests, existing import/ownership/defect inventories and release gates, security/provenance and compatibility/rollback qualification. Existing CI already owns these checks; no duplicate workflow was added. Previous check-run access was unavailable (403); fresh CI status is not claimed here.
7. **Human release authority:** nominate engineering/security reviewer and release approver, agree deployment target and quantitative SLOs, approve a fixed artifact, then controlled staging/canary and rollback rehearsal. No production activation before these gates.

## Boundaries

Feature branch and draft PR only. No merge, main push, tag, publication, deployment, mining, pool connection or external LLM invocation. SHA256d, protocol hashing, signatures, target checks and acceptance authority were not modified. Single-file transactions serialize cooperating writers; they are not multi-file atomicity, protection against hostile local writers, or a universal mathematical proof.
