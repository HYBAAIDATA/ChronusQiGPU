# exact_linear audit

Repository: `QUANTUMDATA2/PYTHIAPhiMiner`.
Scope: document and pin two findings about `kellogg.tensor_ml.exact_linear`.
Behaviour of `exact_linear`, `fit`, `predict`, `sign_sigma`, and
`witness_scalar` is unchanged. Canonical fit weights before and after
the docstring edits are identical (see the verification note below).

## Section A — field channels

Finding. `exact_linear` is declared on `F4 = Q(√2) + iQ(√2)`. The
public fit path casts inputs through `float` before `F4` construction,
so only rational channel `a` is populated. Channels `b` (`√2`), `c`
(`i`), and `d` (`i√2`) stay zero unless the caller bypasses `fit` and
supplies `F4` coefficients. On the public path `sign_sigma` reduces to
the sign of channel `a` (an integer comparison when that rational is an
integer). A score of `1+i` raises `PlaneViolation` from `predict`;
`sign_sigma` itself raises `TypeError`. A complex value passed *into*
`fit` does not raise: `dtype=float` drops the imaginary part.

| test | claim | result |
|---|---|---|
| A | `F4` basis identities and `FIELD_ID` | PASS |
| B | public fit of `0.1`, `0.3` fills only channel `a`; weight `1/5`, bias `−1/150` | PASS |
| C | `√2` ingress is not `F4(0, 1)`; fitted weights keep `b = 0` | PASS |
| D | artifact weight `F4(0, 1)` scores as `F4(0, 1)` and `sign_sigma` is `1` | PASS |
| E | public scores compare the integer numerator of channel `a` | PASS |
| F | `1+i` raises `TypeError` from `sign_sigma` and `PlaneViolation` from `predict` | PASS |
| G | `1+1j` through `fit` is stored as `F4(1)`, not `1+i` | PASS |
| H | `witness_scalar(0.1) == F4(Fraction(1, 10))`, not `Fraction(0.1)` | PASS |
| I | score `0` has `sign_sigma == 0` and `predict` returns class `0` | PASS |

Document: `docs/kellogg/exact_linear_field_audit.md`.
Tests: `tests/test_kellogg_exact_linear_field_audit.py`.

### Field-channel pass/fail

- PASS A `test_A_declared_field_is_q_sqrt2_plus_i_q_sqrt2`
- PASS B `test_B_public_fit_populates_only_rational_channel`
- PASS C `test_C_sqrt2_channel_is_dormant_on_public_ingress`
- PASS D `test_D_direct_f4_coefficients_keep_the_sqrt2_channel`
- PASS E `test_E_sign_sigma_degenerates_to_channel_a_comparison`
- PASS F `test_F_one_plus_i_raises_plane_violation`
- PASS G `test_G_imaginary_channel_is_discarded_by_the_float_cast`
- PASS H `test_H_float_witness_is_decimal_text_not_binary_fraction`
- PASS I `test_I_zero_score_predicts_class_zero_by_integer_comparison`

File result: 9 passed, 0 failed.

## Section B — algorithm class

Finding. `fit` computes `w = μ₁ − μ₀` and `b = −w · ((μ₁ + μ₀)/2)`.
It is a nearest-centroid classifier expressed as an exact linear
threshold. It is not a forest, booster, or fitted regression.
`n_estimators`, `max_depth`, `learning_rate`, `random_state`, and
`class_prior_exact_` are stored but never read by `fit`. `rf`, `xgb`,
`lgbm`, and `gb` construct this same object and warn. Score `0` maps
to class `0`. `predict_proba` is a display map.

