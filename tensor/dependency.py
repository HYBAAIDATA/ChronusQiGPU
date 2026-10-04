"""Output-region → input dependency cones for tensor operations.

Given a :class:`TensorOperationSpec` and a shaped output region (one
``slice``/``int`` per output axis), :func:`dependency_cone` returns the
minimal per-input regions the operation needs — the dependency set a
folded-state decoder must reconstruct.

Rules by :class:`DependencyScope`:

* ``coordinate`` — every input needs the same coordinates the output needs
  (elementwise/hadamard/fma/scale/activation); ``transpose`` needs the
  region permuted back into the input's axis order.
* ``axis`` (``reduce``) — kept output axes take the region's slices;
  reduced axes take the whole input dim.
* ``global`` — ``matmul``/``contract`` resolve via axis names: an output
  axis present on an input takes the region slice; a contracted axis takes
  the full dim (each output element reads the whole contraction fibre).
  ``kron``'s cone is a bounding hull (mixed-radix; declared, not minimal)
  and is explicitly marked ``hull=True``. An op with no structured kind is
  opaque: every input's cone is the whole input, also declared honestly.

Everything here is pure index algebra — nothing touches data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from .contracts import DependencyScope, TensorOperationSpec, TensorOpKind
from .errors import TensorValidationError


@dataclass(frozen=True)
class InputCone:
    """The dependency cone of one input operand for an output region.

    ``slices`` is a per-axis box when a bounded cone exists; ``whole_input``
    means every element of the operand may be read (a genuine global
    dependency). ``hull`` marks a declared superset (the true cone is a
    non-rectangular index set enclosed by the box).
    """

    input_index: int
    slices: Optional[Tuple[slice, ...]]
    whole_input: bool
    scope: DependencyScope
    hull: bool = False
    detail: str = ""


@dataclass(frozen=True)
class DependencyCone:
    """One operation's resolved input dependency set for an output region."""

    operation: str
    output_slices: Tuple[slice, ...]
    inputs: Tuple[InputCone, ...]

    @property
    def any_global(self) -> bool:
        return any(c.whole_input for c in self.inputs)


def _region_slices(
    shape: Tuple[int, ...], specs: Tuple[object, ...]
) -> Tuple[slice, ...]:
    if len(specs) != len(shape):
        raise TensorValidationError(
            f"output region has {len(specs)} entries for a rank-{len(shape)} result"
        )
    resolved = []
    for axis, (dim, spec) in enumerate(zip(shape, specs)):
        if isinstance(spec, slice):
            if (spec.step or 1) != 1:
                raise TensorValidationError(
                    "dependency cones support unit-step output slices only"
                )
            for bound in (spec.start, spec.stop):
                if bound is not None and (
                    int(bound) > int(dim) or int(bound) < -int(dim)
                ):
                    raise TensorValidationError(
                        f"output axis {axis} slice {spec!r} outside dim {dim}"
                    )
            start, stop, _ = spec.indices(int(dim))
            if start < 0 or stop > int(dim) or stop < start:
                raise TensorValidationError(
                    f"output axis {axis} slice [{start}, {stop}) outside dim {dim}"
                )
            if stop == start:
                raise TensorValidationError("output region is empty")
            resolved.append(slice(start, stop))
        elif isinstance(spec, int) and not isinstance(spec, bool):
            pos = int(spec) % int(dim)
            resolved.append(slice(pos, pos + 1))
        else:
            raise TensorValidationError(
                f"unsupported region specifier {spec!r} on output axis {axis}"
            )
    return tuple(resolved)


def _full(shape: Tuple[int, ...]) -> Tuple[slice, ...]:
    return tuple(slice(0, int(d)) for d in shape)


def _canonical_matmul_axes(spec: TensorOperationSpec):
    """Declared axes, or the canonical matmul binding (i,k)·(k,j)→(i,j)."""
    if spec.input_axes is not None and spec.output_axes is not None:
        return spec.input_axes, spec.output_axes
    return (("i", "k"), ("k", "j")), ("i", "j")


