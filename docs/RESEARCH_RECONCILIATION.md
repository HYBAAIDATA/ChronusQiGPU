# Research reconciliation

The workspace research pages assert a large catalogue of advantages. This document gives every substantive one of them a disposition, so the repository carries the pages' *conclusions* — including the negative ones — instead of re-asserting a claim by association with the page it came from.

The machine-readable form is `chronus/v33/research_reconciliation.py`; the gate is `tests/test_chronus_v33/test_research_reconciliation.py`. `REFUTED` and `PROHIBITED` entries are executable: the entry stores the page's own phrasing and the named in-repo linter must catch it.

## Dispositions

| Disposition | Meaning |
| --- | --- |
| `VERIFIED` | Backed by an in-repo test or benchmark. May be asserted. |
| `REFUTED` | In-repo evidence contradicts it. Must not be asserted. |
| `PROHIBITED` | Must be absent from generated pages and release text. |
| `HYPOTHESIS` | Plausible, unevidenced. Stays isolated under `experiments/`. |
| `UNBACKED` | Asserted in a source page with no in-repo evidence either way. |

## The headline

`CLAIMS_BOUNDARY_SHEET_V4` (June 30, 2026) is the most honest document in the set, and it refutes the catalogue's central claim. Its own decision criterion is met in the negative: φ does not beat uniform 8-bit on ≥ 2/3 data types, and does not beat the NULL model. The rate-distortion decomposition attributes every compression gain to the engineering stack — adaptive density, fallback, lattice regeneration — while φ-only lands at 0.92× compression with 0.2735 error, worse than baseline. Gate G1 (null model) is marked **FAILED**; G4, G5 and G6 have never been run.

`USE_CASES` then asserts the opposite across 80+ entries, in the form of one-line `Advantage:` claims with no measurement behind them. That is the gap this reconciliation closes: the pages may keep their catalogue, but the claims that the evidence contradicts, or that policy prohibits, now trip a lint.

## Mining

| Claim | Disposition | Evidence |
| --- | --- | --- |
| φ-compression outperforms uniform quantization | `REFUTED` | `benchmarks/baseline_comparison_v4.py`; decision criterion met in the negative |
| Up to 32:1 compression from 32-face folding | `PROHIBITED` | face-index quantisation is a lossy codebook, not a compression result |
| Golden-ratio partitioning resists hash collisions | `PROHIBITED` | non-uniform output does not lower collision probability in SHA-256d |
| Manifold key search is quantum-resistant cryptography | `PROHIBITED` | `STRICT_QUANTUM_BOUNDARY.md` category 3 |
| Manifold structure makes brute-force nonce search exponentially harder | `PROHIBITED` | every candidate is still checked against the full double-SHA256 predicate |

## Intelligence

| Claim | Disposition | Evidence |
| --- | --- | --- |
| MPS compression makes architecture search polynomial in depth | `PROHIBITED` | bond dimension bounds representable entanglement, not the search |
| φ-resonance-weighted correction improves correction fidelity | `PROHIBITED` | the in-tree decoder is a distance-3 reference decoder with no weighting |
| φ-resonance identifies functional DNA patterns | `PROHIBITED` | no in-repo genomic result exists |
| Self-healing emerges from the architecture | `HYPOTHESIS` | isolated under `experiments/`; the six behaviours are never enumerated |
| Grassmannian subspaces give a natural commitment scheme | `UNBACKED` | no in-repo construction, proof, or hiding argument |

## Quantum

| Claim | Disposition | Evidence |
| --- | --- | --- |
| The wide register is exact for the stabilizer state class | `VERIFIED` | registered as `vqc-stabilizer-full-width` in the executable research intake |
| Quantum walk gives exponential speedup for path finding | `PROHIBITED` | the in-tree walk is exact and verifiable; the speedup claim is neither |
| Quantum interference gives exponential speedup for optimization landscapes | `PROHIBITED` | variational methods are heuristics; no landscape is specified or measured |
| Tensor-network decomposition gives exponential compression | `PROHIBITED` | low entanglement bounds the representation, not the compression ratio |
| The system is a physical quantum computer | `PROHIBITED` | caught by `capabilities.audit_claims`; the doctrine page keeps it RESTRICTED/INTERNAL |

## What this does not do

It does not implement the catalogue. Nothing here promotes a use case to a capability, and no entry in this file is a performance result. Where a page describes a real, bounded, tested artefact — the Kairos mining-orchestration reasoning layer and lab service, the exact stabiliser register, the distance-3 reference decoder — that artefact keeps its own boundary document and its own tests, and this file records the disposition of the claim, not the capability.
