# Lucas/Pisot scaling research closure

## Provenance

The indices `10, 12, 15, 18, 20` are preserved as an **autobiographical discovery seed** derived from the founder's date-of-birth pattern. This explains why these candidates were explored. It is not performance evidence.

Their exact Lucas values are `123, 322, 1364, 5778, 15127`.

## Results

The deterministic suite verifies across `n=0..500`:

- exact agreement between the fast-doubling and `Z[phi]` implementations;
- `L_n^2 - 5F_n^2 = 4(-1)^n`;
- `L_n` is the nearest integer to `phi^n` for `n >= 2`;
- `|phi^n-L_n|=phi^-n` and relative residual `phi^-2n`;
- the discovery indices and adjacent controls obey the same normalized law.

Therefore the discovery set is mathematically coherent but has no special Pisot effect after controlling for the index. Operational preference still requires measurement against conventional candidates.

## Float64 falsification

Binary64 cannot certify the high-index residual:

- at `n=39`, the correctly rounded binary64 representation of `phi^n` already equals `L_n`, erasing the true nonzero residual;
- using binary64 `phi ** n`, the first integral-looking result occurs at `n=70`, but it is already wrong by `1`;
- at `n=76`, it is wrong by `19`.

An integral-looking float is not an exact Pisot certificate. Exact integer or high-precision quadratic-field arithmetic is required.

## 11-D Float32 transport boundary

The current `toe.poincare_golden_11d.to_gpu_input()` contract converts its input to Float32. A focused representability test shows that the Pisot residual first disappears at `n=18`. Within the discovery set:

- `n=10, 12, 15`: the residual remains distinguishable in Float32;
- `n=18, 20`: `float32(phi^n) == float32(L_n)`, so the residual is erased.

This does not corrupt Lucas integers, but it prevents the Float32 GPU payload from serving as evidence of the high-index Pisot drift. The authoritative Float64 11-D state must either remain on an exact/Float64 path or undergo an explicit, evidenced lossy conversion. Silent downcasting must not be treated as exact execution.

## Claim boundary

This work proves identities and numerical boundaries. It does **not** prove mining advantage, scheduling advantage, hardware speedup, ergodicity, or production qualification.

## Command

```bash
python scripts/check_lucas_pisot_scaling_research.py
```
