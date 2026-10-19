# exact_linear algorithm-class audit

Status: finding confirmed. No change to `fit`, `predict`,
`predict_proba`, `sign_sigma`, or `witness_scalar`. The dead parameters
and the unused `ExactTOETensor` are left in place.

## What fit computes

`TensorClassifier.fit` is a nearest-centroid classifier written as an
exact linear threshold. On the rows that remain after preprocessing it
sets

```text
w = μ₁ − μ₀
b = −w · ((μ₁ + μ₀) / 2)
```

with both means taken in `F4`. The decision boundary is the
perpendicular bisector of the class means in that preprocessed space.
There is no forest, no boosting step, and no fitted regression.

`predict` scores `x · w + b` in `F4` and returns class `1` only when
`sign_sigma` is strictly positive. A score of `0` returns class `0`.

`predict_proba` applies a logistic display map to the float projection
of that score. Each row sums to `1`. The values are NumPy floats, not
`F4`, and they are not the empirical class frequencies. On the
imbalanced fixture with labels `[0, 0, 0, 1]` the positive display
probability is not `1/4`.

## What fit does not read

These are stored and then ignored by `fit`:

| name | where it is stored | read by `fit`? |
|---|---|---|
| `n_estimators` | `self.params` | no |
| `max_depth` | `self.params` | no |
| `learning_rate` | `self.params` | no |
| `random_state` | `self.params` | no |
| `class_prior_exact_` | assigned from label counts at the end of `fit` | no `Load` in `fit`; `predict` does not read it |

Changing any of the four parameters and refitting leaves
`weights_exact_` and `bias_exact_` byte-identical (canonical `to_json`
bytes, and `F4` equality). Replacing `class_prior_exact_` and refitting
leaves predictions byte-identical. The refit overwrites the prior from
the label counts; it does not consume the value that was written over.

`__init__` always constructs `ExactTOETensor(num_qubits=5)`. No method
on `TensorClassifier` other than `__init__` mentions `exact_tensor`.
A tracer substituted for that attribute records no reads from `fit`,
`predict`, `predict_proba`, or `exact_scores`. The instance is unused.
It is not removed here.

`rf`, `xgb`, `lgbm`, and `gb` are deprecated aliases. Each warns with
`DeprecationWarning` and returns the same `TensorModelAPI` object that
`exact_linear` returns. After `fit`, `weights_exact_`, `bias_exact_`,
and the family name `"exact_linear"` are byte-identical to a canonical
fit. They do not implement the vendor algorithms those names suggest.

## Edge cases

**One class.** Fitting labels that are all `1` is accepted: `{1}` is a
subset of `{0, 1}`. Under the default `center_only` mode the only class
mean is the centred global mean, which is `0`, and the empty class is
filled with `ZERO`. `weights_exact_` is the zero vector in all four
`F4` channels, every score is `0`, and every prediction is class `0`.

**`center_only` versus the raw centroid formula.** There is no public
`"raw"` preprocessing mode. On a two-class matrix the weights from
`tensor_mode="center_only"` equal `μ₁ − μ₀` computed on the
float-witnessed rows *before* centering. The global mean cancels in the
difference. The bias does **not** cancel. On
`[[0, 1], [0, 1], [4, 5]]` with labels `[0, 0, 1]` both paths give
weights `(F4(4), F4(4))`. The raw bias is `F4(-20)`; the centred bias
is `F4(-16/3)`.

**`range`.** On an asymmetric two-feature problem, `tensor_mode="range"`
is not the same classifier as `center_only`. For points `(0, 0)` and
`(2, 10)` the centred weights are `(F4(2), F4(10))` and the ranged
weights are `(F4(1), F4(1))`. The probe `(6, 0)` is class `0` under
centering and class `1` under range scaling. A constant column makes
`range_fit` raise `ValueError`
(`"range preprocessing cannot encode constant columns"`).

**Float ingress.** `witness_scalar(0.1)` equals `F4(Fraction(1, 10))`.
Channel `a` is `Fraction(1, 10)`, not `Fraction(0.1)`.

**Feature importance.** `feature_importances_` is the display metric
`|wᵢ| / Σ|w|`, where each `|wᵢ|` is `abs` of the float projection of
the `F4` coefficient. On the public path channels `b`, `c`, and `d` are
`0`, so the projection is `float(a)`. For weights `(F4(2), F4(6))` the
metric is exactly `(0.25, 0.75)`, and the entries are not `F4` objects.

**`theorem_proven`.** No instance method can set the flag to `True`.
Assignment, including `object.__setattr__`, raises `PlaneViolation`.
Writing the name into the instance dictionary does not override the
property. `from_artifact` forces the governance state back to
`"unproven"` even if the artifact says `theorem_proven: true`.
The only assignment of `_governance_state = "proven"` in
`TensorClassifier` is inside `__init__`, and only after `govern`
accepts a proof file. `load_proof` is called only from `govern`.
Passing `theorem_proven=` into the constructor raises `PlaneViolation`;
the boolean is not a constructor argument.

## Not done

The dead parameters and the unused tensor are descriptive findings.
Deleting them would be a behaviour change to construction and to the
artifact `params` payload. That requires a separate decision record.

Tests: `tests/test_kellogg_exact_linear_algorithm_audit.py`, cases
N1–N14. Numerical assertions are exact `F4` or `Fraction` equality,
except the display checks in N7 and N13, which compare floats because
those outputs are defined to be floats. No `pytest.approx` is used on
an `F4` value.
