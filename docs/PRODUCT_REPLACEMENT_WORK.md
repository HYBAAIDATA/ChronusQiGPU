# Whole-product replacement work — incomplete

This increment is replacement work on PR #140, not another exact-profile release and not production certification. No new release package is offered. Existing capabilities have not been deleted to create zero audit counts.

## Implemented replacements

- PYTHIA seals the resident execution implementation identity, mode and allowed same-Hendrix fallback. CHRONUS verifies source and live function identity before execution. An unavailable requested implementation fails closed unless the sealed plan names the supported alternative.
- Requested/planned/executed algorithm, implementation module/digest, substrate, plan/geometry identity, actual hash work and fallback are carried into receipts. Independent replay checks the actual candidate digest against SHA-256d and the actual target.
- The public ONE iGPU `evolve` facade now computes exact finite Hamiltonian evolution rather than numerical eigendecomposition. Hermiticity and unitarity are exact checks, and output states must already have exact unit norm; outputs are not renormalised to hide errors.
- Evolution ABI results use `exact_expression_tree_v1`. Numeric inputs are interpreted as their exact binary rational values, not ideal decimal constants. Exact tree inputs are supported. Unknown expression functions and oversized transports fail closed. Evolution receipts are independently recomputed before return and on replay.

## Deliberate compatibility evolution

`OneIGPU.evolve` preserves its name and state/probability accessors. Exact results are symbolic expressions, not complex128 projections. Virtual ABI real/imag outputs are versioned expression trees; consumers needing exact restoration must decode those trees. Float conversion is not performed silently. Unsupported exact materialisation reports UNAVAILABLE. This does not claim all general Hamiltonians are implemented or all public callers are migrated.

## Retained capabilities still requiring replacement

Direct numerical state/operator APIs, S6/cache, QX, UCI, tensor/render/Apple routes and EUCLID operational actuation remain recorded in the machine-readable ledger. Their legitimate roles have not been deleted. None is claimed certified merely because the resident route tests pass.

## Evidence and access boundary

Focused tests use real arithmetic, actual Bitcoin header hashing and injected adversarial faults; injected faults are tests, not execution evidence. Standalone source regressions and fresh installed wheel tests are recorded separately. Canonical integration tests use the retained dependency-scoped source snapshot, not a complete installed canonical repository. Individual GitHub MCP file reads succeed; authenticated full checkout is unavailable and returned raw downloads failed. Full caller enumeration, canonical clean installation, full CI and deployed THESEUS/OVID/pool qualification are not asserted.

The replacement ledger uses null for unmeasured whole-product closure counters. Null is not zero. PR remains draft.
