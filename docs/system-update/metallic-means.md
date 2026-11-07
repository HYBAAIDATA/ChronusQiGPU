# The metallic means family: from phi to the full spectrum

## The discovery

The golden ratio is not an isolated constant. It is the first member (m = 1) of the **metallic means**, the positive roots of

    x^2 = m*x + 1        sigma_m = (m + sqrt(m^2 + 4)) / 2

| m | Name | sigma_m | Conjugate |psi| | Sequence (trace) |
|---|---|---|---|---|
| 1 | Golden | 1.618... | 0.618 | Lucas |
| 2 | Silver | 2.414... | 0.414 | Companion Pell |
| 3 | Bronze | 3.303... | 0.303 | bronze trace |

Every member shares the properties the QiGPU substrate is built on:

- **Exact integer ring.** Z[sigma_m] elements are integer pairs (a, b) with the fold rule sigma_m^2 = m*sigma_m + 1 — the same carry-free structure as base-phi, parameterized by m.
- **PV contraction.** The conjugate satisfies |psi_m| = 1/sigma_m < 1, so powers sigma_m^n converge onto exact integers (the trace sequence T_n = m*T_{n-1} + T_{n-2}) with zero rounding drift at any scale.
- **Norm unit.** N(sigma_m) = -1 for all m, so N(sigma_m^n) = (-1)^n — the generalization of the Cassini parity anchor.

## What is implemented

`src/chronus/backends/metallic.py` provides exact `MetallicElement` arithmetic (multiply, trace, norm), `metallic_power(m, n)` by fast doubling, and `metallic_sequence(m, n)`. The m = 1 case reproduces the golden engine bit-for-bit (`phi_power`, L_90). Known-answer tests cover silver (companion Pell 2, 2, 6, 14, 34), bronze (2, 3, 11, 36, 119), the trace recurrence for arbitrary m, and the norm identity N(sigma_m^n) = (-1)^n.

The `METALLIC_SCALE` workload exposes this over the authenticated API:

```json
{"m": 2, "index": 3}
```

returns sigma_2^3 = 2 + 5*sigma_2 with trace 14 and norm -1.

## Honest boundaries

Golden-angle (phyllotactic) sampling genuinely maximizes uniform dispersion — that is why it distributes Theseus storage lanes. The stronger claims circulating in the design narrative ("zero collision", "bypassing the curse of dimensionality") are not theorems; dispersion minimizes collision probability but cannot defeat information-theoretic limits, and high-dimensional search cost still scales with dimension. The substrate's provable advantages are exactness (no floating-point truncation anywhere in the path), carry-free constant-delay folding, and O(log n)-bit scale indexing.

## Next elevations prepared by this layer

1. **Parameterized fold hardware** — the RTL fold sweep generalizes from `011 -> 100` to the m-fold rule; a parameterized `zeckendorf_fold_sweep #(parameter M)` is the next silicon step.
2. **Metallic norm proofs** — the F_257[phi] Sigma protocol extends to F_p[sigma_m] whenever m^2 + 4 is a quadratic non-residue mod p, giving per-family zero-knowledge receipts.
3. **Multi-scale phyllotaxis** — **implemented**: `PhyllotaxisMesh.map_key_multiscale` nests golden (local lane), silver (8-way partition) and bronze (4-way macro route) lenses over one key, each derived from its own exactly computed metallic fixed-point constant (`metallic_conjugate_64(m)`, integer square roots only — m = 1 reproduces the Knuth golden constant bit-for-bit).

## Missed opportunities now on record

- The engine was φ-specific for six milestones while the mathematics was always general; `metallic.py` closes that gap.
- The RTL fold is a single even-phase sweep; a pipelined even/odd convergent folder is the missing silicon stage.
- Theseus storage remains process-local; durable custody is the largest gap between vision and deployment.
- Physical GPU validation still requires client-provisioned hardware.
