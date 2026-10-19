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

## Mathematical capability verification

The Python mathematical layer is real and now execution-verified (states are
measured, not claimed; every verifier reports `theorem_proven=False`):

- `lucas/` (core, ladder, pool, bound, t_phi): exact big-int Lucas stack;
  ladder `10,12,15,18,20,31,50,76` with `L_76 = 7639424778862807`, Cassini
  `L_n² - 5F_n² = 4(-1)ⁿ` and `L_n = F_{n-1} + F_{n+1}` identities verified
  through `n = 80`; modular M15 tensor satisfies `M15·M15⁻¹ ≡ I (mod 256)`;
  the seven bound kernels return `is_lucas_bounded` route verdicts.
- `kellogg/scales.py`: exact `Z[φ]` layer — `phi_power(n) = F_{n-1} + F_n φ`,
  `pisot_drift(n) = φⁿ - L_n` with exact norm `(-1)ⁿ`, Zeckendorf greedy.
- `millennium/` (quantum_algorithms, folded_grover, grover_exact_scale):
  QFT/QPE/Grover/VQE simulators (labeled simulation, not device execution);
  `FoldedGrover` matches a dense-matrix reference bit-for-bit and preserves
  the Cassini witness to `< 1e-12`.
- `toe/`: `strict_quantum` certifies work windows in exact `Q(i)` —
  `consensus_authority=False` by construction; `solovay_kitaev` synthesizes
  gates over the Clifford+T alphabet with exact `F4` matrix arithmetic
  (X found as `H·S†·S†·H`, error < 1e-12).
- `mtheory/`: exact T-duality spectrum invariance, `SL(2,ℤ)` Möbius group
  laws, `KKTower` mass spectrum in `Fraction`; `thermo/model.py`: sourced
  Landauer/adiabatic energy estimates with falsification hooks.
- `mining/` (nonce_scheduler, difficulty, search): deterministic schedule,
  bounded difficulty controller, real `sha256d` winner verification.

Found and fixed during verification: `binet_residual(n)` computed
`|φⁿ - L_n|` by raw float64 subtraction, which returns garbage for `n > ~74`
(`φ⁷⁶ > 2⁵³`; returned ≈19 instead of `|ψ|⁷⁶ ≈ 1.3e-16`). Both copies
(`millennium/` and the `turing_universal_quantum_computer` vendored copy) now
compute the Binet-identical `|ψ|ⁿ` directly, verified against exact `Z[φ]`
drift evaluated in 60-digit arithmetic. The honest-state gate itself is
unchanged: these capabilities are verified mathematics, not evidence that any
of them alters the SHA256d acceptance law — the call-graph integration defect
below remains the open item.

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

## Python TOE and Kellogg integration

TOE is on the canonical runtime call graph; it is not proof authority. The
production `IntelligentPoolCoordinator.submit_record()` takes the current
Stratum job and observed 64-byte vault state through
`chronus.mla1517.mining.toe_adapter.TOEMiningAdapter`, builds a validated
`TOEMiningDecisionFrame`, and passes only its advisory frame/signal to the
declared mining chooser and safety controls. `toe.bridge.TOEBridge` consumes
Kellogg-owned `kellogg.quantum_tensor` and `kellogg.exact_tensor` operations;
Kellogg owns the tensor representation, while TOE owns the analysis adapter.
The frame digest is attached to the immutable SearchPlan. Missing or incomplete
TOE evidence does not get replaced by synthetic evidence, and cannot validate a
nonce, target, share, or pool outcome.

`manifests/canonical_mining_voyage.json` records the canonical stage owners.
`test_canonical_mining_manifest_resolves_all_production_owners` imports every
declared module and resolves every declared symbol. The loopback voyage tests
exercise the real Stratum client, coordinator, lease ledger, execution router,
host proof check, submission lifecycle, literal outcomes, and restart behavior;
the TOE adapter test separately verifies its real Kellogg-backed observation
path. These software tests do not establish a TOE-driven live-device result.

The full search did not find an indexed Notion page or current-PYTHIA file named
`Hendrix`, `topology_2I.h`, or a 2I/600-cell SHA256d schedule-pruning kernel. I
will not treat that as proof that the artifact never existed; it means the exact
page or attachment still needs to be located and loaded rather than inferred
from a title or a search snippet.

## Voyage evidence classification

The deterministic loopback pool and CPU route establish at most
`SOFTWARE_EXECUTION_VERIFIED`. Their configured accept/reject responses are
fixture outcomes, not `POOL_VERIFIED`; no loopback result establishes
`HARDWARE_EXECUTION_VERIFIED`. Those promotions require separately recorded
real-device execution and real-pool acknowledgement evidence. The executable
stage map records these limits so software evidence cannot be promoted by
wording alone.

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
