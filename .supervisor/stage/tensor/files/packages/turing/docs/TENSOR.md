# TURING exact tensor layer (`turing.tensor`)

`turing.tensor` evaluates tensors, tensor trains and matrix product states
exactly. It is the exact counterpart of the Chronus tensor engine and follows
the TURING standard: exact values, zero rounding, zero truncation, zero lossy
compression, deterministic results, and sizes that are computed rather than
assumed.

The Chronus tensor engine (`chronus.tensor`: `EnhancedTensorRepresentation`,
`network`, `gate`, `dmrg`, `evolution`, `peps`) works in numpy complex128,
factorises bonds by singular value decomposition, truncates them and records
each cut with an error bound. That is certified approximation, which is the
right tool for floating-point inputs, and it is unchanged. Its exact piece,
`chronus.tensor.exact_mps.contract`, works in Z[zeta_5] and expands the full
state vector (at most 16 sites and 65,536 amplitudes); it is also unchanged.
`turing.tensor` keeps states factorised and exact, so amplitudes and marginal
probabilities of registers with thousands of sites can be read without ever
building the state vector, provided the entanglement is low (see Limits).

## What the layer guarantees

- **Exact entries.** Every entry is an element of an exact field: the
  rationals `QQ` (`fractions.Fraction`) or a cyclotomic field `cyclotomic(m)`
  = Q(zeta_m), backed by `turing.algebra.CyclotomicField` (rational
  coordinates in the power basis). Every routine does its arithmetic through a
  small field protocol (`zero`, `one`, `from_int`, `coerce`, `add`, `sub`,
  `neg`, `mul`, `div`, `is_zero`, `eq`, `conj`), so there is no floating point
  anywhere in `turing.tensor`. Floats are refused with `TypeError`.
- **Exact factorisation.** Bonds are factorised with the CR factorisation
  A = C R, where C holds the pivot columns of A and R the nonzero rows of the
  reduced row echelon form of A. It needs only field operations, reveals the
  exact rank and is unique. The singular value decomposition needs square
  roots of eigenvalues, which leave the field, so it cannot be exact.
- **Bond dimension equals exact rank.** `TensorTrain.from_dense` produces bond
  k equal to the exact rank of the k-th unfolding of the tensor, the smallest
  rank any tensor train can have. In `ExactMPS` every gate is invertible and
  every two-site update keeps both factors at full rank, so every bond always
  equals the exact Schmidt rank of the state across that cut. The tests
  compute those ranks independently from dense states and compare.
- **Lossless compression.** `TensorTrain.compress` removes exact linear
  dependence and nothing else: after it, `to_dense()` returns the original
  tensor exactly and every bond is minimal.
- **Refusal instead of truncation.** A dense tensor above `MAX_DENSE_ENTRIES`
  (2^20 = 1,048,576 entries) is refused before any entry is allocated. A gate
  that would make any bond of an `ExactMPS` larger than `max_bond` raises
  `ValueError` naming the bond and its exact rank; the register keeps its
  previous state and `evaluate_circuit` never returns a truncated state.
- **Exact normalisation.** Gates are exact matrices with a declared scale: a
  matrix M with M M^dagger = scale * I acts as M / sqrt(scale), and the check
  is done exactly before the gate is applied. The Hadamard gate is
  [[1, 1], [1, -1]] with scale 2, a factor 2^(-1/2) per H kept symbolically.
  Amplitudes are `ExactAmplitude` values value / sqrt(scale), and every
  probability |value|^2 / scale is an exact element of the field.
- **Determinism and computed sizes.** There is no randomness. The reduced row
  echelon form is unique, so the same circuit always gives the same cores. The
  register size and every bond dimension are read from the stored cores.

## Public API

| Name | Purpose |
| --- | --- |
| `Field`, `QQ`, `cyclotomic(m)`, `RationalField`, `CyclotomicNumberField` | the field protocol and the two provided fields; `cyclotomic(m).root_of_unity(order, power)` and `positive_sqrt(k)` give exact roots where the field contains them |
| `ExactTensor`, `MAX_DENSE_ENTRIES` | dense tensor: `zeros`, `from_nested`, `from_function`, `identity`, `reshape`, `transpose`, `contract` (tensordot semantics), `matmul`, `outer`, `conj`, `norm_squared`, exact equality |
| `rref`, `rank`, `cr_factorization`, `CRFactorization`, `matmul` | exact linear algebra over any field |
| `TensorTrain` | `from_dense`, `to_dense`, `entry`, `inner`, `norm_squared`, `ranks`, `compress`, exact `+`, `-`, `scale` |
| `ExactMPS`, `ExactAmplitude`, `DEFAULT_MAX_BOND`, `GATE_NAMES` | exact qubit and qudit registers; gates `x`, `y`, `z`, `h`, `s`, `t`, `phase`, `cz`, `cnot`, `swap`, `apply_one`, `apply_two`, `apply`; `amplitude`, `probability`, `marginal_probabilities`, `bond_dimensions`, `norm_squared`, `is_normalized`, `as_tensor_train`, `to_dense` |
| `evaluate_circuit(n_qubits, gates, max_bond)` | runs a list of `(name, qubits, params)` from `|0...0>` and returns the `ExactMPS` |

