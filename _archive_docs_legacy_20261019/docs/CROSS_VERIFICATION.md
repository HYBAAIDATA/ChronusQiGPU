# Chronus cross-verification authority (#105)

#105 consumes the immutable #104 `chronus.conformance.*.v1` corpus without changing its schemas, case identifiers, trap taxonomy, or artifacts.

## Authority

`Chronus-1 reference emulator → canonical result/trap` is compared with a registered candidate adapter. The assembler remains the only owner of Chronus-1 encoding. A translated backend need not consume Chronus opcodes, but it must preserve the declared operation semantics and identify non-applicable machine traps honestly.

## Float32 policy

- NaN: both operands must be NaN; payload equality is not required.
- Infinity: exact sign and infinity are required.
- Signed zero: `+0` and `-0` compare equal.
- `vector_add` and `reduce_sum_local`: fused path requires matching binary32 results (except signed zero).
- tiled matmul: `atol=1e-5`, `rtol=1e-5`; physical reordering is allowed only inside that bound.
- Float64 is not supported or inferred from `cl_khr_fp64`. It needs a separate numerical conformance corpus.

## Promotion

`VERIFIED = implemented ∧ applicable case ∧ reference comparison passed ∧ physical evidence present when hardware is claimed`.

The Intel adapter is a translation hook. Without a bound device runner and content-addressed device/driver evidence it reports `PHYSICAL_EVIDENCE_REQUIRED`, never PASS. Host fallback is not accepted as candidate execution. `FOLDED_NATIVE` is not claimed.

## Replay

```bash
python scripts/check_chronus105.py
```

The command first runs #104, regenerates and verifies corpus digest `0b4035e138256cfed08ba5d9e1b0058dc8e7c0dbce2e0ccb50039254de4e1712`, validates negative boundaries, and leaves absent hardware explicit.
