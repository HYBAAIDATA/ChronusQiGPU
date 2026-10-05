"""Semantic-IR contracts: op kinds, axis semantics, shape algebra, bounds."""


import pytest

from tensor.contracts import (
    MAX_TENSOR_ELEMENTS,
    DependencyScope,
    ExactnessMode,
    Precision,
    TensorOperationSpec,
    TensorOpKind,
    TensorRequest,
    TensorShape,
    estimate_bytes,
)
from tensor.errors import TensorMemoryError, TensorValidationError


def _spec(name="matmul", **overrides):
    defaults = dict(
        name=name,
        input_shapes=(TensorShape((2, 3)), TensorShape((3, 4))),
        output_shape=TensorShape((2, 4)),
        dtype=Precision.FLOAT64,
        exactness_mode=ExactnessMode.EXACT,
        op_count=48,
    )
    defaults.update(overrides)
    return TensorOperationSpec(**defaults)


def _equal(name, **overrides):
    return _spec(
        name,
        input_shapes=(TensorShape((2, 2)), TensorShape((2, 2))),
        output_shape=TensorShape((2, 2)),
        **overrides,
    )


def test_kind_resolves_from_canonical_name():
    assert _spec("matmul").kind is TensorOpKind.MATMUL
    assert _equal("hadamard").kind is TensorOpKind.HADAMARD
    assert _spec("not-supported").kind is None


def test_explicit_op_kind_wins_over_name():
    spec = _spec("custom-name", op_kind=TensorOpKind.MATMUL)
    assert spec.kind is TensorOpKind.MATMUL
    with pytest.raises(TensorValidationError):
        _spec("matmul", op_kind="matmul")  # must be the enum, not a string


def test_dependency_scope_classification():
    assert _spec("matmul").dependency_scope is DependencyScope.GLOBAL
    assert _equal("hadamard").dependency_scope is DependencyScope.COORDINATE
    reduce_spec = _spec(
        "reduce",
        input_shapes=(TensorShape((2, 3)),),
        output_shape=TensorShape((2,)),
        input_axes=(("i", "j"),),
        output_axes=("i",),
    )
    assert reduce_spec.kind is TensorOpKind.REDUCE
    assert reduce_spec.dependency_scope is DependencyScope.AXIS
    assert _spec("not-supported").dependency_scope is None


def test_axis_dimension_consistency_enforced():
    with pytest.raises(TensorValidationError, match="inconsistent extents"):
        _spec(
            "contract",
            input_axes=(("i", "k"), ("k", "j")),
            output_axes=("i", "j"),
            contract_axes=("k",),
            input_shapes=(TensorShape((2, 3)), TensorShape((4, 5))),
            output_shape=TensorShape((2, 5)),
        )


def test_output_axis_must_appear_on_an_input():
    with pytest.raises(TensorValidationError, match="does not appear on any input"):
        _spec(
            "contract",
            input_axes=(("i", "k"), ("k", "j")),
            output_axes=("i", "z"),
            contract_axes=("k",),
        )


def test_contract_axis_cannot_reach_output():
    with pytest.raises(TensorValidationError, match="cannot appear in the output space"):
        _spec(
            "contract",
            input_axes=(("i", "k"), ("k", "j")),
            output_axes=("i", "j", "k"),
            output_shape=TensorShape((2, 4, 3)),
            contract_axes=("k",),
        )


def test_contract_axis_must_be_shared():
    with pytest.raises(TensorValidationError, match="at least two inputs"):
        _spec(
            "contract",
            input_axes=(("i", "k"), ("l", "j")),
            output_axes=("i", "j", "l"),
            output_shape=TensorShape((2, 4, 3)),
            contract_axes=("k",),
        )


def test_duplicate_axis_names_rejected():
    with pytest.raises(TensorValidationError, match="unique"):
        _spec(
            "contract",
            input_axes=(("i", "i"), ("i", "j")),
            output_axes=("i", "j"),
            contract_axes=("i",),
        )


def test_matmul_shape_algebra_fails_closed():
    with pytest.raises(TensorValidationError, match="inner dims"):
        _spec(input_shapes=(TensorShape((2, 3)), TensorShape((4, 4))))
    with pytest.raises(TensorValidationError, match="output must be"):
        _spec(output_shape=TensorShape((2, 3)))
    with pytest.raises(TensorValidationError, match="rank-2"):
        _spec(
            input_shapes=(TensorShape((2, 3, 1)), TensorShape((3, 1))),
            output_shape=TensorShape((2, 1)),
        )


def test_elementwise_family_requires_equal_shapes():
    with pytest.raises(TensorValidationError, match="equal shape"):
        _spec("hadamard", input_shapes=(TensorShape((2, 2)), TensorShape((3, 3))))
    with pytest.raises(TensorValidationError, match="equal shape"):
        _spec("add", input_shapes=(TensorShape((2, 2)), TensorShape((2, 2, 1))))


