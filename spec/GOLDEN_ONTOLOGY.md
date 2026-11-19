# Golden Ontology — normative candidate v2.0

Status: frozen candidate for independent review, NOT accepted or approved for publication.
This standalone standard-library reference does not replace the maintained Chronus,
OVID, AL HARAS, THESEUS or TURING authority paths. The earlier checkpoint profile
(scripts/fold_verify.py) has an explicit different width/nonempty contract.

## GO-01 — exact golden fold

For width b in [1,4096], modulus m=2^b, canonical even-length integer words
(including the empty sequence), and nonnegative integer steps s, let Q=[[1,1],[1,0]].
Reject booleans, negative and out-of-range words, odd length and invalid width;
do not reduce input words. An explicit period must be the exact integer
P=3*2^(b-1). Reduce s modulo P first. Obtain F(n),F(n+1) by fast doubling,
reducing on every iteration modulo m. Multiply successive pairs by
[[F(n+1),F(n)],[F(n),F(n+1)-F(n)]] modulo m. Inverse uses (-s) mod P.
Cassini: determinant is (-1)^n, hence a unit. Bit complexity depends on width
and multiplication; O(log n) counts modular integer operations, not bit operations.
This bijection neither compresses nor proves authenticity of a particular payload.
A trusted original/digest is required for payload integrity; a bare image is unbound.

Mathematical period and minimality argument: Q^3=I+2Q, and Q^6=I+4A
where A=[[3,2],[2,1]]. For k>=2, if Q^(3*2^(k-1))=I+2^k B then
squaring gives I+2^(k+1)(B+2^(k-1) B^2). Since B has odd diagonal entries
at k=2 and B mod 2 is unchanged by each subsequent lift, the order doubles
at each lift. At k=1 the order is 3 (Q and Q^2 are not identity mod 2);
Q^3 is not identity mod 4. Thus exact order as stated. The formal file targets
Cassini and the general period congruence; minimality is a separate mathematical
review obligation, not claimed to be kernel-proven.

## GO-02 — resonance

Represent phi^(-k)=(p+q sqrt(5))/2; p=(-1)^k L(k), q=(-1)^(k+1) F(k).
Verify p^2-5q^2=4(-1)^k. For distinct nonnegative integers i,j, the
coefficient F(|i-j|) is nonzero, proving pairwise irrational frequency ratios.
This does not establish rational independence among three or more frequencies,
absence of near-resonance, or physical advantage. Numerical projection is
separate, may underflow and is not an exact algebraic proof.

## GO-03 — unimodular PV registry

Family / monic polynomial coefficients descending / companion rows / determinant:

- golden: (1,-1,-1); (1,1),(1,0); -1
- silver: (1,-2,-1); (2,1),(1,0); -1
- plastic: (1,0,-1,-1); (0,1,0),(0,0,1),(1,1,0); +1
- supergolden: (1,-1,0,-1); (1,0,1),(1,0,0),(0,1,0); +1
- tribonacci: (1,-1,-1,-1); (1,1,1),(1,0,0),(0,1,0); +1

All five immutable. Exact alpha lower bounds and strict upper bounds on other
conjugate magnitudes respectively: (8/5,5/8), (12/5,5/12), (5/4,9/10),
(13/9,5/6), (9/5,3/4). Quadratics have conjugate magnitude 1/alpha;
cubics have negative discriminant and a conjugate complex pair of modulus
sqrt(1/alpha). Irreducibility follows by rational root test; the sign change
and discriminant certify existence of the designated root. Bound^radius is
exact rational upper bound, not an exact evaluation of the algebraic conjugate
magnitude and not a statistical noise-filter guarantee. Other family IDs rejected.
Generalized period is the least positive matrix order modulo m; non-golden
or non-power-of-two computation is bounded enumeration and explicitly fails
when unavailable. No universal closed form or constant-time order claim.

## GO-04 — numerical filter and ordinal encoding

On an ordered finite real sequence, kernel w_j proportional to alpha^(-|j|)
for j=-r,...,r with endpoint clamping. Evaluate using numerical root projection.
Report symmetry and normalization separately from error and finite-edge behavior.
Static observations cannot be passed as a temporal claim without ordering.
Dense ranks assign tied values the same rank; strictly increasing warp preserves
all order and tie classes; reject inversions, splits, merges or nonfinite values.
Zeckendorf decomposition uses distinct nonadjacent Fibonacci terms F_2 onward.
Cross-dataset ordinal comparisons require a shared basis and defined semantics.

## GO-05 — independent QC protocol

Use a clean checkout at the reviewed commit. Reconstruct vectors independently
from this text, before looking at expected outputs or producer implementation.
Byte-compare normative JSON outcomes, including negative cases; replay the
Python suite and Lean checker; independently inspect minimal-order argument,
purity, error paths and authority boundaries. Record reviewer identity, commit,
spec/vector digests, commands, aggregate and individual outputs, mismatch count,
and signed/authorized disposition. An executor run or CodeRabbit review is
not independent mathematical acceptance. Do not publish or ratify merely
because tests pass. No release gate can be satisfied by an empty register.

## GO-06 — benchmark boundaries

Controlled generated signals are explicitly test fixtures, not real telemetry.
Measure raw baseline, matched-window moving average and Savitzky–Golay, causal
EMA separately and all five PV families; same input, edge policy and metrics.
Report unrounded RMSE, impulse asymmetry and actual execution environment.
No superiority is inferred from ordinal invariance or from a single fixture.
Real-telemetry and maintained TOE consumer acceptance remain separate obligations.

## Integration boundary

The standalone package is included in the internal Chronus wheel for the
research adapter, but its core is standard-library-only and can be replayed
from the checkout without installing Chronus. Numerical functions are exposed
through golden_ontology.numeric_reference and chronus.research.golden_nature_reference,
not the exact chronus.math namespace. The draft numerical imports have moved;
exact descriptors and integer operations remain in chronus.math.golden_nature.
The namespace move is an actual execution boundary, not an exemption from an
existing gate. No production dispatch or customer API uses it.
