# exact_linear field-channel audit

Status: finding confirmed. No change to `witness_scalar`, `sign_sigma`,
`fit`, or `predict`.

## Declared field

`exact_linear` is declared to operate in

```text
F4 = Q(√2) + i Q(√2) = Q(ζ₈)
```

`kellogg.exact_tensor.F4` stores four `Fraction` channels on the basis
`{1, √2, i, i√2}`:

| channel | basis element |
|---|---|
| `a` | `1` |
| `b` | `√2` |
| `c` | `i` |
| `d` | `i√2` |

`FIELD_ID` is `"Q(sqrt2)+iQ(sqrt2)"`. The algebra is live when
coefficients are constructed directly. In particular
`(√2)² = 2`, `i² = −1`, `(i√2)² = −2`, and `(1+i)(1−i) = 2`, all as
exact `F4` equalities. `sign_sigma` is the sign of the real embedding
`a + b√2`, and it raises `TypeError` when `c` or `d` is non-zero.

## The finding

The public fit path does not use that field.

`TensorClassifier.fit` sends every caller-supplied matrix through
`_as_2d`, which is `numpy.asarray(..., dtype=float)`. `TensorState`
then rebuilds each entry with `witness_scalar`. For a float,
`witness_scalar` does `Fraction(str(float(value)))` and returns
`F4` of that rational. Only channel `a` is written. Channels `b`, `c`,
and `d` stay `0`.

Consequences, all pinned by tests A–I:

1. A public fit of decimal data, including `0.1` and `0.3`, stores
   weights, bias, and witnessed rows whose `b`, `c`, and `d` channels
   are `Fraction(0)`. `0.1` is witnessed as `Fraction(1, 10)`. It is
   not the binary value `Fraction(0.1) = 3602879701896397/36028797018963968`.
   `witness_scalar` returns an `F4`, not a bare `Fraction`; the exact
   statement is `witness_scalar(0.1) == F4(Fraction(1, 10))` and
   `witness_scalar(0.1).a == Fraction(1, 10)`.
2. The `√2` channel is dormant on that path. `witness_scalar(2**0.5)`
   is a decimal rational in channel `a`. It is not `F4(0, 1)`.
3. The channels are real if the caller bypasses `fit` and supplies `F4`
   coefficients. `TensorModelAPI.from_artifact` accepts a weight
   `F4(0, 1)`. The score of `1` is then exactly `F4(0, 1)`, and
   `sign_sigma` returns `1` even though channel `a` is `0`. That is the
   quadratic comparison `a² ? 2b²`, which the public path never reaches.
   `TensorState.from_values` also preserves an `F4` it is given, because
   `witness_scalar` returns an `F4` unchanged. `fit` itself never takes
   that path: it float-casts first.
4. On the public path every decision score has `b = c = d = 0` and, for
   the integer fixtures used here, denominator `1`. `sign_sigma` then
   reduces to the sign of the integer numerator of channel `a`.
5. `1+i`, that is `F4(1, 0, 1, 0)`, makes `sign_sigma` raise
   `TypeError`. `predict` catches that `TypeError` and raises
   `PlaneViolation`. A direct score equal to `1+i` is produced by
   predicting a `TensorState` that already holds `1+i` against a real
   weight of `1` and a zero bias. That is the bypass, not the public
   float ingress.
6. Public ingress of a complex value does **not** raise
   `PlaneViolation`. `dtype=float` discards the imaginary part (NumPy
   `ComplexWarning`) and `witness_scalar` stores the remaining real
   number in channel `a`. `1+1j` becomes `F4(1)`, not `F4(1, 0, 1, 0)`.

## Boundary

Nothing in this audit deletes a channel, changes the cast, or teaches
`fit` to accept `F4` directly. The dormant channels stay in the type.
Removing them, or routing public ingress around the float cast, would
be a behaviour change and needs a separate decision record.

Tests: `tests/test_kellogg_exact_linear_field_audit.py`, cases A–I.
Each numerical assertion is `==` on `F4` or `Fraction`. None uses
`pytest.approx`.
