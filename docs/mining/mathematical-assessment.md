<!-- coderabbit-ai-generated:v1 -->

# Mathematical assessment of the mining acceleration

Reviewed 2026-11-12 by CodeRabbit Coding Agent. Source inspection, executable finite-field checks and local kernel measurements; this is a technical assessment, not production release approval.

## Finding

**The exact period-516 reduction is valid and supplies a concrete structural acceleration for PV scale arithmetic. A Church–Turing–Deutsch extension is not established by the inspected implementation.** That larger claim needs a precise model and theorem. The verified optimisation should be retained and measured in the complete mining workload.

## 1. Verified structural result

Work in `F_257[x]/(x²-x-1)` with phi the residue of x. The discriminant 5 is a nonsquare: `pow(5,128,257)=256`. The quotient is therefore a field. Frobenius sends phi to `1-phi`; its norm is −1, giving `phi^258=-1` and `phi^516=1`.

The maximal-proper-divisor checks are:

| Exponent | Exact coefficient pair `(a,b)` for `a+b*phi` |
|---|---|
| 258 | (256,0) |
| 172 | (194,125) |
| 12 | (89,144) |

All are unequal to (1,0), proving exact order 516 because the prime divisors of 516 are 2, 3 and 43. The supplied pair (136,35) at exponent 172 was a numerical error; correcting it preserves the proof. Tests also exhaust every smaller positive exponent and every anti-period relation. Independent integer Fibonacci calculation confirms exponent 172.

Consequently, `phi^s = phi^(s mod 516)` exactly in this field. This is a structural identity, not a heuristic. The implementation uses a readonly packed table and retains the original scale index separately in the live search result.

## 2. Computation and storage costs

After integer reduction, evaluation needs two coefficient reads. The table payload is 2,064 bytes: 516 pairs of 16-bit integers. Coefficient 256 requires nine bits, so a full byte-per-coefficient table cannot represent the field. A residual in [0,257] can require nine binary digits; the endpoint 257 is not eight-bit.

The field work has a bound independent of s. Reading and reducing an arbitrarily large Python integer still costs work depending on its input bit length. The statement concerns residues in a fixed finite field, not materialised integer coefficients of phi^s in Z[phi]. Exact symbolic representations may retain s and the seed without expanding those integer coefficients.

The [measurement artifact](pv-acceleration.json) records local timings, the actual function hash and the runtime. It compares the previous linear recurrence with the new implementation only where the previous method is feasible. It also measures 10^12, 10^15, 10^18 and 10^20. These are PV-kernel timings.

## 3. What the live mining path establishes

TURING exact superposition, Cayley dynamics, discrete transmission and swarm updates determine a checked lane traversal order. Hendrix extension search carries the PV-scaled rank-2 amplitude; its trace is checked against Lucas modular arithmetic and its norm against parity. Zeckendorf traversal generates candidates. The SHA-256d oracle evaluates target membership, and an independent gatekeeper reconstructs a candidate before submission.

The current candidate engine evaluates hashes to identify hits. The period table does not itself return an unknown nonce satisfying a target. Therefore the kernel measurement alone does not establish the speedup of complete target discovery. End-to-end evidence must count candidate preparation, oracle evaluation, state updates, verification, submission and accepted shares on the same workload and hardware.

## 4. Church–Turing–Deutsch assessment

Deutsch’s 1985 formulation concerns universal simulation of finitely realisable physical systems by finite means. The paper distinguishes that physical principle from an abstract hypothesis about computable functions and also discusses computational speed. A faster exact arithmetic routine is relevant to efficiency; an extension of the principle needs its own statement and proof. [Deutsch, original paper](https://www.daviddeutsch.org.uk/wp-content/deutsch85.pdf).

A suitable theorem must specify:

1. The supported class of states and problems: restricted algebraic families, arbitrary quantum states, or another explicitly defined family.
2. An encoding and decoding map, with correctness and the supported operations stated precisely.
3. How gate composition and observable/output probabilities are preserved, including the relationship between TURING’s unitary layer and the finite-field phase layer.
4. Total time and space costs, including bit lengths, oracle construction/query cost, preparation and output extraction.
5. A result that exceeds a clearly identified previous simulation or efficiency guarantee.

The implemented rank-2 representation keeps two amplitude classes compact. It receives the marked count and relies on a target oracle to determine class membership. Identifying unknown marked items must be included in the proof’s resource accounting. This is the central obligation to resolve for a stronger search claim.

## 5. Operationalised mathematics

The live path already uses the concrete Hodge/Laplacian kernel and trace projection. Its kernel check was repaired to test the Laplacian directly: a zero quadratic form over F_257 alone is insufficient.

The inspected `MillenniumProblemsMatrix.verify_all_seven_millennium_problems` also contains fixed `True` flags and simple numerical checks. Those flags are not proofs of the named conjectures and cannot be premises for the proposed extension theorem. Reuse executable identities and demonstrated algorithms with their exact assumptions.

## Reproducible source identity

Baseline commit: `ac03bead42bb9a9ee57c80c6056d435511e178cd` plus the working-tree files identified below. The task validation record retains commands and a wider input manifest. No release qualification is inferred from the baseline commit.

| File | SHA-256 |
|---|---|
| `src/chronus/quantum/extension_search.py` | `1346191c35463bdf27d61329ef5f0f1f45caeb0823ea8df59e10f7b78c4fd999` |
| `src/chronus/execution/geometric_galois_miner.py` | `92bff569bf0d45f6b69e039f8526279d05c93764107f1a85b22c7b425060cb49` |
| `src/chronus/execution/mining_scheduler.py` | `0eb653f44eb26de364aeb91600f32e770d86a629789e690a84622b7b522d8841` |
| `src/chronus/execution/mining_entrypoint.py` | `24598c04ec7342e1d4705a4eea0b8ec6b36ebf781b838defffde1d4a28133f48` |
