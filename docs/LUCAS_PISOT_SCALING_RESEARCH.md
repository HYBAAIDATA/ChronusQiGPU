# Lucas/Pisot scaling research closure

## Provenance and claim boundary

The indices `10, 12, 15, 18, 20` are an **autobiographical discovery seed**. They explain candidate origin, not performance. Their exact Lucas values are `123, 322, 1364, 5778, 15127`.

The suite verifies the exact integer identities, high-precision Pisot law and adjacent controls. It does **not** establish mining advantage, scheduling advantage, hardware speedup, ergodicity or production qualification.

## Semantic roles

| Role | Use | Precision contract |
|---|---|---|
| Decorative | labels, geometry, visualization | Float32 allowed; no invariant inferred |
| Parametric | seeds, schedules, subset selection | Float32 allowed with disclosed approximation |
| Structural | gates, folds, transitions, invariants | required distinctions must be preserved |
| Certifying | witnesses and acceptance evidence | authoritative exact/high-precision arithmetic |

Dimensionality alone does not require Float64. Structural dependence on a sub-ULP distinction does.

## Numerical boundaries

Binary64 erases the true residual at `n=39`. Ordinary binary64 `phi ** n` first looks integral at `n=70`, where it is already wrong by `1`; at `n=76` it is wrong by `19`.

The real host `to_gpu_input()` codec is exercised with 11-D vectors. Float32 preserves the tested distinction at `n=10, 12, 15` and erases it at `n=18, 20`. This is a **host codec result**, not OpenCL execution or fp64 device qualification.

## Enforced transport contract

`to_gpu_input()` now requires both an explicit `role` and `allow_lossy=True`. Only `decorative` and `parametric` roles are accepted. Structural and certifying inputs fail closed. `to_authoritative_input()` preserves Float64 on the host without claiming GPU support.

A device fp64 path may be called certified only after a real numerical device test; extension discovery alone is insufficient.

## Artifact verification

`content_sha256` hashes canonical UTF-8 JSON with sorted keys and compact separators after removing only `content_sha256`. The check command regenerates the artifact and verifies that digest.

```bash
python scripts/check_lucas_pisot_scaling_research.py
```
