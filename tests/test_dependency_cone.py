"""Dependency-cone algebra: output region → minimal input regions."""

import pytest

from tensor.contracts import ExactnessMode, TensorOperationSpec, TensorShape
from tensor.dependency import dependency_cone
from tensor.errors import TensorValidationError


def _spec(name, inputs, out, **kw):
    return TensorOperationSpec(
        name=name,
        input_shapes=[TensorShape(tuple(i)) for i in inputs],
        output_shape=TensorShape(tuple(out)),
        dtype="float64",
        exactness_mode=ExactnessMode.LOSSY_APPROX,
        op_count=1,
        **kw,
    )


def test_elementwise_coordinate_cone():
    spec = _spec("add", [(8, 8), (8, 8)], (8, 8))
    cone = dependency_cone(spec, (slice(2, 4), slice(1, 5)))
    assert len(cone.inputs) == 2
    for c in cone.inputs:
        assert not c.whole_input
        assert c.slices == (slice(2, 4), slice(1, 5))


def test_matmul_row_block_cone_is_bounded():
    spec = _spec(
        "matmul",
        [(6, 5), (5, 7)],
        (6, 7),
        input_axes=(("i", "k"), ("k", "j")),
        output_axes=("i", "j"),
    )
    cone = dependency_cone(spec, (slice(2, 4), slice(0, 3)))
    a_cone, b_cone = cone.inputs
    # Output rows 2:4 read A rows 2:4 (all k), B cols 0:3 (all k).
    assert a_cone.slices == (slice(2, 4), slice(0, 5))
    assert b_cone.slices == (slice(0, 5), slice(0, 3))
    assert not cone.any_global


def test_matmul_default_axes_when_undeclared():
    spec = _spec("matmul", [(4, 3), (3, 5)], (4, 5))
    cone = dependency_cone(spec, (slice(1, 2), slice(2, 4)))
    a_cone, b_cone = cone.inputs
    assert a_cone.slices == (slice(1, 2), slice(0, 3))
    assert b_cone.slices == (slice(0, 3), slice(2, 4))


def test_matmul_full_output_cone_covers_inputs():
    spec = _spec("matmul", [(4, 3), (3, 5)], (4, 5))
    cone = dependency_cone(spec, (slice(None), slice(None)))
    a_cone, b_cone = cone.inputs
    assert a_cone.slices == (slice(0, 4), slice(0, 3))
    assert b_cone.slices == (slice(0, 3), slice(0, 5))
    # Explicit whole-region cones are bounded regions, not opaque globals.


def test_contract_axis_cone():
    # Two contracted axes + two free axes, all mapped through the region.
    spec = _spec(
        "contract",
        [(4, 6, 5), (5, 7, 4)],
        (4, 6, 7, 4),
        input_axes=(("b", "m", "k"), ("k", "j", "n")),
        output_axes=("b", "m", "j", "n"),
        contract_axes=("k",),
    )
    cone = dependency_cone(spec, (slice(0, 2), slice(1, 3), slice(3, 5), slice(0, 4)))
    a_cone, b_cone = cone.inputs
    assert a_cone.slices == (slice(0, 2), slice(1, 3), slice(0, 5))
    assert b_cone.slices == (slice(0, 5), slice(3, 5), slice(0, 4))


def test_reduce_axis_cone():
    spec = _spec(
        "reduce_sum",
        [(8, 6)],
        (8,),
        input_axes=(("i", "j"),),
        output_axes=("i",),
    )
    cone = dependency_cone(spec, (slice(2, 4),))
    (c,) = cone.inputs
    assert c.slices == (slice(2, 4), slice(0, 6))


def test_transpose_inverse_cone():
    spec = _spec(
        "transpose",
        [(6, 8)],
        (8, 6),
        input_axes=(("j", "i"),),
        output_axes=("i", "j"),
    )
    cone = dependency_cone(spec, (slice(2, 4), slice(1, 3)))
    (c,) = cone.inputs
    # Output region (i 2:4, j 1:3) maps back to input (j 1:3, i 2:4).
    assert c.slices == (slice(1, 3), slice(2, 4))


def test_kron_cone_is_declared_hull():
    spec = _spec("kron", [(2, 3), (3, 2)], (6, 6))
    cone = dependency_cone(spec, (slice(0, 3), slice(0, 3)))
    a_cone, b_cone = cone.inputs
    # Out rows 0:3 → A rows 0 (0..2 // 3), B rows 0..2 (mod 3 wraps).
    assert a_cone.hull and b_cone.hull
    assert a_cone.slices[0] == slice(0, 1)
    assert b_cone.slices[0] == slice(0, 3)


def test_opaque_op_cone_is_honest_global():
    spec = _spec("mystery_op", [(4, 4), (4, 4)], (4, 4))
    cone = dependency_cone(spec, (slice(0, 2), slice(0, 2)))
    assert cone.any_global
    assert all(c.whole_input for c in cone.inputs)


def test_region_validation_fail_closed():
    spec = _spec("add", [(4, 4), (4, 4)], (4, 4))
    with pytest.raises(TensorValidationError, match="outside"):
        dependency_cone(spec, (slice(0, 9), slice(None)))
    with pytest.raises(TensorValidationError, match="unit-step"):
        dependency_cone(spec, (slice(None), slice(0, 4, 2)))
    with pytest.raises(TensorValidationError, match="empty"):
        dependency_cone(spec, (slice(2, 2), slice(None)))
    with pytest.raises(TensorValidationError, match="rank-2"):
        dependency_cone(spec, (slice(None),))


def test_int_coordinate_region():
    spec = _spec("add", [(4, 4), (4, 4)], (4, 4))
    cone = dependency_cone(spec, (2, 1))
    assert cone.inputs[0].slices == (slice(2, 3), slice(1, 2))
