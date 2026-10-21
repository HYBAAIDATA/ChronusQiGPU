# Original numbered review and current-source retest map — 2026-10-20

Production/publication HOLD. This map does not close any full finding or supply an owner sign-off.

## Original review recovered

Versioned source: https://github.com/PhiEnterprise1/EuclidPhiEnterprise/blob/7a2e749ef5f4c62299fed14eaac2ebf5e6927bde/docs/reviews/OVID_THESEUS_CHRONUS_PRODUCTION_20261004.md

The verbatim file is `docs/reviews/OVID_THESEUS_CHRONUS_PRODUCTION_20261004.md`, SHA-256 `86214ff8272c2154fdb4a6dfaeb0c407739118b5e244c904a723604dc61dba3c`, Git blob `3609cceb5c85508e609798cc87b3b0d278f8c829`. The review dated 2026-10-04 references baseline `f51cef18784da84120cf69aa21a6a656590898fa`. It is **static review**, not historical runtime proof. It contains **R01–R12**, not just R01–R09. Do not silently drop R10–R12.

## Ownership decision reconciliation

The historical text assigns durable ownership to Ovid and projections to Theseus. The user's later explicit product decision controls this closeout: **Ovid = versioned transform/materialisation facade; Theseus = durable custody/recovery; PULVINI = folding only**. The original review is retained unchanged as evidence, not executed as an instruction to invert the current split. Its single-authority, isolation, sealed-commit, projection-lineage and recovery obligations remain. R01 needs an explicit authority/migration map, not label replacement or a parallel custody root.

## Current-source mapping

| Finding | Evidence inspected/tested | Current disposition and remaining acceptance |
| --- | --- | --- |
| R01 ownership | Existing `aethel/enterprise/custody.py`; competing `aethel/ovid_authority.py` and `aethel/theseus_projection.py` inspected at candidate | OPEN. Reconcile current product split; prove one durable authority behind facade and complete rebuild/lineage. No source migration in this tranche. |
| R02 tenant/path | Prior 22 memory tests plus new runtime/restart/refusal callers; custody path guards statically inspected | PARTIAL. Full custody collision/traversal/absolute/symlink/copy and trusted principal mapping unqualified. |
| R03 sealed commit | Journal-local intent/seal cases; custody `recover` at line 264 and `_load_envelope` at line 406 inspected | OPEN. Recovery ignores returned sealed rows before scanning files; no complete crash/divergent-generation/delete matrix or previous committed payload recovery. |
| R04 journal | Prior 33 journal-local tests, normal and optimized; 85-test combined logs | PARTIAL PASS only. Full custody transaction integration, retention/schema policy and owner review still required. |
| R05 process transaction | Custody `put` line 433, `delete` line 696, `backup` line 799, `restore` line 823 inspected | OPEN. Generation/quota/idempotency decisions precede process lock; backup not proven consistent; restore removes live directories before validated staging. No concurrent-writer/restore runtime closure. |
| R06 fsync/readiness | Journal-local repair/fsync tests; custody `_atomic_write_json` line 80, `_append_event` line 257, `recover`/health inspected | PARTIAL. Full file+directory/provenance durability, per-record degraded state and read-only no-heal remain unqualified. |
| R07 scoped memory ownership | Prior 22 memory cases + real runtime/client/wire subset | PARTIAL PASS. Caller regression fixed; full app/principal/multi-process memory and external caller qualification remain. |
| R08 physical residency | Fake physical labels refused; tamper/restart/host-output cases pass | PARTIAL. Real transfer/release/budget/reattach adapter and durable facade integration NOT implemented or measured. Host output is not GPU evidence. |
| R09 attested ontology reads | Earlier source inspection found `get_edge` path present | SOURCE PRESENT, NOT QUALIFIED. Actual tampered-edge traversal/topology and policy tests not run here. |
| R10 numeric/resource limits | Original review retained | OPEN / NOT RETESTED. No numeric overflow/strict integral/admission/long-chain closure asserted. |
| R11 basic triad/form invariants | Original review retained; competing authority sources inspected | OPEN / NOT RETESTED. No fresh-process basic-store recovery/folded-form invariant proof. |
| R12 discriminating acceptance | New memory/journal/caller negative controls produce expected failures on original sources | PARTIAL. This does not repair or qualify every original vacuous assertion or substitute real device dispatch. |

Line numbers refer to the unchanged candidate custody source (Git blob `aef7e02953924bbd9f6275a46b412cf3259ca9f5`), not to a newly fixed implementation. The caller patch does not modify custody. Dependencies and fault windows must be exercised before marking any full R01/R03/R05 PASS. Preserve valid committed generations before attempting sealed-only recovery; filtering journal rows alone cannot undo an overwritten primary.