def test_scale_requires_scalar_second_operand():
    with pytest.raises(TensorValidationError, match="single-element scalar"):
        _spec(
            "scale",
            input_shapes=(TensorShape((2, 2)), TensorShape((2, 2))),
            output_shape=TensorShape((2, 2)),
        )
    ok = _spec(
        "scale",
        input_shapes=(TensorShape((2, 2)), TensorShape((1,))),
        output_shape=TensorShape((2, 2)),
    )
    assert ok.dependency_scope is DependencyScope.COORDINATE


def test_kron_shape_algebra():
    _spec(
        "kron",
        input_shapes=(TensorShape((2, 3)), TensorShape((4, 5))),
        output_shape=TensorShape((8, 15)),
    )
    with pytest.raises(TensorValidationError, match="pairwise product"):
        _spec(
            "kron",
            input_shapes=(TensorShape((2, 3)), TensorShape((4, 5))),
            output_shape=TensorShape((8, 16)),
        )
    with pytest.raises(TensorValidationError, match="equal rank"):
        _spec(
            "kron",
            input_shapes=(TensorShape((2,)), TensorShape((4, 5))),
            output_shape=TensorShape((8, 5)),
        )


def test_transpose_axis_permutation_checked():
    _spec(
        "transpose",
        input_shapes=(TensorShape((2, 3)),),
        output_shape=TensorShape((3, 2)),
        input_axes=(("i", "j"),),
        output_axes=("j", "i"),
    )
    with pytest.raises(TensorValidationError, match="permutation"):
        _spec(
            "transpose",
            input_shapes=(TensorShape((2, 3)),),
            output_shape=TensorShape((2, 2)),
        )


def test_reduce_keeps_declared_axes():
    _spec(
        "reduce",
        input_shapes=(TensorShape((2, 3)),),
        output_shape=TensorShape((2,)),
        input_axes=(("i", "j"),),
        output_axes=("i",),
    )
    with pytest.raises(TensorValidationError, match="extent"):
        _spec(
            "reduce",
            input_shapes=(TensorShape((2, 3)),),
            output_shape=TensorShape((3,)),
            input_axes=(("i", "j"),),
            output_axes=("i",),
        )


def test_contracted_axes_derived_when_not_declared():
    spec = _spec(
        "matmul",
        input_axes=(("i", "k"), ("k", "j")),
        output_axes=("i", "j"),
    )
    assert spec.contracted_axes == ("k",)


def test_activation_is_shape_preserving():
    _spec(
        "activation",
        input_shapes=(TensorShape((2, 2)),),
        output_shape=TensorShape((2, 2)),
    )
    with pytest.raises(TensorValidationError, match="shape-preserving"):
        _spec(
            "activation",
            input_shapes=(TensorShape((2, 2)),),
            output_shape=TensorShape((4,)),
        )


def test_fma_requires_three_equal_inputs():
    _spec(
        "fma",
        input_shapes=(TensorShape((2,)), TensorShape((2,)), TensorShape((2,))),
        output_shape=TensorShape((2,)),
    )
    with pytest.raises(TensorValidationError, match="three inputs"):
        _spec(
            "fma",
            input_shapes=(TensorShape((2,)), TensorShape((2,))),
            output_shape=TensorShape((2,)),
        )


def test_element_count_overflow_fails_before_allocation():
    huge = TensorShape((MAX_TENSOR_ELEMENTS,))
    assert huge.size == MAX_TENSOR_ELEMENTS
    with pytest.raises(TensorValidationError, match="64-bit addressable"):
        TensorShape((MAX_TENSOR_ELEMENTS, 2))
    with pytest.raises(TensorValidationError):
        TensorShape((2**62, 2**62))


def test_estimate_bytes_overflow_checked():
    with pytest.raises(TensorValidationError, match="64-bit addressable"):
        estimate_bytes((TensorShape((MAX_TENSOR_ELEMENTS,)),), Precision.COMPLEX128)
    with pytest.raises(TensorMemoryError):
        TensorRequest(
            operation=_spec(
                input_shapes=(TensorShape((20000, 20000)), TensorShape((20000, 20000))),
                output_shape=TensorShape((20000, 20000)),
            )
        )


def test_negative_and_zero_dims_still_fail():
    with pytest.raises(TensorValidationError):
        TensorShape((-1,))
    with pytest.raises(TensorValidationError):
        TensorShape((0, 2))
    with pytest.raises(TensorValidationError):
        TensorShape(())


def test_axes_without_input_axes_rejected():
    with pytest.raises(TensorValidationError, match="require declared input_axes"):
        _spec("matmul", output_axes=("i", "j"))
