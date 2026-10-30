# HYBA capability contracts: structural planning foundation

This is a directly implemented, additive planning layer. It is not AGI, an
execution scheduler, an automatic semantic planner, or a deployment approval.
Existing exact-math, governed skills and non-actuating SALAMANDER semantics are
unchanged. No Copilot-generated implementation is required for these files.

## Opt-in MCP integration

A trusted embedding can construct `hyba_mcp.capability_server.CapabilityMCPServer`
in place of `hyba_mcp.server.HybaMCPServer`, with the same constructor arguments
and existing protocol dispatcher. The extension registers `goal_decompose` and
`plan_validate`. The existing CLI and .mcp.json are intentionally unchanged.
The current dispatcher has a process-global registry: do not mix base-server
and extension instances in one process. A per-instance registry and qualified
stdio launcher remain integration work; this is not a claim of production
transport qualification.

## Request and contract

Call `goal_decompose` with `goal_contract` containing `goal`, `criteria` and
optional `subgoals`. Each subgoal has exactly `id`, `skill_id`, `arguments`,
`depends_on`, and `covers`. Supply real registered skill IDs from
`discover_skills`, with literal arguments satisfying their existing schemas.
For example, use `healing.propose_repair` only with the documented telemetry
and fault_type inputs. Do not invent code-writing or live messaging skills.

Without explicit subgoals the result is `needs_clarification`, not a fabricated
four-step plan. With subgoals it returns a versioned plan and structural
validation. Call `plan_validate` with `plan` to check an existing plan.

The validator checks finite JSON, 256 KiB encoded contracts, nesting depth 20,
one to 64 nodes, unique IDs, registered capabilities, missing dependencies,
self-dependencies, cycles, and declared acceptance-criterion coverage. The MCP
boundary also checks literal inputs through the existing control plane. The
pure validator deliberately does not evaluate skill schemas by itself.

The returned order is deterministic. Its SHA-256 plan hash covers the submitted
plan and discovered capability contracts. It is not a signature, source-code
attestation, approval token or permission grant. Contract digests do not pin
executable binaries. A valid plan always has `execution_authorized: false` and
`verification_status: not_run`. Declared criterion coverage does not prove
criterion satisfaction or the correctness of a dependency's meaning.

## Research and authority boundaries

EUCLID/TOE skills remain subject to their current evidence qualifications.
Descriptive factor rankings are not identified causal effects. Trajectory
fidelity is not calibrated forecasting uncertainty. Emergence predicates are
not proof of AGI or consciousness. Lucas/Fibonacci exactness does not establish
real-world validity. SALAMANDER repair proposals do not actuate changes.
`theorem_proven` remains false.

This layer does not execute plans, grant child permissions, bind artifacts,
reserve budgets, infer arbitrary semantic goals, persist job state, cancel
jobs or implement approval tokens. These require separate implementation and
verification before corresponding MCP tools can be advertised. Existing
`invoke_skill` remains the execution path and retains host identity, AL HARAS,
durable audit and bounded-execution requirements. Never bypass those controls
because structural validation passed.

## Validation

Run `python -m pytest tests/test_capability_contracts.py -q` in the repository.
Run existing MCP, expert-skill, SALAMANDER, context and transport suites before
qualifying an embedding. Eight isolated checks of the pure contract logic
passed during authoring; the checked-in pytest suite and full-repository
integration/transport tests were not executed in that isolated environment.
