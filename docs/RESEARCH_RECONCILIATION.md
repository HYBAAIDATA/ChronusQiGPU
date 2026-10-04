# Research reconciliation

The workspace research pages assert a large catalogue of advantages. This document gives every substantive one of them a disposition, so the repository carries the pages' *epistemic state* instead of re-asserting a claim by association with the page it came from.

The machine-readable form is `chronus/v33/research_reconciliation.py`; the gate is `tests/test_chronus_v33/test_research_reconciliation.py`.

## The rule

**Nothing is refuted unless it was tested.**

A claim is `TESTED_AND_REFUTED` only when an experiment ran, in a stated regime, and failed *there*. A claim no experiment has addressed is `UNTESTED`, and it is not refuted: an experiment on a different question, in a different regime, does not settle it. That is enforced structurally, not by convention — `TESTED_AND_REFUTED` requires a `regime` and an `outcome`, `UNTESTED` requires the `falsification` that would settle it, neither may borrow the other's evidence, and `test_the_refuted_lint_stays_silent_on_untested_claims` fails if an untested claim ever reaches the refuted register.

| Disposition | Meaning |
| --- | --- |
| `VERIFIED` | Tested in this repository, in the stated regime, and passes. May be asserted within that regime. |
| `TESTED_AND_REFUTED` | An experiment ran and the claim failed **in the stated regime**. Says nothing about any other regime. |
| `UNTESTED` | No experiment addresses it. Must not be asserted, and must not be called refuted. |
| `PROHIBITED` | A boundary rather than a result: barred from generated pages and release text by policy, whatever any experiment would say. |
| `HYPOTHESIS` | Plausible, unevidenced. Stays isolated under `experiments/`. |

Two lints, deliberately separate. `al_haras/refuted_claims.py` bars claims that were tested and failed. `al_haras/unmeasured_claims.py` bars claims that were never tested. Putting the second kind into the first would let an untested claim be dismissed by someone else's experiment on a different question.

## Mining

| Claim | Disposition | Basis |
| --- | --- | --- |
| φ-compression matches or beats uniform 4-bit on structured data | `TESTED_AND_REFUTED` | `baseline_comparison_v4.py`, sinusoidal: φ 3.06× / 0.1022 error vs uniform 4-bit 4.00× / 0.0803; no improvement over the NULL model |
| The φ-specific components (lattice, multiscale) contribute to compression | `TESTED_AND_REFUTED` | `rate_distortion_decomposition.py`: φ-only 0.92× / 0.2735 error; engineering-only 4.00× / 0.1072 |
| φ-compression outperforms uniform quantization on real transformer KV-cache data | `UNTESTED` | the sheet marks it Pending, not Failed. Falsifier: `llm_kv_cache_real_model.py`, PPL degradation ≤ 0.5 at 2× |
| Up to 32:1 compression from 32-face folding | `UNTESTED` | falsifier: measure the sheet's own `compression_ratio` over payload + metadata on a stated corpus |
| Golden-ratio partitioning resists hash collisions | `UNTESTED` | falsifier: birthday search, phi partition vs uniform, equal nonce budget, full double-SHA256 predicate |
| Manifold key search is quantum-resistant cryptography | `UNTESTED` | falsifier: state the hardness assumption, then a reduction or an attack cost. None is stated |
| Manifold structure makes brute-force nonce search exponentially harder | `UNTESTED` | falsifier: candidates per second on the phi schedule vs uniform at equal accepted-work accounting |

## Intelligence

| Claim | Disposition | Basis |
| --- | --- | --- |
| MPS compression makes architecture search polynomial in depth | `UNTESTED` | falsifier: run the search with and without MPS at equal evaluation budget |
| φ-resonance-weighted correction improves correction fidelity | `UNTESTED` | falsifier: fixed-rate depolarising channel, logical error rate with and without weighting |
| φ-resonance identifies functional DNA patterns | `UNTESTED` | falsifier: labelled functional-annotation corpus, precision/recall against a motif baseline |
| Grassmannian subspaces give a natural commitment scheme | `UNTESTED` | falsifier: a hiding and binding argument, or a distinguishing attack cost. No construction exists |
| Self-healing emerges from the architecture | `HYPOTHESIS` | isolated under `experiments/`; the six behaviours are never enumerated |

## Quantum

| Claim | Disposition | Basis |
| --- | --- | --- |
| The wide register is exact for the stabilizer state class | `VERIFIED` | 10,000 qubits, 20,000 tableau bits, cut entropy 1, `materialised False`; registered as `vqc-stabilizer-full-width` |
| Quantum walk gives exponential speedup for path finding | `PROHIBITED` | must not claim this; policy bar on the phrase, not a test result. The in-tree walk is exact and verifiable; the speedup is unmeasured |
| Quantum interference gives exponential speedup for optimization landscapes | `PROHIBITED` | must not claim this; no landscape is named, so the claim is unfalsifiable as written |
| Tensor-network decomposition gives exponential compression | `UNTESTED` | falsifier: bits per element on a stated tensor family vs a fixed-rank baseline at equal error |
| The system is a physical quantum computer | `PROHIBITED` | no QPU provider is bound; the doctrine page keeps this sentence RESTRICTED/INTERNAL. No experiment would make it assertable |

## What this does not do

It does not implement the catalogue. Nothing here promotes a use case to a capability, and no entry is a performance result. It also does not dismiss the catalogue: most of it is `UNTESTED`, which is a statement about the absence of an experiment, not about the claim's truth. Where a page describes a real, bounded, tested artefact — the Kairos mining-orchestration reasoning layer and lab service, the exact stabiliser register, the distance-3 reference decoder — that artefact keeps its own boundary document and its own tests, and this file records the disposition of the claim, not the capability.

## Correction history

The first revision of this file dispositioned eleven claims as `REFUTED` or `PROHIBITED` and extended `al_haras/refuted_claims.py` with nine of the pages' phrasings. That was wrong. Nine of those eleven had never been tested: they were unmeasured, and an experiment on a different question does not refute them. `refuted_claims.py` is unchanged by this work; the nine phrasings live in `al_haras/unmeasured_claims.py`, and only two claims in the whole catalogue are `TESTED_AND_REFUTED` — both because a named benchmark ran in a named regime and failed there.