Conventions: an `int` basis index follows TURING (bit k is qubit k, bit 0 the
least significant; mixed radix for qudits); a digit string or a sequence lists
site 0 first. Two-site matrices use the basis index s_first * d_second +
s_second. Without an explicit field, `evaluate_circuit` uses Q(zeta_m) with m
the least common multiple of 8 and every root-of-unity order the gates need.

## Cost of each operation

Costs are counted in field operations. n is the number of sites, d the local
dimension, chi the largest bond dimension, N the number of entries of a dense
tensor and r a rank. Measured locally in Q(zeta_8) with small coefficients, an
addition takes about 6 microseconds, a multiplication about 14 and a division
about 150 (pure Python); the time per operation grows with the size of the
coefficients.

| Operation | Cost |
| --- | --- |
| `ExactTensor.reshape` | O(1) (entries shared) |
| `transpose`, `conj`, `norm_squared` | O(N) |
| `contract` of an (a x k) by (k x b) grouping | O(a k b) |
| `rref`, `rank`, `cr_factorization` of an m x k matrix of rank r | O(m k r) plus r divisions |
| `TensorTrain.from_dense`, `to_dense` | O(N r) |
| `TensorTrain.entry` | O(n r^2) |
| `TensorTrain.inner`, `norm_squared`, `compress` | O(n d r^3) |
| `ExactMPS` one-site gate | O(d^2 chi^2) |
| `ExactMPS` two-site gate on neighbours | O(d^2 chi^3 + d^4 chi^2) to contract and apply, O((d chi)^3) for the CR factorisation |
| `ExactMPS` two-site gate at distance L | the same, plus 2 (L - 1) exact SWAP updates |
| `amplitude`, `probability` | O(n chi^2), no state vector |
| `marginal_probabilities`, `norm_squared`, `is_normalized` | O(n d chi^3) by exact environment contraction |
| `bond_dimensions` | O(n) |

Memory is O(n d chi^2) field elements for a register and N for a dense tensor.

## The 2,500-qubit instances

Each test builds the circuit for 2,500 qubits and then reads the register size
from the returned register. All values below are exact and asserted by
`tests/test_turing_tensor_scale.py`.

| Instance | Gates | Computed bond dimensions | Exact results |
| --- | --- | --- | --- |
| GHZ: H, then a CNOT chain | 2,500 | all 2,499 bonds are 2 | P(0...0) = P(1...1) = 1/2; the two mixed strings checked have probability 0; amplitude(0...0) = 1/sqrt(2); the marginals of qubits 0, 1,250 and 2,499 are 1/2 |
| GHZ, then T on every qubit | 5,000 | all 2 | amplitude(1...1) = zeta_8^(2500 mod 8) / sqrt(2) = zeta_8^4 / sqrt(2) = -1/sqrt(2); both probabilities stay 1/2 |
| Product state: H, T, H on every qubit | 7,500 | all 1 | for a fixed string with 715 ones, amplitude = (1 + zeta_8)^1785 (1 - zeta_8)^715 / 2^2500; qubits 0 and 2,499 are 0 with probability (2 + sqrt 2)/4, an exact irrational value |
| Depth-2 brickwork: H, CZ on even pairs, T, H, CZ on odd pairs, T | 12,499 | all 2,499 bonds are 2 | amplitude(0...0) = (1 + 2 zeta_8 - zeta_8^2)^1250 / 2^2500 and P(0...0) = (3/8)^1250; the marginal of qubit 1,250 is 1/2 |

The brickwork is cross-checked twice. For 2 to 10 qubits every amplitude
equals a dense evaluation in Q(zeta_8). At 2,500 qubits two amplitudes equal an
independent closed form: the circuit is diagonal, H layer, diagonal, H layer,
so the path sum factorises over the even pairs into
f(u, v) = sum_ab zeta^(a+b) (-1)^(ab + ua + vb), with |f(0,0)|^2 = |f(1,1)|^2 = 6
and |f(0,1)|^2 = |f(1,0)|^2 = 2.

