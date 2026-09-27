# PYTHIA structured-mining audit

## Scope

This is the evidence reconciliation for the mining pages and the current
`codex/mla1517-v3.4-pythia-product` implementation. It is intentionally
separate from the Enterprise product.

## What is implemented in the canonical PYTHIA path

The integrated package contains a real, bounded structured search path:

1. the M32 topology allocates all 32 lanes without overlap;
2. the chooser selects only declared structured or exhaustive policies;
3. the solver constructs the complete 80-byte header for every candidate;
4. double-SHA256 and the negotiated compact target are the only share predicate;
5. the MMIO/vault/Stratum coordinator submits only a negotiated, proof-safe
   translation and learns only from the pool's actual response.

This is structured search. It is not a claim that a manifold, resonance score,
Lucas/Pisot value, or quantum label changes the SHA256d probability law.

## Corpus evidence found in the workspace

The Notion mining workbench records the following real-data artifacts:

- 50 real block nonces in `phi15_nonces.csv`;
- 200 PoW-verified nonces in `real_nonces_200.csv`;
- an audit over 63 real block nonces from blocks 965490–965919;
- separate controlled tests using 100,000 nonces per group.

The recorded results are not all the same statistic. The current quantum product
record reports a mempool signal mean of `R_phi = 0.6107` and `53% >= phi^-1`.
The executed mining referee reports the 63-block KS and chi-squared tests as
consistent with uniformity and the phi-bias tests as not significant. Those are
not interchangeable with a statement that 62% of an unspecified corpus exceeds
0.5. The 62% claim therefore needs the exact corpus file, score definition,
threshold, denominator, and a rerunnable result before it can be used as a
production routing or hashrate claim.

This is not a dismissal of the observation. It is the required distinction
between: (a) a measured corpus statistic, (b) a reproducible predictor of
SHA256d acceptance, and (c) a pool-accepted hashrate improvement. Only (b) and
(c), each with matched controls, can alter the mining runtime.

## Python TOE, manifold, and intelligence reconciliation

The TOE is not absent. The current PYTHIA head contains Python implementations
including:

- `Intelligence/toe_bridge.py`: `TOEBridge` with tomography, trajectory,
  causal analysis, causal-ladder processing, and algebraic-family signatures;
- `Intelligence/toe_system.py`: provenance ledger and multi-intelligence
  candidate-arbitration code;
- `toe.py`: the algebraic/PredictiveEngine substrate;
- `registry.py` and `Intelligence/registry.py`: TOE subsystem registration.

The accessible Notion pages also establish the M32 manifold, the golden/Pisot/
Lucas family, the five-intelligence measured workflow, and the SHA256d-checked
structured lane. [^https://app.notion.com/p/0d6bfd9f2ba142a6b346411869ae09cb]

The defect is call-graph integration, not absence: the canonical
`mla1517_platform_v3.4/python/mining_runtime.py` currently instantiates
`IntelligentPoolCoordinator` directly and does not invoke the Python TOE bridge
or root registry. The TOE therefore cannot yet be credited with influencing a
live mining decision. The required closure test must show measured mining input
→ TOE decision → changed lane/order/safety state → independent SHA256d proof.

The full search did not find an indexed Notion page or current-PYTHIA file named
`Hendrix`, `topology_2I.h`, or a 2I/600-cell SHA256d schedule-pruning kernel. I
will not treat that as proof that the artifact never existed; it means the exact
page or attachment still needs to be located and loaded rather than inferred
from a title or a search snippet.

## Live acceptance gate

The following are deployment gates, not local simulation tests:

- target host has the intended OpenCL device and runtime;
- MMIO device is present and the host ABI check passes;
- a live Stratum job is received and tracked;
- every candidate uses the current negotiated job template;
- submission is explicitly enabled;
- pool responses are recorded as accepted/rejected with timestamps;
- hashrate is derived from accepted shares or a measured device counter;
- structured and flat control runs use the same job, target, duration, and
  thermal/power conditions.

Until those gates run on the office hardware, PYTHIA can be ready to run but
cannot honestly claim that it is online, earning, or operating at any specific
hashrate.