def dependency_cone(
    operation: TensorOperationSpec, output_slices: Tuple[object, ...]
) -> DependencyCone:
    """Resolve the per-input dependency set for an output region."""
    region = _region_slices(operation.output_shape.dims, tuple(output_slices))
    kind = operation.kind
    scope = operation.dependency_scope
    shapes = [s.dims for s in operation.input_shapes]

    if kind is None or scope is None:
        return DependencyCone(
            operation.name,
            region,
            tuple(
                InputCone(
                    i,
                    None,
                    True,
                    DependencyScope.GLOBAL,
                    detail="opaque operation — whole-input dependency declared",
                )
                for i in range(len(shapes))
            ),
        )

    if scope is DependencyScope.COORDINATE:
        if kind is TensorOpKind.TRANSPOSE and operation.input_axes and operation.output_axes:
            inverse = _region_slices(
                shapes[0],
                tuple(
                    region[operation.output_axes.index(axis)]
                    for axis in operation.input_axes[0]
                ),
            )
            inputs = (InputCone(0, inverse, False, scope, detail="transpose inverse"),)
        else:
            inputs = tuple(
                InputCone(i, region, False, scope)
                if s == operation.output_shape.dims or kind is not TensorOpKind.SCALE
                else InputCone(i, _full(s), False, scope)
                for i, s in enumerate(shapes)
            )
        return DependencyCone(operation.name, region, inputs)

    if scope is DependencyScope.AXIS:
        # reduce: output axes keep their region slice; all other input axes
        # (the reduced ones) take the whole dim.
        if operation.input_axes and operation.output_axes:
            axis_slice = dict(zip(operation.output_axes, region))
            slices = tuple(
                axis_slice.get(axis, slice(0, int(dim)))
                for axis, dim in zip(operation.input_axes[0], shapes[0])
            )
            return DependencyCone(
                operation.name, region, (InputCone(0, slices, False, scope),)
            )
        return DependencyCone(
            operation.name,
            region,
            (
                InputCone(
                    0, None, True, scope,
                    detail="reduce without declared axes — whole input required",
                ),
            ),
        )

    # GLOBAL scope — matmul/contract/kron.
    if kind in (TensorOpKind.MATMUL, TensorOpKind.CONTRACT):
        input_axes, output_axes = _canonical_matmul_axes(operation)
        axis_slice = dict(zip(output_axes, region))
        cones = []
        for index, (axes, dims) in enumerate(zip(input_axes, shapes)):
            slices = tuple(
                axis_slice.get(axis, slice(0, int(dim)))
                for axis, dim in zip(axes, dims)
            )
            cones.append(
                InputCone(
                    index,
                    slices,
                    False,
                    scope,
                    detail="output axes take region slices; contracted axes take full fibres",
                )
            )
        return DependencyCone(operation.name, region, tuple(cones))

    if kind is TensorOpKind.KRON:
        # C[i*mb + j] = A[i] * B[j] per dim. The true cone is a
        # mixed-radix index set; the honest bound is its box hull.
        cones = []
        for operand, dims in enumerate(shapes):
            hull_slices = []
            for axis, (a_dim, b_dim) in enumerate(zip(shapes[0], shapes[1])):
                out_lo = region[axis].start or 0
                out_hi = (region[axis].stop or operation.output_shape.dims[axis]) - 1
                if operand == 0:
                    lo, hi = out_lo // b_dim, out_hi // b_dim
                else:
                    lo, hi = out_lo % b_dim, out_hi % b_dim
                hull_slices.append(slice(lo, hi + 1))
            cones.append(
                InputCone(
                    operand, tuple(hull_slices), False, scope,
                    hull=True,
                    detail="mixed-radix cone bounded by its box hull (declared superset)",
                )
            )
        return DependencyCone(operation.name, region, tuple(cones))

    return DependencyCone(  # pragma: no cover - every kind handled above
        operation.name,
        region,
        tuple(InputCone(i, None, True, scope) for i in range(len(shapes))),
    )


__all__ = ["DependencyCone", "InputCone", "dependency_cone"]