Measured local runtimes (2026-11-11, CPython 3.12.16, x86_64, one process on a
shared sandbox, minimum and maximum of three runs, wall clock):

| Step | Time (s) |
| --- | --- |
| GHZ: build (H and 2,499 CNOT) | 0.37 to 0.46 |
| GHZ: P(0...0) and P(1...1) | 0.11 to 0.16 |
| GHZ: one single-qubit marginal | 0.32 to 0.37 |
| GHZ + T: the 2,500 T gates | 0.10 |
| GHZ + T: amplitude(1...1) | 0.04 to 0.08 |
| H T H product: build (7,500 gates) | 0.47 to 0.82 |
| H T H product: one amplitude | 0.04 to 0.09 |
| Brickwork: build (12,499 gates) | 2.56 to 2.59 |
| Brickwork: one amplitude | 0.20 to 0.25 |
| Brickwork: one single-qubit marginal | 1.42 to 1.50 |

These are measurements on one machine, not guarantees.

## Limits

- The bond dimension is the exact Schmidt rank, and it grows with
  entanglement up to 2^(n/2) at the middle cut of an n-qubit register (2^1250
  for 2,500 qubits). A two-site update costs about (d chi)^3 field operations,
  so highly entangled circuits are refused at `max_bond`
  (`DEFAULT_MAX_BOND` = 64, the largest Schmidt rank of 12 qubits) rather
  than approximated. The 2,500-qubit instances above are low-entanglement
  circuits; their exact Schmidt ranks are 1 or 2, which is the only reason
  they are small. The test circuits reach the full rank 32 on 10 qubits.
- Gates on distant sites are routed with exact SWAP gates. `max_bond` applies
  to every intermediate bond, so a long-range gate can be refused while it is
  being routed.
- Dense tensors are limited to `MAX_DENSE_ENTRIES` entries.
- Coefficient sizes can grow with circuit depth, and the time per field
  operation grows with them.
- This is exact classical evaluation of the mathematics. It is not a quantum
  computer or device simulator, nothing is executed on quantum hardware, and
  no performance advantage over any other method is claimed.

## Floating-point Kronecker products

The floating-point Kronecker products `tensor_states` and `tensor_operators` moved unchanged to `turing/kronecker.py` and stay importable from `turing`; they are outside the exact layer.

## Use from Chronus

`chronus.igpu.tensor.exact` returns this module when the hyba-turing
distribution is installed, and raises `ImportError` otherwise; importing
`chronus.igpu.tensor` does not import TURING.

## Tests

| File | What it shows |
| --- | --- |
| `test_turing_tensor_field.py` | field axioms for Q and Q(zeta_8) on fixed samples; coercion refuses floats; exact roots of unity and positive square roots with their signs |
| `test_turing_tensor_dense.py` | reshape, transpose and contraction against explicit index loops; outer product, conjugation and norm; the dense bound |
| `test_turing_tensor_linalg.py` | C R = A exactly for rational and cyclotomic matrices, including rank-deficient, zero and empty ones; rank equals an independent elimination and the largest nonzero minor; the reduced form is invariant under invertible row operations; a GF(7) field shows that every routine uses only the field protocol |
| `test_turing_tensor_train.py` | from_dense then to_dense is exact for 18 shapes; bond ranks equal unfolding ranks; entries, inner products and norms; compress is lossless and minimal |
| `test_turing_tensor_mps.py` | every amplitude of a fixed family of circuits on 1 to 10 qubits (T, phases, sqrt(iSWAP), routed gates) equals an independent dense evaluation in Z[zeta_8]; bond dimensions equal exact Schmidt ranks; marginals; agreement with `turing.algorithms.clifford` on Clifford circuits; qudits; refusals |
| `test_turing_tensor_scale.py` | the 2,500-qubit instances above |
| `test_turing_tensor_policy.py` | no float literals, `float()`, non-integer `math` functions, `random`, `numpy`, `chronus` or floating-point modules in `turing/tensor`, located through the imported package; the Kronecker products stay outside the exact package; no unsupported claim wording in its sources and tests |
| `tests/test_turing_repository_policy.py` (repository root) | the document checks, which read repository paths: no claim wording in this document and in `docs/algorithms.md`, and the statements required here |

From `packages/turing`: `python -m pytest -q tests/test_turing_tensor_*.py`; from the repository
root: `python -m pytest -q tests/test_turing_repository_policy.py`.
