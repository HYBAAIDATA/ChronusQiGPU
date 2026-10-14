# Gap-closure register — the seven exact-only blockers

**Status:** DRAFT — closure set, not implementation.
**Source of record:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md`.
**Baseline:** `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.
**Date:** 2026-10-13.

---

This register is the index over the closure set. Each blocker is addressed by
one document; each document states what it closes and what it does not.

| # | Blocker | Document | Closed here | Still open |
|---|---|---|---|---|
| 1 | Wythoff bijection | `02-wythoff-bijection.md` | 1-based convention; exact-comparison Beatty floors; inverse totality | bijectivity proof |
| 2 | Metallic decomposition | `03-metallic-digit-language.md` | Ostrowski alphabet; legality predicate | uniqueness proof; negative powers |
| 3 | H4 composition | `01-h4-composition-contracts.md` | admissible set; `z_to_qsqrt5`; termination/tie/zero; DphiT wiring; Zeckendorf reuse; Cassini semantics | **covering radius; `Vec4Context`** |
| 4 | Quantum arsenal | `04-quantum-arsenal-embedding.md` | dimension options; evolution domain; classical-operator disposition; variational contract | dimension choice; 4 methods absent |
| 5 | TOE bridge | `05-toe-bridge-typing.md` | return taxonomy; distribution/outcome split; zero-state rule; bounded frontend claim | typing implementation |
| 6 | Consortium ledger | `06-consortium-ledger-separation.md` | claim-class separation; identity requirements; throughput boundary; replay | ledger read surface |
| 7 | No-simulator semantics | `07-no-simulator-semantics.md` | three-way distinction; vocabulary ruling; memory bound | none — wording only |

## Owner decisions required

| Decision | Blocks | Reference |
|---|---|---|
| `Vec4Context` target space | H4 §4 implementation; covering radius | `01` §7 |
| Admissible bound B | H4 §2, §5; covering radius | `01` §7 |
| Digit language approval | metallic §3, §4 | `03` §9 |
| Dimensional choice (120 vs 128) | arsenal §2 | `04` §8 |
| Evolution domain | arsenal §3 | `04` §8 |
| Four-method disposition | arsenal §6 | `04` §8 |

All six are canonical calls. Owner: @EuclidUltimaPhi.

## The one blocker not closeable by specification

**Covering radius.** The review's own standard:

> "a rigorously derived covering radius. Sampling cannot prove universal coverage."

The 40k-probe `m32_covering_deg` result in
`reports/toe_universal_principle_evidence.json` is `evidence_class: MEASURED`
and cannot become a certificate by repetition. The forced order:

```
admissible set A(B)          [specified in 01 §2]
  -> termination + tie rules  [specified in 01 §5]
  -> radius DERIVED           [OPEN — needs Vec4Context + B]
  -> certificate              [OPEN]
```

Documents 01–07 close six of seven blockers in whole or part. The seventh
component of blocker 3 — the covering radius — stays open by decision, not by
omission.

## What this set does not do

No implementation. No tests. No code. No merge, release, deployment or mining
activation. No `MEASURED` result promoted to `VERIFIED`. `theorem_proven`
remains False.

## Governance note

**PR #42** shows `merged: true`, `merged_by: pythiaphi`, `closed_at
2026-10-13T10:31:58Z`, while its own body reads *"Owner approval required:
@EuclidUltimaPhi"* and `theorem_proven remains False`. If `theorem_proven:
False` is intended to block canonical promotion, that merge is a separate
governance event requiring a decision of its own.
