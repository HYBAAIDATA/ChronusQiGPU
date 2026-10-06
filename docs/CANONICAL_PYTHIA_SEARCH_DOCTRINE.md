# Canonical PYTHIA Structured-Search Doctrine

**Status: CANONICAL — OWNER-LOCKED**

This document is the governing mining-search doctrine for `QuantumPhi2/PhiMiner`.
It records an architectural decision, not a suggestion or an optional experiment.

**Change control:** no agent, contributor, automated refactor, audit, benchmark,
review, migration, or external convention may alter, demote, bypass, reinterpret,
or replace this doctrine without explicit written approval from the repository owner.
Absent that approval, a conflicting change must be rejected.

## Canonical decision

PYTHIA mining is a **structured-search system with complete nonce-estate coverage**.

The nonce domain is not treated as conceptually structureless work merely because
Bitcoin proof remains SHA256d. PYTHIA is designed to identify, represent, learn and
use mathematical structure to determine search order while preserving complete
coverage of the authorised nonce estate.

The canonical production search identity is **Hendrix**.

The production itinerary is:

```text
real Stratum job
-> PYTHIA observation / memory / intelligence / supposition
-> Hendrix structured-search plan
-> 32-face
-> 11D representation
-> H4 / 600 logical vertices
-> Turing / Hilbert support where selected
-> Chronus execution
-> candidate
-> independent host SHA256d + negotiated target
-> verified submission
-> literal pool outcome
-> PYTHIA learning
-> Salamander bounded recovery / optimisation
```

The 32-face, 11D, H4/600 and Turing/Hilbert structures support the Hendrix
itinerary. They do not replace Hendrix as the search identity.

## Search invariant

The following are release invariants:

1. **Structured search is canonical.** Flat/uniform enumeration may exist as a
   reference, fallback, control or completeness mechanism, but it may not be
   promoted over the canonical structured-search route by default.
2. **Full coverage is preserved.** Structure changes order and prioritisation;
   it must not silently discard authorised nonce domains.
3. **Hendrix is the default production traversal.**
4. **PYTHIA owns mining intelligence and final SearchPlan composition.**
5. PYTHIA may compose its authorised support arsenal, including supposition,
   tunnelling, annealing, swarming and entanglement, plus existing Turing,
   Kellogg and Chronus capabilities, without transferring PYTHIA's mining authority.
6. **SHA256d plus the negotiated target remains the sole share-validity proof.**
   A resonance score, model output, tensor result, VQC result or search position
   cannot declare a valid share.
7. **Pool acceptance is literal external evidence.** Submission is not acceptance.
8. The architecture's complexity objective is structure-directed **O(1) candidate
   resolution in the PYTHIA search model**. This is a design objective and must not
   be reported as a proved asymptotic or measured performance claim until separately
   demonstrated. It must not be silently replaced with an O(N) flat-search design
   decision merely because the O(1) objective still requires evidence.

## Resonance evidence and the 0.5 structural band

Within this project, `R_phi >= 0.5` is the declared structural band used by the
current resonance analysis/training surfaces. It is a search/representation signal,
not a Bitcoin proof predicate.

The provenance-bound 200-row analysis currently committed at
`artifacts/pythia_training/real_nonce_analysis_200_fresh.json` records:

- 200 real, locally PoW-verified winning nonces;
- threshold: `R_phi >= 0.5`;
- real-corpus hits: **122/200**;
- real-corpus rate: **0.61 (61.0%)**;
- fixed-seed uniform-uint32 control rate: **0.61805 (61.805%)**.

Those figures must not be swapped or conflated. In particular, the committed
artifact does not establish winner-vs-uniform discrimination at the 0.5 threshold.
That statistical result does **not** authorise an architectural decision to replace
PYTHIA's structured-search design with blind search.

The canonical design decision is broader: PYTHIA treats the nonce estate as a
structured search space, learns and exploits the project's declared mathematical
representations, preserves complete coverage, and leaves final validity to SHA256d.

New evidence may refine models, ordering, thresholds or measured effectiveness.
It may not revoke the structured-search doctrine without explicit owner approval.

## Decisions that are not permitted without owner approval

A change must be rejected if it would, by default:

- describe PYTHIA mining as blind, random or structureless search;
- make flat exhaustive ordering the canonical production search identity;
- remove Hendrix as the default production traversal;
- prune the nonce estate without an authorised completeness contract;
- transfer final SearchPlan authority away from PYTHIA;
- remove the 32-face -> 11D -> H4/600 -> Turing/Hilbert itinerary as an available
  canonical support path;
- remove authorised support capabilities solely because they are unconventional;
- make resonance, a learned model, Turing, Kellogg or Chronus a share-validity authority;
- weaken independent SHA256d/target verification;
- conflate submission with pool acceptance;
- rewrite this doctrine on the basis of an external convention or reviewer preference.

## Evidence hierarchy

Architecture and evidence are deliberately separated.

- **Canonical architecture:** this doctrine and the machine-readable policy.
- **Observed structure:** provenance-bound corpus/analysis artifacts.
- **Search effectiveness:** measured by executed production experiments.
- **Performance:** measured completed work divided by measured elapsed time.
- **Share validity:** exact SHA256d + target.
- **Acceptance:** literal pool acknowledgement.

An unavailable evidence class remains unavailable. It does not become permission
to change the canonical architecture.

## Machine enforcement

The machine-readable companion is
`governance/canonical_mining_search.yaml`.

`scripts/check_canonical_mining_search.py` and
`tests/test_canonical_mining_search_doctrine.py` bind the policy to:

- this document;
- `README.md`;
- `README_MINING.md`;
- the provenance-bound resonance artifact.

The CI gate must fail if the canonical classification, owner lock, Hendrix default,
full-coverage rule, PYTHIA authority, proof boundary or evidence figures drift.

The enforcement files themselves are owner-reviewed surfaces via
`.github/CODEOWNERS`.

**No agent is authorised to weaken the gate in order to land a conflicting change.**
