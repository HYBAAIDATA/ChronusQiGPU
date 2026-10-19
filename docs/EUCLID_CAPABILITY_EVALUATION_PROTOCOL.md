# Euclid like-for-like capability evaluation protocol (not benchmark results)

## Claim boundary

The target is independently reproducible competitive performance. This document does not assert AGI, ASI, scientific superiority, a solved Millennium problem, or increased intelligence from Lucas-number growth. Counts of repositories, skills, source files, unit tests and catalogue entries are not intelligence scores.

## Two separate comparison tracks

1. Model-level track: identical frozen task and prompt sets, tool access, context/response limits, inference budget, number of attempts, grading rules and failure accounting. Record exact model identifiers, provider revision/date, inference parameters and endpoint. Hosted provider internals may be undisclosed; call this task/tool/budget-matched, not hardware-identical or bitwise reproducible.
2. System-level track: Euclid plus its complete routing/tool/memory/skill stack versus each competitor's declared stack under the same permitted tools and budget. Declare external model calls, retrieval sources and human intervention. Do not present a tool-rich system versus a tool-free model as like-for-like.

## Preregister before observing results

Freeze taskset, prompts, hidden holdout, grader implementation, resource policy, stopping/retry rules, hypotheses, primary metric, meaningful superiority margin, sample-size/power rationale and uncertainty method. Record contamination/overlap screening and limitations. Include math proof-checking, repo defect repair with held-out regressions, retrieval/grounding, planning/action safety, memory recovery and tool execution. Millennium work is graded on explicit theorem statements and checkable proofs, not a synthetic mass-gap number or a finite passing fixture.

## Evidence retained per run

Immutable task/prompt/grader/policy hashes; source commit and installed artifact digest; exact provider/model revision; environment/container digest and hardware; seed or disclosed stochastic settings; complete inputs/outputs/tool traces; timestamps; latency, cost and resource observations with units; failures, refusals and timeouts; independent outcome evidence and approval identity. Keep credentials out of records. Protect hidden holdout answers from candidates and graders whose role excludes them.

Compare paired identical tasks; publish success rates with numerators/denominators, uncertainty intervals, paired differences and latency/cost distributions. Do not drop failed runs or compare selectively favourable subsets. Report supported domains rather than a universal ranking. Independent assessors must reproduce the scored artifact and review any public claim.

## Lucas scaling ablation

Treat the proposed 10/12/15/20 settings as named configurations, not measured intelligence multipliers. Hold models, tasks, tools, budgets and graders fixed; vary only the documented Lucas configuration. Run an unscaled baseline and repeated paired trials. Publish actual improvements, null results and regressions, including resource costs. If exponent notation refers to different values, bind the exact parameter definition in the run manifest before execution. No exponential IQ claim is implied.

## Present availability

No like-for-like competitor runs have executed in this workstream. No competitor credentials/endpoints, frozen benchmark dataset, independent scoring service or approved inference budget is configured. Scientific/model comparison state is NOT_RUN, not zero-performance, pass, superiority or inferiority. PR #66 remains blocked/draft; CI checks are unreadable through the current token (403) and recorded reviews are absent. Integration snapshots are catalogued, not promoted or deployed.
