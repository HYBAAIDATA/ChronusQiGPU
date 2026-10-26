"""Canonical Chronus compute instruction surface.

The ABI describes intent. Backends advertise only operators they execute and
verify; an absent operator is never emulated silently.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class OperatorFamily(str, Enum):
    ELEMENTWISE = "elementwise"
    LINEAR = "linear"
    TENSOR = "tensor"
    SEARCH = "search"
    FOLD = "fold"
    PHI_LUCAS = "phi_lucas"
    CRYPTOGRAPHIC = "cryptographic"
    QUANTUM_MATH = "quantum_math"


class ExecutionClass(str, Enum):
    DENSE_NATIVE = "dense_native"
    FOLDED_NATIVE = "folded_native"
    PARTIAL_UNFOLD = "partial_unfold"
    STREAMED_FOLD = "streamed_fold"
    GEODESIC = "geodesic"
    SYMBOLIC = "symbolic"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    family: OperatorFamily
    dtypes: tuple[str, ...]
    execution_classes: tuple[ExecutionClass, ...]
    verification_authority: str


OPERATORS = {
    # Existing physically/reference evidenced surface.
    "add": OperatorSpec("add", OperatorFamily.ELEMENTWISE, ("float32",), (ExecutionClass.DENSE_NATIVE,), "reference_numeric"),
    "scale": OperatorSpec("scale", OperatorFamily.ELEMENTWISE, ("float32",), (ExecutionClass.DENSE_NATIVE,), "reference_numeric"),
    "hadamard": OperatorSpec("hadamard", OperatorFamily.ELEMENTWISE, ("float32",), (ExecutionClass.DENSE_NATIVE,), "reference_numeric"),
    "matmul": OperatorSpec("matmul", OperatorFamily.LINEAR, ("float32",), (ExecutionClass.DENSE_NATIVE, ExecutionClass.PARTIAL_UNFOLD, ExecutionClass.HYBRID), "reference_numeric"),
    "kron": OperatorSpec("kron", OperatorFamily.TENSOR, ("float32",), (ExecutionClass.DENSE_NATIVE,), "reference_numeric"),
    "tensor_contract": OperatorSpec("tensor_contract", OperatorFamily.TENSOR, ("float32",), (ExecutionClass.DENSE_NATIVE, ExecutionClass.PARTIAL_UNFOLD, ExecutionClass.GEODESIC), "reference_numeric"),
    "tensor_svd": OperatorSpec("tensor_svd", OperatorFamily.TENSOR, ("float64",), (ExecutionClass.DENSE_NATIVE,), "reference_numeric"),
    "fold": OperatorSpec("fold", OperatorFamily.FOLD, ("bytes",), (ExecutionClass.FOLDED_NATIVE, ExecutionClass.STREAMED_FOLD), "aethel_certificate"),
    "unfold": OperatorSpec("unfold", OperatorFamily.FOLD, ("bytes",), (ExecutionClass.PARTIAL_UNFOLD, ExecutionClass.DENSE_NATIVE), "aethel_certificate"),
    "partial_unfold": OperatorSpec("partial_unfold", OperatorFamily.FOLD, ("bytes",), (ExecutionClass.PARTIAL_UNFOLD,), "aethel_certificate"),
    "phi_transform": OperatorSpec("phi_transform", OperatorFamily.PHI_LUCAS, ("float64",), (ExecutionClass.SYMBOLIC, ExecutionClass.DENSE_NATIVE), "deterministic_replay"),
    "lucas_transform": OperatorSpec("lucas_transform", OperatorFamily.PHI_LUCAS, ("int",), (ExecutionClass.SYMBOLIC,), "deterministic_replay"),
    "sha256": OperatorSpec("sha256", OperatorFamily.CRYPTOGRAPHIC, ("bytes",), (ExecutionClass.DENSE_NATIVE,), "sha256"),
    "sha256d_scan": OperatorSpec("sha256d_scan", OperatorFamily.CRYPTOGRAPHIC, ("bytes",), (ExecutionClass.DENSE_NATIVE, ExecutionClass.HYBRID), "sha256d_target"),
    "sha256d_verify": OperatorSpec("sha256d_verify", OperatorFamily.CRYPTOGRAPHIC, ("bytes",), (ExecutionClass.DENSE_NATIVE,), "sha256d"),
    "quantum_program": OperatorSpec(
        "quantum_program",
        OperatorFamily.QUANTUM_MATH,
        ("q8", "tableau"),
        (ExecutionClass.SYMBOLIC,),
        "turing_exact_certificate_replay",
    ),
    "exact_graph": OperatorSpec(
        "exact_graph",
        OperatorFamily.TENSOR,
        ("q8",),
        (ExecutionClass.FOLDED_NATIVE,),
        "kellogg_exact_graph_replay",
    ),
    "grid_geometry": OperatorSpec(
        "grid_geometry",
        OperatorFamily.SEARCH,
        ("uint8",),
        (ExecutionClass.DENSE_NATIVE,),
        "coordinate_component_oracle",
    ),
    "modular_geometry": OperatorSpec(
        "modular_geometry",
        OperatorFamily.SEARCH,
        ("rational",),
        (ExecutionClass.GEODESIC,),
        "psl2z_metric_identity",
    ),
    # Reserved vocabulary: declared but not advertised by an adapter until real.
    "clifford": OperatorSpec("clifford", OperatorFamily.QUANTUM_MATH, ("tableau",), (ExecutionClass.SYMBOLIC,), "tableau_replay"),
    "tableau_transform": OperatorSpec("tableau_transform", OperatorFamily.QUANTUM_MATH, ("tableau",), (ExecutionClass.SYMBOLIC,), "tableau_replay"),
    "vqc_operator": OperatorSpec("vqc_operator", OperatorFamily.QUANTUM_MATH, ("float64",), (ExecutionClass.HYBRID,), "backend_measurement"),
}


def operator(name: str) -> OperatorSpec:
    try:
        return OPERATORS[name]
    except KeyError as exc:
        raise ValueError(f"unknown Chronus operator {name!r}") from exc
