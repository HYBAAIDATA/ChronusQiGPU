# CHRONUS / TURING / Tensor — shared agent handover (28 October 2026)

> **Documentation-only handover.** This folder is a portable copy of the agent requirements and implementation prompts; it neither modifies any authoritative Notion page nor qualifies a system for production.

## Start here

**Start with [08_OWNER_DIRECTIVE_PRODUCTION_PARITY.md](08_OWNER_DIRECTIVE_PRODUCTION_PARITY.md)** for the owner's superseding workstream acceptance rule (real-workload parity, distinct product classes, competitive benchmarks only), then [00_READ_ME_FIRST.md](00_READ_ME_FIRST.md) and [07_SHORT_MASTER_PROMPT.md](07_SHORT_MASTER_PROMPT.md).

| Assignment | Document |
| --- | --- |
| CHRONUS execution and graphics consolidation | [01_CHRONUS_implementation_prompt.md](01_CHRONUS_implementation_prompt.md) |
| TURING independent VQC elevation | [02_TURING_implementation_prompt.md](02_TURING_implementation_prompt.md) |
| Tensor/Kellogg mathematical and runtime elevation | [03_TENSOR_implementation_prompt.md](03_TENSOR_implementation_prompt.md) |
| Independent cross-system QC | [04_JOINT_INTEGRATION_QC.md](04_JOINT_INTEGRATION_QC.md) |
| Consolidated Notion requirements and primary links | [05_NOTION_REQUIREMENTS_DIGEST.md](05_NOTION_REQUIREMENTS_DIGEST.md) |
| Evidence and acceptance gates | [06_ACCEPTANCE_MATRIX.md](06_ACCEPTANCE_MATRIX.md) |

**Repository evidence baseline:** `c4ea01fd1b82d411db3fd394c96fc143579b08b5` on `main`. Re-pin and re-audit the current exact HEAD before implementation. Historical findings are retest obligations, not proven current defects.

**Authority:** CHRONUS owns execution; TURING owns VQC semantics; Kellogg owns exact tensor mathematics; `tensor/` owns logical tensor contracts; OVID owns transformations; THESEUS owns durable custody; AL HARAS governs security; PYTHIA owns mining-domain semantics. Consult the referenced canonical Notion manuals before material changes.

**Operating rule:** three non-overlapping implementation PRs, independent QC, no changes to owner-controlled architecture or claim status without explicit approval, no removal without verified functional replacement, no synthetic production evidence, and no automatic publication. Agents must preserve negative results and record unresolved gates as unavailable or gated.

**Document provenance:** prepared as a requirements handover on 28 October 2026; source citations and limitations are in the digest. These Markdown files are available on the repository branch that contains them and become available on `main` after merge.

## Assigned workstreams and independent QC

| Workstream | GitHub tracker | Accountable role |
| --- | --- | --- |
| CHRONUS | [#91](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/91) | Single implementation agent, owner to assign |
| TURING | [#92](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/92) | Single implementation agent, owner to assign |
| Tensor/Kellogg | [#93](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/93) | Single implementation agent, owner to assign |
| Independent QC | [#94](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/94) | ChatGPT QC as appointed in owner conversation |

Never mark a production-ready status merely because a task/PR is complete. The final acceptance is **actual workload correctness/parity and recovery**, independently verified, then owner-approved for its declared profile. Competitor-only benchmarking is separate.
