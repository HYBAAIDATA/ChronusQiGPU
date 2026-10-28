# GitHub Copilot — repository-wide CI GREEN workstream

**Named owner:** GitHub Copilot (owner-designated agent). **Tracking:** [#96](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/96). **Independent QC:** ChatGPT ([#94](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/94)). This is separate from Copilot's Tensor/Kellogg assignment.

## Mission

Bring **all required repository GitHub Actions CI workflows** to a reproducible GREEN state using actual executed jobs/tests on exact candidate commits. Resolve both infrastructure-level `startup_failure` and genuine code/test/package failures. Do not convert failing or required checks into optional/no-op jobs, fake artifacts or passing statuses.

## Execution obligations

1. Pin main and each relevant candidate PR commit; inventory required workflows, matrix entries, triggers, action versions, runner settings, secrets/dependencies, branch-protection requirements and testing obligations. Preserve existing required checks; do not silently narrow them.
2. Separate job startup failures (`startup_failure`, job never ran, no action minutes) from jobs that ran and failed real tests. Fix repository-controlled failures; document uncontrollable runner quota/provider faults as `INFRA_BLOCKED`, not green.
3. For every applicable workflow, rerun the actual jobs, validate each command and exit code, preserve links to workflow and job runs, evidence of steps executed, test counts, logs/artifact digest and exact source/package SHA. Green badge alone is insufficient.
4. Coordinate version, installation, test coverage, package resolution and backend issues with Perplexity/CHRONUS #91, Sider/TURING #92 and Copilot/Tensor #93. Do not invade their semantic authority or rewrite tests merely to satisfy CI.
5. For the integration candidate, require clean wheel/sdist install, independent known-answer/negative tests and product-contract tests to actually execute, plus whatever cross-system CI gates are required by canonical approval.
6. Re-run current SHA after merging or changing prerequisites. Produce a `CI_GREEN_CLOSURE_DOSSIER.md` listing every required workflow, exact SHA, executed job evidence, PASS/FAIL/INFRA_BLOCKED and unresolved risks, and open appropriate CI-only remediation PRs.
7. Submit evidence to independent QC. **The owner authorizes final production/readiness status after QC; CI repair alone grants neither product readiness nor mathematical correctness.**

## External benchmarking and parity boundaries

Final system validation is **real workload result parity**, not comparative benchmarking. Only real competing systems can be compared in a separately approved competitive benchmark. Required CI may run actual runtime, performance-envelope or resource-safety tests without making external performance claims.

## Handover

- [Main agent and QC directive](08_OWNER_DIRECTIVE_PRODUCTION_PARITY.md)
- [Cross-system independent QC](04_JOINT_INTEGRATION_QC.md)
- [Acceptance matrix](06_ACCEPTANCE_MATRIX.md)
- [Tracking issue #96](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/96)