| test | claim | result |
|---|---|---|
| N1 | weights `(F4(6),)`, bias `F4(−6)` match `μ₁ − μ₀` and `−w · mid` | PASS |
| N2 | symmetric midpoint score is `F4(0)`; `predict` is class `0` | PASS |
| N3 | changing each dead parameter and refitting leaves weights and bias byte-identical | PASS |
| N4 | replacing `class_prior_exact_` and refitting leaves predictions byte-identical; `fit` only stores the prior | PASS |
| N5 | `__init__` builds `ExactTOETensor(num_qubits=5)`; no later method reads it | PASS |
| N6 | query at the class-mean midpoint has `sign_sigma == 0` and `predict` returns `0` | PASS |
| N7 | `predict_proba` rows sum to `1.0`, are not `F4`, and are not the empirical frequency `1/4` | PASS |
| N8 | `rf`, `xgb`, `lgbm`, `gb` warn and match `exact_linear` weights, bias, and family name | PASS |
| N9 | all-ones labels give the zero weight in all four channels and predict class `0` | PASS |
| N10 | `center_only` weights equal the raw centroid difference `(F4(4), F4(4))`; biases differ (`−16/3` vs `−20`) | PASS |
| N11 | `range` weights and the probe prediction differ from `center_only`; a constant column raises `ValueError` | PASS |
| N12 | `witness_scalar(0.1).a == Fraction(1, 10)` and is not `Fraction(0.1)` | PASS |
| N13 | importances of weights `(2, 6)` are exactly `(0.25, 0.75)` via `abs(float(a))` | PASS |
| N14 | no instance method sets `theorem_proven`; only `govern` loads a proof file | PASS |

Document: `docs/kellogg/exact_linear_algorithm_audit.md`.
Tests: `tests/test_kellogg_exact_linear_algorithm_audit.py`.

### Algorithm-class pass/fail

- PASS N1 `test_N1_weight_formula_is_centroid_difference`
- PASS N2 `test_N2_symmetric_midpoint_scores_zero_and_predicts_class_zero`
- PASS N3 `test_N3_dead_parameters_do_not_change_the_fitted_threshold`
- PASS N4 `test_N4_dead_prior_does_not_change_predictions`
- PASS N5 `test_N5_exact_toe_tensor_is_constructed_and_unread`
- PASS N6 `test_N6_exact_midpoint_has_sign_zero_and_predicts_class_zero`
- PASS N7 `test_N7_predict_proba_is_a_display_map`
- PASS N8 `test_N8_aliases_fit_the_same_exact_linear_object`
- PASS N9 `test_N9_one_class_input_has_zero_weights_and_predicts_class_zero`
- PASS N10 `test_N10_center_only_weights_match_the_raw_centroid_difference`
- PASS N11 `test_N11_range_mode_differs_and_rejects_a_constant_column`
- PASS N12 `test_N12_float_ingress_witness_is_one_tenth_not_binary`
- PASS N13 `test_N13_feature_importance_is_the_float_projection`
- PASS N14 `test_N14_theorem_proven_is_not_set_by_instance_methods`

File result: 14 passed, 0 failed.

## Verification

Both new files together: 23 passed, 0 failed
(`python -m unittest tests/test_kellogg_exact_linear_field_audit.py tests/test_kellogg_exact_linear_algorithm_audit.py`).

Existing kellogg suite
(`tests/test_kellogg_tensor.py`, `tests/test_toe_tensor_ml.py`):
44 ran, 41 passed, 3 failed. The three failures are the pre-existing
`test_retired_toe_paths_do_not_resolve` cases for `toe.exact_tensor`,
`toe.quantum_tensor`, and `toe.tensor_ml`. That pass count is unchanged
by this audit.

Canonical fit of `[[0, 0], [0, 1], [1, 0], [1, 1]]` with labels
`[0, 0, 1, 1]` and the stored dead parameters
`(n_estimators=100, max_depth=8, learning_rate=0.005, random_state=42)`
produced the same weight JSON, bias JSON, and predictions before and
after the docstring edits.

`float(`, `np.float`, and `math.sqrt` do not appear in any `F4`
assertion. The only `float(` in the new tests is N13, which is the
display projection the importance metric is defined to use.

Docstring notes were appended on `exact_linear`, `TensorClassifier.fit`,
`TensorClassifier.predict`, and the module-level `fit` and `predict`.
`F4` and `sign_sigma` in `kellogg/exact_tensor.py` received docstring
notes only.
