# Governed promotion, core release engineering, and service catalogue

## Implemented

- Commit-bound promotion receipts, required role sets, author/approver separation, unique approvers per role, and all-required-gates-PASS enforcement. SKIP cannot promote.
- GitHub environment policy manifest and an admin-only, dry-run-by-default environment configurator.
- Promotion workflow with immutable target SHA, environment gates, PR-review role verification, signed receipt artifact, and no direct repository state mutation.
- Hardware-acceptance workflow for the Miner self-hosted OpenCL runner.
- Release tag parsing, exact Pythia/Enterprise pins, staging ranges, major-upgrade approval, version consistency and checksums.
- Future `mla1517-core` release workflow/build/publish scripts supplied as extraction templates only.
- Executable dependency-injected references for Flow, Ontology, Agent Fabric, Quality, Evidence, Share, Federate, Vault/legal hold, Edge, Studio, Functions, Insight, Deploy and Proof.
- Quantum Access, Privacy Compute, Autonomous Operations and Energy remain research-gated and fail closed without explicit evidence/enablement.

## Developer evidence

31 dependency-free tests pass and all Python/workflow files compile or parse.

## Required configuration before promotion can run

1. Copy `config/promotion-roles.example.json` to `config/promotion-roles.json` and replace placeholders with real GitHub identities through a reviewed change.
2. A repository administrator runs `scripts/configure_environments.py --apply` with an admin-capable token.
3. Add `PROMOTION_SIGNING_KEY` as a protected environment secret.
4. Ensure target commits are associated with reviewed pull requests; environment approval alone is not treated as evidence of reviewer identity.

## Explicit boundaries

- The workflow issues a signed promotion receipt artifact. Persistent subsystem-state change requires a separate reviewed repository change.
- Environment protection was not configured by this change because reviewer identities and an administrative token were unavailable.
- No core package was built or published, and no private-index credentials were used.
- Reference services require injected production connectors, policy engines, sandboxes, stores and attesters; they are not represented as deployed integrations.
