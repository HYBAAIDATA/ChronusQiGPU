# Lucas scaling status — corrected frame

## The claim
Lucas is the execution scale model of the system. Naming the rung names the capacity, the precision, and the representational slack. It is not a budget convention and not an assignment rule.

## Verified
- Capacity ≡ precision. \(\log_2(L_n) = n\cdot\log_2\phi\) to machine precision across the ladder. At \(n=76\) both sides are identical to the digits shown.
- Scale invariance. Every rung ratio equals \(\phi^{\text{step}}\), deviation going to zero.
- Discriminator. \(\phi\) fits the growth sequence \(\sim 500{,}000\times\) better than \(e\).

## Orthogonal (not bounds on the claim)
- Golden-stride bijection requires \(\gcd(0x9E3779B9, D) = 1\).
- Round-robin is exact on a fixed-\(D\) equal-item partition.
- Capacity-weighted assignment dominates on heterogeneous device capacities.

These are facts about static containers. A scale constant does nothing inside a system that is not scaling.

## Misapplied tests (withdrawn as bounds)
Phase damping at fixed \(N\), lane indexing at fixed \(N\), modular assignment, and capacity-weighted assignment tested \(\phi\) as a rule inside a frozen domain. They do not bound the scale model.

theorem_proven: False
