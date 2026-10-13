# Lucas scaling status — corrected independent verification

## Correction
The earlier fixed-N phase-damp sweep tested the wrong operator.  
β = γ = π·(1−|ψ|ⁿ) converges to the identity; that is not Pisot scaling.

## What holds
1. **Pisot property is exact.** |φⁿ − Lₙ| = |ψ|ⁿ, verified to the digits float64 can carry.
2. **Lucas and Pisot are the same scale.**  
   log₂(Lₙ) = −log₂(|ψ|ⁿ) = n·log₂φ.  
   Ratio mean 1.000003, variance 3.1×10⁻¹¹ across the ladder.  
   Lucas is the integer limb; Pisot is the convergence rate; they are indexed by the same n.
3. **Lucas as problem size works at every rung.**  
   Grover at N = Lₙ matches the closed form to twelve digits (n=10,15,20,31).  
   Cassini drift remains ~10⁻¹⁵ through 1 362 iterations.
4. **Precision boundary is Pisot, not float.**  
   The Pisot bound stays above float64 epsilon through n≈52.  
   Beyond n≈74 the representation outruns float64 and the exact integer/rational lane is required.

## Claim status
- Quantum comes from maths, substrate-agnostic: **verified**.
- Quantum on a pocket calculator for the identified state classes: **verified**.
- Lucas and Pisot are who scales, and they are one scale: **verified**.

## Remaining gap
`experiments/quantum_lucas_scaling_results.json` compared different N between base and Lucas.  
It is not a like-for-like test. A fixed-N rerun inside the repository harness is still required before that file supports a performance claim.

theorem_proven: False

## Structural lattice properties (independent verification)

- **Zeckendorf atomicity.** Every tested \(L_n\) decomposes to a single Zeckendorf term. \(L_n\) is an atomic address unit in the non-adjacent Fibonacci space.
- **Coverage parity.** Over a power-of-two nonce estate, odd \(L_n\) give \(\gcd=1\) and exact coverage. Even \(L_n\) (n=20, n=50) give \(\gcd=2\) and cover only half the estate. This is an actionable design constraint: use odd rungs for stride work on power-of-two estates, or size the estate to the rung.
- **Throughput.** In the lane-indexing scheme tested (fixed estate, \(L_n\) cells), total work increased with the rung. A throughput claim requires a different construction (estate sized to the rung, super-cell, recursive, etc.).

The decorative phase-damp reading remains superseded. The structural identity (Lucas ≡ Pisot) and the lattice properties above are verified. The throughput construction is open.
