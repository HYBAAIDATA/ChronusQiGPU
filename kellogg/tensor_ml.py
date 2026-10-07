"""TOE Tensor Elevation: exact MLA1517 authority plane plus diagnostics.

This module implements the contract described by the TOE Tensor Elevation
specification.  Exact state, field arithmetic, preprocessing witnesses,
linear model decisions, commitments, CV folds, and metrics stay in
Q(sqrt(2)) + i Q(sqrt(2)).  Floats are produced only by explicitly marked
measurement helpers and are never persisted as authority data.

The legacy names (StandardScaler, RandomForestClassifier, XGBClassifier,
LGBMClassifier, GradientBoostingClassifier, and sklearn-style metrics) are
compatibility shims.  Their exact core is a field-closed linear kernel; their
probability arrays and feature-importance values are diagnostic measurements.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import warnings
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .exact_tensor import ExactTOETensor, F4, ONE, Qsqrt2, ZERO

FIELD_ID = "Q(sqrt2)+iQ(sqrt2)"
# Frozen domain-separation string hashed into every commitment; renaming it
# would change every stored commitment digest, so the bytes stay as they are.
SUBSTRATE_TAG = "chronus.mla1517.1"
ARTIFACT_SCHEMA = "kellogg.tensor-ml/v2"
# Legacy artifact lock values: read-only acceptance of v1 artifacts written
# before Kellogg stopped locking its file format to a consumer's version.
MLA1517_VERSION = SUBSTRATE_TAG
TOE_VERSION = "3.5.0"


# ---------------------------------------------------------------------------
# §1 exact field F = Q(sqrt(2)) + i Q(sqrt(2))
#
# The field itself (Qsqrt2, F4 and the ZERO/ONE constants) lives in the
# declared substrate ``kellogg.exact_tensor``; it is imported above and
# re-exported here so ``kellogg.tensor_ml`` consumers keep resolving.


def from_int(value: int) -> F4:
    return F4(value)


def from_rat(numerator: int, denominator: int) -> F4:
    if denominator == 0:
        raise ZeroDivisionError("rational denominator is zero")
    return F4(Fraction(numerator, denominator))


def witness_scalar(value: Any) -> F4:
    """Explicit input-boundary witness; floats are captured by decimal text."""
    if isinstance(value, F4):
        return value
    if isinstance(value, bool):
        return from_int(int(value))
    if isinstance(value, (int, np.integer)):
        return from_int(int(value))
    if isinstance(value, Fraction):
        return from_rat(value.numerator, value.denominator)
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            raise ValueError("non-finite value cannot be re-encoded")
        return from_rat(*Fraction(str(float(value))).as_integer_ratio())
    raise TypeError(f"value {value!r} has no exact rational witness")


# ---------------------------------------------------------------------------
# §4 planes, governance, and exact TensorState


class Plane(Enum):
    EXACT = "exact"
    DIAGNOSTIC = "diagnostic"
    GOVERNANCE = "governance"


class PlaneViolation(TypeError):
    pass


@dataclass(frozen=True)
class ExactValue:
    value: Any
    plane: Plane = Plane.EXACT


@dataclass(frozen=True)
class DiagnosticValue:
    value: Any
    provenance: str
    plane: Plane = Plane.DIAGNOSTIC


@dataclass(frozen=True)
class GovernanceValue:
    value: Any
    plane: Plane = Plane.GOVERNANCE


@dataclass(frozen=True)
class SchemaTag:
    basis: tuple[str, ...]
    order: str = "sigma:real-then-imag"
    dtype_map: str = "F4=(a,b,c,d) rational tuples"
    mla_version: str = MLA1517_VERSION
    field: str = FIELD_ID

    @property
    def hash(self) -> str:
        payload = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class TensorState:
    rows: tuple[tuple[F4, ...], ...]
    basis: tuple[str, ...]
    schema: SchemaTag
    identifier: str
    field: str = FIELD_ID
    mla_version: str = "MLA1517"
    subsystem_dims: tuple[int, ...] = ()
    subsystem_bases: tuple[tuple[str, ...], ...] = ()
    is_joint: bool = False

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.rows), len(self.rows[0]) if self.rows else len(self.basis))

    @classmethod
    def from_values(cls, values: Any, basis: Sequence[str] | None = None) -> "TensorState":
        matrix = np.asarray(values, dtype=object)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.ndim != 2:
            raise ValueError("TensorState input must be a vector or matrix")
        rows = tuple(tuple(witness_scalar(value) for value in row) for row in matrix.tolist())
        names = tuple(basis or [f"feature_{i}" for i in range(matrix.shape[1])])
        if len(names) != matrix.shape[1]:
            raise ValueError("basis length does not match tensor width")
        schema = SchemaTag(names)
        ident = hashlib.sha256(canonical_bytes_raw(rows, schema, "state")).hexdigest()
        return cls(rows, names, schema, ident)

    def subset(self, indices: Sequence[int], domain: str = "subset") -> "TensorState":
        rows = tuple(self.rows[i] for i in indices)
        ident = hashlib.sha256(canonical_bytes_raw(rows, self.schema, domain)).hexdigest()
        return TensorState(rows, self.basis, self.schema, ident, self.field, self.mla_version)


def _tag(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, "big") + encoded


def _signed_bytes(value: int) -> bytes:
    size = max(1, (abs(value).bit_length() + 8) // 8)
    raw = value.to_bytes(size, "big", signed=True)
    return len(raw).to_bytes(4, "big") + raw


def _frac_bytes(value: Fraction) -> bytes:
    return _signed_bytes(value.numerator) + _signed_bytes(value.denominator)


def canonical_bytes_raw(rows, schema: SchemaTag, domain: str) -> bytes:
    out = bytearray()
    out += _tag("TOE-STATE-v1") + _tag(domain) + _tag(schema.mla_version) + _tag(schema.field)
    out += _tag(schema.hash)
    out += len(rows).to_bytes(4, "big")
    width = len(rows[0]) if rows else len(schema.basis)
    out += width.to_bytes(4, "big")
    for row in rows:
        out += len(row).to_bytes(4, "big")
        for value in row:
            for component in (value.a, value.b, value.c, value.d):
                out += _frac_bytes(component)
    return bytes(out)


def canonical_bytes(state: TensorState, domain: str) -> bytes:
    return canonical_bytes_raw(state.rows, state.schema, domain)


def commit(state: TensorState, domain: str) -> str:
    return hashlib.sha256(canonical_bytes(state, domain)).hexdigest()


def row_commit(row: Sequence[F4], schema: SchemaTag, domain: str) -> str:
    return hashlib.sha256(canonical_bytes_raw((tuple(row),), schema, domain)).hexdigest()


def merkle_root(state: TensorState, domain: str) -> tuple[str, tuple[dict[str, Any], ...]]:
    leaves = [bytes.fromhex(row_commit(row, state.schema, domain)) for row in state.rows]
    if not leaves:
        return hashlib.sha256(_tag("empty-merkle") + _tag(domain)).hexdigest(), ()
    proofs: list[dict[str, Any]] = []
    level = leaves[:]
    while len(level) > 1:
        nxt = []
        for index in range(0, len(level), 2):
            left = level[index]
            right = level[index + 1] if index + 1 < len(level) else left
            nxt.append(hashlib.sha256(_tag("node") + left + right).digest())
        level = nxt
    for index in range(len(leaves)):
        proofs.append({"row": index, "leaf": leaves[index].hex(), "root": level[0].hex()})
    return level[0].hex(), tuple(proofs)


def assert_exact(value: Any) -> None:
    if isinstance(value, (DiagnosticValue, GovernanceValue)):
        raise PlaneViolation("diagnostic/governance value cannot enter the exact plane")
    if isinstance(value, float) or isinstance(value, np.floating):
        raise PlaneViolation("float cannot enter the exact plane without a rational witness")


def re_encode(value: Fraction) -> F4:
    if not isinstance(value, Fraction):
        raise PlaneViolation("re_encode accepts Rational/Fraction only")
    return from_rat(value.numerator, value.denominator)


def plane_multiply(left: Any, right: Any) -> Any:
    """Apply the declared plane algebra to scalar wrappers."""
    left_plane = getattr(left, "plane", Plane.EXACT)
    right_plane = getattr(right, "plane", Plane.EXACT)
    if Plane.GOVERNANCE in {left_plane, right_plane}:
        return GovernanceValue((left, right))
    if {left_plane, right_plane} == {Plane.EXACT, Plane.DIAGNOSTIC}:
        raise PlaneViolation("Exact ⊗ Diagnostic requires explicit measurement/re-encoding")
    if left_plane == Plane.DIAGNOSTIC and right_plane == Plane.DIAGNOSTIC:
        return DiagnosticValue((left, right), provenance="diagnostic:product")
    if isinstance(left, F4) and isinstance(right, F4):
        return left * right
    return left * right


def measure(state: TensorState, observable: str = "identity") -> DiagnosticValue:
    payload = commit(state, "measure:" + observable)
    values = np.asarray(
        [[float(v.real.a) + float(v.real.b) * np.sqrt(2.0) for v in row] for row in state.rows]
    )
    if observable == "identity":
        measured = values
    elif observable == "norm2":
        measured = np.sum(values * values, axis=1)
    else:
        raise ValueError(f"unknown observable {observable}")
    return DiagnosticValue(measured, payload)


class Unitary:
    """An exact unitary whose expensive validation is performed once.

    ``M`` is a read-only tuple-of-tuples of F4 values. The API never converts
    it to a NumPy view, so cached validation cannot be invalidated by shared
    mutable storage. Public mutation is rejected; reflective object-level
    mutation is outside the API contract.
    """

    def __init__(self, matrix: Sequence[Sequence[F4]], *, validate: bool = True):
        self._M = tuple(
            tuple(value if isinstance(value, F4) else witness_scalar(value) for value in row)
            for row in matrix
        )
        if len(self._M) == 0 or any(len(row) != len(self._M) for row in self._M):
            raise ValueError("unitary must be a non-empty square matrix")
        if validate:
            identity = [
                [ONE if i == j else ZERO for j in range(len(self._M))] for i in range(len(self._M))
            ]
            adjoint_times = [
                [
                    sum(
                        (self._M[k][i].conjugate() * self._M[k][j] for k in range(len(self._M))),
                        ZERO,
                    )
                    for j in range(len(self._M))
                ]
                for i in range(len(self._M))
            ]
            times_adjoint = [
                [
                    sum(
                        (self._M[i][k] * self._M[j][k].conjugate() for k in range(len(self._M))),
                        ZERO,
                    )
                    for j in range(len(self._M))
                ]
                for i in range(len(self._M))
            ]
            if adjoint_times != identity or times_adjoint != identity:
                raise PlaneViolation("matrix is not exactly unitary")
        self._checked = True

    @property
    def M(self):
        return self._M

    def apply(self, state: TensorState) -> TensorState:
        if not self._checked:
            raise PlaneViolation("unitary invariant was not validated")
        if len(self._M) != state.shape[1]:
            raise ValueError("unitary/state dimensions do not match")
        evolved = tuple(
            tuple(
                sum((self._M[i][j] * row[j] for j in range(len(self._M))), ZERO)
                for i in range(len(self._M))
            )
            for row in state.rows
        )
        return TensorState(
            evolved,
            state.basis,
            state.schema,
            hashlib.sha256(canonical_bytes_raw(evolved, state.schema, "unitary")).hexdigest(),
        )


def apply_unitary(U: Unitary | Sequence[Sequence[F4]], state: TensorState) -> TensorState:
    return (U if isinstance(U, Unitary) else Unitary(U)).apply(state)


def joint(left: TensorState, right: TensorState) -> TensorState:
    rows = tuple(
        tuple(a * b for a in left_row for b in right_row)
        for left_row in left.rows
        for right_row in right.rows
    )
    basis = tuple(f"{a}⊗{b}" for a in left.basis for b in right.basis)
    schema = SchemaTag(basis)
    return TensorState(
        rows,
        basis,
        schema,
        hashlib.sha256(canonical_bytes_raw(rows, schema, "joint")).hexdigest(),
        subsystem_dims=(left.shape[0], left.shape[1], right.shape[0], right.shape[1]),
        subsystem_bases=(tuple(left.basis), tuple(right.basis)),
        is_joint=True,
    )


def partial_trace(state: TensorState, keep: Sequence[int], *, max_dim: int = 2**16) -> TensorState:
    """True partial trace over the Kronecker factors of a joint state.

    For ``state = L ⊗ R`` (a 4-tensor J[i_L, i_R, a_L, a_R] flattened
    row-major), ``keep=(0,)`` returns Tr_R(J) = Tr(R)·L — the standard
    matrix partial trace, summing the traced factor's row/column indices.
    ``keep=(1,)`` returns Tr_L(J) = Tr(L)·R. ``keep`` selects subsystem
    factor indices, not columns; a column projection is a different
    operation and is intentionally not what this function does.
    """
    if not state.is_joint or not state.subsystem_dims:
        raise ValueError("partial_trace requires an explicitly joint TensorState")
    dims = state.subsystem_dims
    if len(dims) % 2 != 0 or np.prod(dims, dtype=int) != state.shape[0] * state.shape[1]:
        raise ValueError("joint subsystem dimensions do not match ordered state shape")
    if tuple(sorted(keep)) != tuple(keep) or len(set(keep)) != len(keep):
        raise ValueError("partial-trace keep indices must be ordered and unique")
    # Check the ordered metadata before creating the traced rows or any dense
    # intermediate. This is a pre-allocation guard, not a post-failure check.
    if state.shape[0] * state.shape[1] > max_dim:
        raise MemoryError(f"partial trace exceeds exact dimension budget: {state.shape}")
    keep = tuple(int(i) for i in keep)
    n_factors = len(dims) // 2
    if not keep or any(i < 0 or i >= n_factors for i in keep):
        raise ValueError("partial-trace index out of range")
    if len(keep) == n_factors:
        return state
    if n_factors != 2 or keep not in ((0,), (1,)):
        raise ValueError(
            "partial_trace is declared for two-factor joint states; keep must select one factor"
        )
    r_left, c_left, r_right, c_right = dims
    if keep == (0,):
        # Tr_R(L ⊗ R) = Tr(R) · L : out[i_L][a_L] = Σ_b J[i_L·r_R+b][a_L·c_R+b]
        trace_width = min(r_right, c_right)
        rows = tuple(
            tuple(
                sum(
                    (state.rows[i_left * r_right + b][a_left * c_right + b]
                     for b in range(trace_width)),
                    ZERO,
                )
                for a_left in range(c_left)
            )
            for i_left in range(r_left)
        )
        basis = state.subsystem_bases[0] if state.subsystem_bases else tuple(
            f"feature_{i}" for i in range(c_left)
        )
    else:
        # Tr_L(L ⊗ R) = Tr(L) · R : out[i_R][a_R] = Σ_b J[b·r_R+i_R][b·c_R+a_R]
        trace_width = min(r_left, c_left)
        rows = tuple(
            tuple(
                sum(
                    (state.rows[b * r_right + i_right][b * c_right + a_right]
                     for b in range(trace_width)),
                    ZERO,
                )
                for a_right in range(c_right)
            )
            for i_right in range(r_right)
        )
        basis = state.subsystem_bases[1] if len(state.subsystem_bases) > 1 else tuple(
            f"feature_{i}" for i in range(c_right)
        )
    schema = SchemaTag(tuple(basis))
    return TensorState(
        rows,
        tuple(basis),
        schema,
        hashlib.sha256(canonical_bytes_raw(rows, schema, "partial-trace")).hexdigest(),
    )


# ---------------------------------------------------------------------------
# §5 exact preprocessing and §9 exact metrics


def _exact_mean(values: Sequence[F4]) -> F4:
    total = sum(values, ZERO)
    return total / from_int(len(values))


def median_f(values: Sequence[F4]) -> F4:
    if not values:
        raise ValueError("median of empty exact column")
    if any(value.c != 0 or value.d != 0 for value in values):
        raise PlaneViolation("median_f is declared on the real channel only")
    from functools import cmp_to_key

    ordered = sorted(
        values, key=cmp_to_key(lambda left, right: (left - right).sign_sigma())
    )
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / from_int(2)


class TensorSimpleImputer:
    def __init__(self, strategy: str = "median"):
        if strategy not in {"median", "mean"}:
            raise ValueError("strategy must be median or mean")
        self.strategy = strategy

    def fit_exact(self, state: TensorState, missing: Sequence[Sequence[bool]] | None = None):
        mask = missing or [[False] * state.shape[1] for _ in state.rows]
        self.statistics_exact_ = []
        for col in range(state.shape[1]):
            observed = [row[col] for row, flags in zip(state.rows, mask) if not flags[col]]
            if not observed:
                raise ValueError("cannot impute an all-missing exact column")
            self.statistics_exact_.append(
                median_f(observed) if self.strategy == "median" else _exact_mean(observed)
            )
        self.n_features_in_ = state.shape[1]
        self.commit_ = commit(state, "impute:fit")
        return self

    def fit(self, X):
        state, mask = _state_and_missing(X)
        self.fit_exact(state, mask)
        self.statistics_ = np.asarray(
            [_diagnostic_scalar(v) for v in self.statistics_exact_], dtype=float
        )
        return self

    def transform_exact(self, state: TensorState, missing=None) -> TensorState:
        mask = missing or [[False] * state.shape[1] for _ in state.rows]
        rows = tuple(
            tuple(
                self.statistics_exact_[col] if flags[col] else value
                for col, value in enumerate(row)
            )
            for row, flags in zip(state.rows, mask)
        )
        return TensorState(
            rows,
            state.basis,
            state.schema,
            hashlib.sha256(canonical_bytes_raw(rows, state.schema, "impute:apply")).hexdigest(),
        )

    def transform(self, X):
        state, mask = _state_and_missing(X)
        exact = self.transform_exact(state, mask)
        return _diagnostic_matrix(exact)

    def fit_transform(self, X):
        return self.fit(X).transform(X)


MODE = "center_only"
TFIDF_MODE = "exact_linear"


def center_fit(state: TensorState) -> dict[str, Any]:
    means = tuple(_exact_mean([row[col] for row in state.rows]) for col in range(state.shape[1]))
    return {"mu": means, "commit": commit(state, "center:fit"), "mode": "center_only"}


def center_apply(state: TensorState, params: dict[str, Any]) -> TensorState:
    rows = tuple(
        tuple(value - params["mu"][col] for col, value in enumerate(row)) for row in state.rows
    )
    return TensorState(
        rows,
        state.basis,
        state.schema,
        hashlib.sha256(canonical_bytes_raw(rows, state.schema, "center:apply")).hexdigest(),
    )


def _sigma_min_max(values: Sequence[F4]) -> tuple[F4, F4]:
    def cmp(left: F4, right: F4) -> int:
        return (left - right).sign_sigma()

    from functools import cmp_to_key

    ordered = sorted(values, key=cmp_to_key(cmp))
    return ordered[0], ordered[-1]


def range_fit(state: TensorState) -> dict[str, Any]:
    bounds = [_sigma_min_max([row[col] for row in state.rows]) for col in range(state.shape[1])]
    low = tuple(pair[0] for pair in bounds)
    ranges = tuple(pair[1] - pair[0] for pair in bounds)
    if any(value == ZERO for value in ranges):
        raise ValueError("range preprocessing cannot encode constant columns")
    return {"lo": low, "rng": ranges, "commit": commit(state, "range:fit"), "mode": "range"}


def range_apply(state: TensorState, params: dict[str, Any]) -> TensorState:
    rows = tuple(
        tuple((value - params["lo"][col]) / params["rng"][col] for col, value in enumerate(row))
        for row in state.rows
    )
    return TensorState(
        rows,
        state.basis,
        state.schema,
        hashlib.sha256(canonical_bytes_raw(rows, state.schema, "range:apply")).hexdigest(),
    )


def zscore_fit_diagnostic(state: TensorState) -> DiagnosticValue:
    values = _diagnostic_matrix(state)
    means = values.mean(axis=0)
    scales = values.std(axis=0)
    scales[scales == 0.0] = 1.0
    return DiagnosticValue(
        {"mu": means, "sigma": scales},
        commit(state, "zscore:fit"),
    )


def zscore_apply_diagnostic(state: TensorState, params: DiagnosticValue) -> DiagnosticValue:
    if not isinstance(params, DiagnosticValue):
        raise PlaneViolation("diagnostic z-score requires diagnostic parameters")
    values = _diagnostic_matrix(state)
    return DiagnosticValue(
        (values - params.value["mu"]) / params.value["sigma"],
        params.provenance,
    )


def preprocess_exact(state: TensorState, mode: str = MODE):
    if mode == "center_only":
        params = center_fit(state)
        return center_apply(state, params), params
    if mode == "range":
        params = range_fit(state)
        return range_apply(state, params), params
    if mode == "diagnostic":
        params = zscore_fit_diagnostic(state)
        return zscore_apply_diagnostic(state, params), params
    raise ValueError(f"unknown tensor preprocessing mode: {mode}")


class TensorStandardScaler:
    """Legacy diagnostic z-score shim; exact training never uses it."""

    def fit_exact(self, state: TensorState):
        self.mean_exact_ = center_fit(state)["mu"]
        self.scale_exact_ = [ONE for _ in self.mean_exact_]
        self.scale_field_closed_ = False
        self.n_features_in_ = state.shape[1]
        self.commit_ = commit(state, "center:fit")
        return self

    def fit(self, X):
        values = _as_2d(X)
        if not np.isfinite(values).all():
            raise ValueError("exact tensor scaler rejects non-finite input")
        state = TensorState.from_values(values)
        self.fit_exact(state)
        self.mean_ = np.asarray([_diagnostic_scalar(v) for v in self.mean_exact_], dtype=float)
        self.scale_ = np.asarray(values.std(axis=0), dtype=float)
        self.scale_[self.scale_ == 0.0] = 1.0
        self.n_features_in_ = values.shape[1]
        return self

    def transform_exact(self, state: TensorState) -> TensorState:
        return center_apply(
            state,
            {"mu": tuple(self.mean_exact_), "commit": self.commit_, "mode": "center_only"},
        )

    def transform(self, X):
        values = _as_2d(X)
        if values.shape[1] != self.n_features_in_:
            raise ValueError(f"expected {self.n_features_in_} features, got {values.shape[1]}")
        if not np.isfinite(values).all():
            raise ValueError("exact tensor scaler rejects non-finite input")
        return (values - self.mean_) / self.scale_

    def fit_transform(self, X):
        return self.fit(X).transform(X)


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "with",
}


class TensorMatrix:
    def __init__(self, values, provenance: str = ""):
        self._values = np.asarray(values, dtype=float)
        self.provenance = provenance
        self.plane = Plane.DIAGNOSTIC

    @property
    def shape(self):
        return self._values.shape

    def toarray(self):
        return self._values.copy()

    def __array__(self, dtype=None):
        return np.asarray(self._values, dtype=dtype)


class TensorTfidfVectorizer:
    def __init__(self, max_features: int | None = None, stop_words=None, tfidf_mode=None):
        self.max_features = max_features
        self.stop_words = stop_words
        self.mode = tfidf_mode

    def _tokens(self, text: str) -> list[str]:
        tokens = [token.lower() for token in _TOKEN_RE.findall(str(text))]
        return [
            token for token in tokens if self.stop_words != "english" or token not in _STOP_WORDS
        ]

    def fit_exact(self, raw_documents: Iterable[str]):
        documents = [self._tokens(value) for value in raw_documents]
        counts: dict[str, int] = {}
        for tokens in documents:
            for token in set(tokens):
                counts[token] = counts.get(token, 0) + 1
        ordered = sorted(counts, key=lambda token: (-counts[token], token))
        if self.max_features is not None:
            ordered = ordered[: int(self.max_features)]
        self.vocabulary_ = {token: i for i, token in enumerate(ordered)}
        n_docs = max(len(documents), 1)
        self.n_documents_ = n_docs
        self.df_ = {token: counts[token] for token in ordered}
        self.idf_exact_ = {token: from_rat(n_docs, counts[token]) for token in ordered}
        self.fit_commit_ = hashlib.sha256(
            json.dumps({"vocab": ordered, "n": n_docs}, sort_keys=True).encode()
        ).hexdigest()
        return self

    def fit(self, raw_documents):
        self.fit_exact(raw_documents)
        self.idf_ = np.asarray(
            [_diagnostic_scalar(self.idf_exact_[token]) for token in self.vocabulary_], dtype=float
        )
        return self

    def transform_exact(self, raw_documents: Iterable[str]) -> TensorState:
        documents = [self._tokens(value) for value in raw_documents]
        rows = []
        for tokens in documents:
            counts: dict[str, int] = {}
            for token in tokens:
                if token in self.vocabulary_:
                    counts[token] = counts.get(token, 0) + 1
            total = max(len(tokens), 1)
            rows.append(
                tuple(
                    from_rat(count, total) * self.idf_exact_[token] if token in counts else ZERO
                    for token in self.vocabulary_
                    for count in [counts.get(token, 0)]
                )
            )
        return (
            TensorState.from_values(
                [[value for value in row] for row in rows], basis=list(self.vocabulary_)
            )
            if rows
            else TensorState.from_values([[]], basis=[])
        )

    def transform(self, raw_documents):
        mode = self.mode or TFIDF_MODE
        if mode == "exact_linear":
            exact = self.transform_exact(raw_documents)
            return TensorMatrix(_diagnostic_matrix(exact), commit(exact, "tfidf:exact"))
        if mode == "diagnostic_log":
            return self.transform_diagnostic(raw_documents)
        raise ValueError(f"unknown TFIDF_MODE: {mode}")

    def transform_diagnostic(self, raw_documents):
        documents = [self._tokens(value) for value in raw_documents]
        matrix = np.zeros((len(documents), len(self.vocabulary_)), dtype=float)
        idf = np.asarray(
            [np.log(float(self.n_documents_ / self.df_[token])) for token in self.vocabulary_],
            dtype=float,
        )
        for row, tokens in enumerate(documents):
            counts: dict[str, int] = {}
            for token in tokens:
                if token in self.vocabulary_:
                    counts[token] = counts.get(token, 0) + 1
            total = max(len(tokens), 1)
            for token, count in counts.items():
                matrix[row, self.vocabulary_[token]] = (count / total) * idf[
                    self.vocabulary_[token]
                ]
        exact = self.transform_exact(raw_documents)
        return TensorMatrix(matrix, commit(exact, "tfidf:diagnostic"))

    def fit_transform(self, raw_documents):
        documents = list(raw_documents)
        return self.fit(documents).transform(documents)


def tfidf_apply(vectorizer: TensorTfidfVectorizer, raw_documents):
    """Select the explicitly configured exact or diagnostic TF-IDF plane."""
    return vectorizer.transform(raw_documents)


class TensorSentimentAnalyzer:
    _POSITIVE = {"great", "good", "like", "love", "well", "excellent", "happy"}
    _NEGATIVE = {"bad", "hate", "difficult", "sucks", "leave", "poor", "sad"}

    def polarity_scores(self, text: str):
        tokens = [token.lower() for token in _TOKEN_RE.findall(str(text))]
        positive = sum(token in self._POSITIVE for token in tokens)
        negative = sum(token in self._NEGATIVE for token in tokens)
        total = positive + negative
        compound = 0.0 if total == 0 else (positive - negative) / total
        return {
            "neg": negative / max(len(tokens), 1),
            "neu": max(len(tokens) - total, 0) / max(len(tokens), 1),
            "pos": positive / max(len(tokens), 1),
            "compound": compound,
        }


def _diagnostic_scalar(value: F4) -> float:
    if value.c != 0 or value.d != 0:
        raise TypeError("expected a real F4 value")
    return float(value.a) + float(value.b) * float(np.sqrt(2.0))


def _diagnostic_matrix(state: TensorState) -> np.ndarray:
    return np.asarray(
        [[_diagnostic_scalar(value) for value in row] for row in state.rows], dtype=float
    )


def _state_and_missing(X):
    values = np.asarray(X, dtype=object)
    if values.ndim == 1:
        values = values.reshape(1, -1)
    if values.ndim != 2:
        raise ValueError("expected a 1D or 2D matrix")
    mask = []
    witness_rows = []
    for row in values.tolist():
        flags = []
        exact_row = []
        for value in row:
            missing = value is None or (
                isinstance(value, (float, np.floating)) and not np.isfinite(value)
            )
            flags.append(missing)
            exact_row.append(ZERO if missing else witness_scalar(value))
        witness_rows.append(exact_row)
        mask.append(flags)
    return TensorState.from_values(witness_rows), mask


def _as_2d(X) -> np.ndarray:
    # Field-channel boundary: dtype=float is the public ingress cast.
    # F4 channels b, c, and d stay zero after witness_scalar rebuilds
    # the rational channel from decimal text. See
    # docs/kellogg/exact_linear_field_audit.md.
    values = np.asarray(X, dtype=float)
    if values.ndim == 1:
        values = values.reshape(1, -1)
    if values.ndim != 2:
        raise ValueError("expected a 1D or 2D numeric matrix")
    return values


def _confusion(y_true, y_pred):
    truth, pred = np.asarray(y_true, dtype=int), np.asarray(y_pred, dtype=int)
    return {
        "TP": int(np.sum((truth == 1) & (pred == 1))),
        "FP": int(np.sum((truth == 0) & (pred == 1))),
        "TN": int(np.sum((truth == 0) & (pred == 0))),
        "FN": int(np.sum((truth == 1) & (pred == 0))),
    }


def exact_precision(y_true, y_pred) -> F4:
    C = _confusion(y_true, y_pred)
    return from_rat(C["TP"], C["TP"] + C["FP"]) if C["TP"] + C["FP"] else ZERO


def exact_recall(y_true, y_pred) -> F4:
    C = _confusion(y_true, y_pred)
    return from_rat(C["TP"], C["TP"] + C["FN"]) if C["TP"] + C["FN"] else ZERO


def exact_f1(y_true, y_pred) -> F4:
    precision, recall = exact_precision(y_true, y_pred), exact_recall(y_true, y_pred)
    return (
        (from_int(2) * precision * recall / (precision + recall))
        if precision != ZERO or recall != ZERO
        else ZERO
    )


def exact_accuracy(y_true, y_pred) -> F4:
    C = _confusion(y_true, y_pred)
    total = sum(C.values())
    return from_rat(C["TP"] + C["TN"], total) if total else ZERO


def precision_score(y_true, y_pred) -> float:
    return _diagnostic_scalar(exact_precision(y_true, y_pred))


def recall_score(y_true, y_pred) -> float:
    return _diagnostic_scalar(exact_recall(y_true, y_pred))


def f1_score(y_true, y_pred) -> float:
    return _diagnostic_scalar(exact_f1(y_true, y_pred))


def accuracy_score(y_true, y_pred) -> float:
    return _diagnostic_scalar(exact_accuracy(y_true, y_pred))


# ---------------------------------------------------------------------------
# §6 model core, §8 CV, §10 JSON persistence


class TensorClassifier:
    model_family = "tensor_linear"

    def __init__(self, **params):
        if "theorem_proven" in params:
            raise PlaneViolation(
                "theorem_proven is governance-derived and cannot be passed to __init__"
            )
        self.params = dict(params)
        self.tensor_backend = "mla1517_exact_tensor"
        self._governance_state = "unproven"
        self._proof_sha = None
        self.governance_events: list[dict[str, str]] = [
            {"event": "initialized", "state": "unproven"}
        ]
        self.exact = True
        self.name = self.model_family
        self.commit_log: list[tuple[str, str]] = []
        self.exact_tensor = ExactTOETensor(num_qubits=5)
        theorem_claim = self.params.get("theorem_claim")
        if theorem_claim is not None:
            governed = govern(theorem_claim)
            if governed.value.get("state") == "proven":
                self._governance_state = "proven"
                self._proof_sha = governed.value.get("proof_sha256")
                self.governance_events.append(
                    {"event": "proof_accepted", "state": "proven", "claim_id": theorem_claim}
                )

    def __setattr__(self, name, value):
        if name == "theorem_proven":
            raise PlaneViolation(
                "theorem_proven is read-only; use a checked proof or revoke_proof()"
            )
        object.__setattr__(self, name, value)

    @property
    def theorem_proven(self) -> bool:
        return self._governance_state == "proven"

    @theorem_proven.setter
    def theorem_proven(self, value: bool):
        raise PlaneViolation("theorem_proven is read-only; use a checked proof or revoke_proof()")

    @property
    def governance_state(self) -> str:
        return self._governance_state

    def revoke_proof(self, reason: str, actor: str) -> None:
        if not reason or not actor:
            raise ValueError("revocation requires a non-empty reason and actor")
        if self._governance_state == "unproven":
            raise PlaneViolation("cannot revoke an unproven model")
        if self._governance_state == "revoked":
            raise PlaneViolation("revocation is terminal and cannot be repeated")
        self._governance_state = "revoked"
        self._proof_sha = None
        self.governance_reason = reason
        self.governance_events.append(
            {
                "event": "proof_revoked",
                "state": "revoked",
                "reason": reason,
                "actor": actor,
            }
        )

    def get_params(self, deep=True):
        return dict(self.params)

    def _state(self, X):
        if isinstance(X, TensorState):
            return X
        return TensorState.from_values(_as_2d(X))

    def fit(self, X, y):
        """Fit the nearest-centroid threshold on binary labels.

        Field-channel note: exact_linear is declared to operate in F4 =
        Q(√2) + iQ(√2). The public fit path casts inputs through float
        before F4 construction, so only the rational channel a is
        populated. The √2 and imaginary channels are real but dormant
        unless the caller bypasses fit and supplies F4 coefficients
        directly. sign_sigma degenerates to integer comparison on the
        public path. 1+i raises PlaneViolation.

        Algorithm note: fit computes w = μ₁ − μ₀ and
        b = −w · ((μ₁ + μ₀)/2). It is a nearest-centroid classifier
        expressed as an exact linear threshold. It is not a forest,
        booster, or fitted regression. n_estimators, max_depth,
        learning_rate, random_state, and class_prior_exact_ are stored
        but never read by fit. rf, xgb, lgbm, gb construct this same
        object and warn. See docs/kellogg/exact_linear_algorithm_audit.md
        and docs/kellogg/exact_linear_field_audit.md.
        """
        values = _as_2d(X)
        labels = np.asarray(y, dtype=int).reshape(-1)
        if len(values) != len(labels) or len(values) == 0:
            raise ValueError("X and y must have equal non-zero lengths")
        if not set(np.unique(labels)).issubset({0, 1}):
            raise ValueError("tensor model requires binary labels")
        state = self._state(values)
        if state.is_joint:
            raise PlaneViolation("joint TensorState cannot enter the trainer")
        self.fit_state_ = state
        self.commit_log.append(("fit", commit(state, "fit")))
        self.preprocessing_mode = self.params.get("tensor_mode", MODE)
        processed, preprocessing = preprocess_exact(state, self.preprocessing_mode)
        self.preprocessing_ = preprocessing
        if isinstance(processed, DiagnosticValue):
            # Diagnostic mode is intentionally not an exact model.
            self.exact = False
            train_state = state
            self.preprocessing_commitment_ = preprocessing.provenance
        else:
            train_state = processed
            self.preprocessing_commitment_ = preprocessing["commit"]
        self.train_state_ = train_state
        self.commit_log.append(("preprocess", self.preprocessing_commitment_))
        self.classes_ = np.array([0, 1], dtype=int)
        self.n_features_in_ = train_state.shape[1]
        self.class_prior_exact_ = [
            from_rat(int(np.sum(labels == klass)), len(labels)) for klass in self.classes_
        ]
        means = []
        for klass in self.classes_:
            rows = [row for row, label in zip(train_state.rows, labels) if label == klass]
            means.append(
                tuple(
                    _exact_mean([row[col] for row in rows]) if rows else ZERO
                    for col in range(train_state.shape[1])
                )
            )
        self.centroids_exact_ = tuple(means)
        # Nearest-centroid threshold: w = μ₁ − μ₀ and
        # b = −w · ((μ₁ + μ₀)/2). n_estimators, max_depth,
        # learning_rate, random_state, and class_prior_exact_ are not
        # read here. See docs/kellogg/exact_linear_algorithm_audit.md.
        self.weights_exact_ = tuple(
            positive - negative for positive, negative in zip(means[1], means[0])
        )
        midpoint = tuple(
            (positive + negative) / from_int(2) for positive, negative in zip(means[1], means[0])
        )
        self.bias_exact_ = -sum(
            (weight * centre for weight, centre in zip(self.weights_exact_, midpoint)), ZERO
        )
        self.fit_tensor_commitment_ = commit(state, "fit")
        self.commit_log.append(("kernel", self.kernel_commitment()))
        self.feature_importances_ = self._measure_importances()
        return self

    def kernel_commitment(self) -> str:
        payload = json.dumps(
            {"w": [v.to_json() for v in self.weights_exact_], "b": self.bias_exact_.to_json()},
            sort_keys=True,
        ).encode()
        return hashlib.sha256(_tag("kernel") + payload).hexdigest()

    def _measure_importances(self):
        values = np.asarray(
            [abs(_diagnostic_scalar(value)) for value in self.weights_exact_], dtype=float
        )
        total = values.sum()
        return values / total if total else np.zeros_like(values)

    def _prepare_state(self, X):
        state = self._state(X)
        if state.shape[1] != self.n_features_in_:
            if state.shape[1] < self.n_features_in_:
                rows = tuple(
                    row + (ZERO,) * (self.n_features_in_ - state.shape[1]) for row in state.rows
                )
            else:
                rows = tuple(row[: self.n_features_in_] for row in state.rows)
            state = TensorState(
                rows,
                tuple(f"feature_{i}" for i in range(self.n_features_in_)),
                SchemaTag(tuple(f"feature_{i}" for i in range(self.n_features_in_))),
                state.identifier,
            )
        if self.preprocessing_mode == "center_only":
            state = center_apply(state, self.preprocessing_)
        elif self.preprocessing_mode == "range":
            state = range_apply(state, self.preprocessing_)
        elif self.preprocessing_mode == "diagnostic":
            # Diagnostic preprocessing cannot re-enter the exact model plane.
            self.exact = False
        return state

    def exact_scores(self, X) -> tuple[F4, ...]:
        raw_state = self._state(X)
        if raw_state.is_joint:
            raise PlaneViolation("joint TensorState cannot enter prediction")
        state = self._prepare_state(raw_state)
        self.last_predict_state_ = state
        self.last_predict_commitment_ = commit(state, "predict")
        self.last_tensor_commitments_ = [
            row_commit(row, state.schema, "predict") for row in state.rows
        ]
        self.commit_log.append(("predict", self.last_predict_commitment_))
        return tuple(
            sum((value * weight for value, weight in zip(row, self.weights_exact_)), ZERO)
            + self.bias_exact_
            for row in state.rows
        )

    def predict(self, X):
        """Return class 1 only when the exact score is strictly positive.

        Field-channel note: exact_linear is declared to operate in F4 =
        Q(√2) + iQ(√2). The public fit path casts inputs through float
        before F4 construction, so only the rational channel a is
        populated. The √2 and imaginary channels are real but dormant
        unless the caller bypasses fit and supplies F4 coefficients
        directly. sign_sigma degenerates to integer comparison on the
        public path. 1+i raises PlaneViolation.

        Algorithm note: fit computes w = μ₁ − μ₀ and
        b = −w · ((μ₁ + μ₀)/2). It is a nearest-centroid classifier
        expressed as an exact linear threshold. It is not a forest,
        booster, or fitted regression. n_estimators, max_depth,
        learning_rate, random_state, and class_prior_exact_ are stored
        but never read by fit. rf, xgb, lgbm, gb construct this same
        object and warn. See docs/kellogg/exact_linear_algorithm_audit.md
        and docs/kellogg/exact_linear_field_audit.md.
        """
        if getattr(self, "weights_exact_", None) is None:
            raise ValueError("tensor model is not fitted")
        try:
            return np.asarray(
                [1 if score.sign_sigma() > 0 else 0 for score in self.exact_scores(X)],
                dtype=int,
            )
        except TypeError as exc:
            raise PlaneViolation(
                "exact decision scores left the real channel; joint or complex inputs are not decidable"
            ) from exc

    def predict_proba(self, X):
        scores = self.exact_scores(X)
        measured = np.asarray([_diagnostic_scalar(score) for score in scores], dtype=float)
        # sigmoid is a measurement-only display map; it never re-enters F4.
        positive = 1.0 / (1.0 + np.exp(-measured))
        return np.column_stack((1.0 - positive, positive))

    def to_artifact(self):
        preprocessing = self.preprocessing_
        if isinstance(preprocessing, dict):
            serialized_preprocessing = {
                key: (
                    [value.to_json() for value in item]
                    if isinstance(item, tuple) and item and isinstance(item[0], F4)
                    else item
                )
                for key, item in preprocessing.items()
            }
        else:
            serialized_preprocessing = {
                "mode": "diagnostic",
                "provenance": preprocessing.provenance,
            }
        return {
            "schema": {
                "kellogg_schema": ARTIFACT_SCHEMA,
                "kellogg_version": _kellogg_version(),
                "substrate": SUBSTRATE_TAG,
                "field": FIELD_ID,
                "order": "sigma:real-then-imag",
            },
            "model": self.model_family,
            "params": self.params,
            "exact": self.exact,
            "n_features_in": self.n_features_in_,
            "preprocessing_mode": self.preprocessing_mode,
            "preprocessing": serialized_preprocessing,
            "weights": [value.to_json() for value in self.weights_exact_],
            "bias": self.bias_exact_.to_json(),
            "commits": self.commit_log,
            "theorem_proven": self.theorem_proven,
            "governance_state": self.governance_state,
            "proof_sha256": self._proof_sha,
            "governance_events": self.governance_events,
        }

    @classmethod
    def from_artifact(cls, artifact):
        expected = FIELD_ID
        schema = artifact.get("schema", {})
        # The lock is on the whole schema: format version, substrate and
        # declared field order are part of the artifact contract. An artifact
        # written under a different format, substrate or ordering must not
        # silently load.
        if "kellogg_schema" in schema:
            if schema.get("kellogg_schema") != ARTIFACT_SCHEMA:
                raise ValueError(
                    f"artifact format {schema.get('kellogg_schema')!r} is not "
                    f"{ARTIFACT_SCHEMA}; retrain or run an explicit migration"
                )
            if schema.get("substrate") != SUBSTRATE_TAG:
                raise ValueError(
                    f"artifact substrate {schema.get('substrate')!r} does not match "
                    f"the locked substrate {SUBSTRATE_TAG!r}"
                )
        else:
            if schema.get("toe_version") != TOE_VERSION:
                raise ValueError(
                    f"legacy artifact toe_version {schema.get('toe_version')!r} is not the "
                    f"readable legacy lock {TOE_VERSION}; retrain or run an explicit migration"
                )
            if schema.get("mla_version") != MLA1517_VERSION:
                raise ValueError(
                    f"legacy artifact substrate {schema.get('mla_version')!r} does not match "
                    f"the locked substrate {MLA1517_VERSION!r}"
                )
        if schema.get("order") != "sigma:real-then-imag":
            raise ValueError("artifact field order does not match the declared sigma order")
        if schema.get("field") != expected:
            raise ValueError("tensor artifact schema mismatch")
        model = cls(**artifact.get("params", {}))
        model.exact = bool(artifact.get("exact", False))
        model._governance_state = "unproven"
        model._proof_sha = None
        model.governance_events = list(artifact.get("governance_events", []))
        model.n_features_in_ = int(artifact["n_features_in"])
        if "preprocessing_mode" not in artifact or "preprocessing" not in artifact:
            raise ValueError("artifact lacks an explicit preprocessing mode; retrain is required")
        model.preprocessing_mode = artifact["preprocessing_mode"]
        if model.preprocessing_mode not in {"center_only", "range", "diagnostic"}:
            raise ValueError(f"unsupported stored preprocessing mode: {model.preprocessing_mode}")
        raw_preprocessing = artifact.get("preprocessing", {})
        if model.preprocessing_mode == "center_only":
            model.preprocessing_ = {
                "mu": tuple(F4.from_json(value) for value in raw_preprocessing["mu"]),
                "commit": raw_preprocessing.get("commit", ""),
                "mode": "center_only",
            }
        elif model.preprocessing_mode == "range":
            model.preprocessing_ = {
                "lo": tuple(F4.from_json(value) for value in raw_preprocessing["lo"]),
                "rng": tuple(F4.from_json(value) for value in raw_preprocessing["rng"]),
                "commit": raw_preprocessing.get("commit", ""),
                "mode": "range",
            }
        else:
            model.preprocessing_ = DiagnosticValue({}, raw_preprocessing.get("provenance", ""))
        model.weights_exact_ = tuple(F4.from_json(value) for value in artifact["weights"])
        model.bias_exact_ = F4.from_json(artifact["bias"])
        model.commit_log = [tuple(item) for item in artifact.get("commits", [])]
        model.feature_importances_ = model._measure_importances()
        model.fit_tensor_commitment_ = next(
            (value for domain, value in model.commit_log if domain == "fit"), ""
        )
        return model


class TensorRandomForestClassifier(TensorClassifier):
    model_family = "random_forest_contract"


class TensorGradientBoostingClassifier(TensorClassifier):
    model_family = "gradient_boosting_contract"


class TensorXGBClassifier(TensorClassifier):
    model_family = "xgboost_contract"


class TensorLGBMClassifier(TensorClassifier):
    model_family = "lightgbm_contract"


CANONICAL = "exact_linear"
_DEPRECATED = {"rf", "xgb", "lgbm", "gb"}
_warned_aliases: set[str] = set()


class TensorModelAPI(TensorClassifier):
    """The one canonical TOE model surface."""

    model_family = CANONICAL


def exact_linear(**kwargs) -> TensorModelAPI:
    """Return the canonical exact linear model.

    Field-channel note: exact_linear is declared to operate in F4 =
    Q(√2) + iQ(√2). The public fit path casts inputs through float
    before F4 construction, so only the rational channel a is
    populated. The √2 and imaginary channels are real but dormant
    unless the caller bypasses fit and supplies F4 coefficients
    directly. sign_sigma degenerates to integer comparison on the
    public path. 1+i raises PlaneViolation.

    Algorithm note: fit computes w = μ₁ − μ₀ and
    b = −w · ((μ₁ + μ₀)/2). It is a nearest-centroid classifier
    expressed as an exact linear threshold. It is not a forest,
    booster, or fitted regression. n_estimators, max_depth,
    learning_rate, random_state, and class_prior_exact_ are stored
    but never read by fit. rf, xgb, lgbm, gb construct this same
    object and warn. See docs/kellogg/exact_linear_algorithm_audit.md
    and docs/kellogg/exact_linear_field_audit.md.
    """
    return TensorModelAPI(**kwargs)


def _deprecated_alias(name: str):
    def make(**kwargs):
        if name not in _warned_aliases:
            warnings.warn(
                f"kellogg.{name}() is a deprecated alias for exact_linear(); "
                f"it does not implement the vendor algorithm of the same name. "
                "Migrate to kellogg.exact_linear(). Removal in v2.",
                DeprecationWarning,
                stacklevel=2,
            )
            _warned_aliases.add(name)
        return exact_linear(**kwargs)

    return make


rf = _deprecated_alias("rf")
xgb = _deprecated_alias("xgb")
lgbm = _deprecated_alias("lgbm")
gb = _deprecated_alias("gb")


def _clone(model):
    return model.__class__(**model.get_params())


@dataclass(frozen=True)
class Fold:
    train: TensorState
    test: TensorState
    tag: str
    train_indices: tuple[int, ...] = ()
    test_indices: tuple[int, ...] = ()


def joint_for_cv(state: TensorState, k: int, seed: F4 = ZERO) -> list[Fold]:
    """Bind fold membership and row identity without feeding a joint state to training."""
    if k < 2 or k > len(state.rows):
        raise ValueError("k must be between 2 and the number of rows")
    digest = hashlib.sha256(canonical_bytes(state, "cv-seed") + _tag(str(seed))).digest()
    order = sorted(
        range(len(state.rows)),
        key=lambda i: digest[i % len(digest)] ^ (i * 131 % 251),
    )
    folds: list[Fold] = []
    for fold_number, test in enumerate(np.array_split(np.asarray(order, dtype=int), k)):
        test_indices = tuple(int(i) for i in test.tolist())
        train_indices = tuple(i for i in order if i not in set(test_indices))
        test_state = state.subset(test_indices, f"cv:fold={fold_number}")
        folds.append(
            Fold(
                train=state.subset(train_indices, "cv:train"),
                test=test_state,
                tag=commit(test_state, f"cv:fold={fold_number}"),
                train_indices=train_indices,
                test_indices=test_indices,
            )
        )
    return folds


def kfold(state: TensorState, k: int, seed: F4 = ZERO):
    for fold in joint_for_cv(state, k, seed):
        yield fold


def tensor_cross_val_score(model, X, y, cv=3, scoring="f1"):
    if scoring != "f1":
        raise ValueError("tensor CV currently supports scoring='f1' only")
    values = _as_2d(X)
    labels = np.asarray(y, dtype=int)
    state = TensorState.from_values(values)
    scores = []
    for fold in joint_for_cv(state, int(cv), ZERO):
        # Indices are carried by the fold — never re-derived by row lookup,
        # so duplicate rows cannot leak across the train/test boundary.
        train_idx = list(fold.train_indices)
        test_idx = list(fold.test_indices)
        candidate = _clone(model).fit(values[train_idx], labels[train_idx])
        scores.append(f1_score(labels[test_idx], candidate.predict(values[test_idx])))
    return np.asarray(scores, dtype=float)


PROOF_DIR = Path(
    os.environ.get("KELLOGG_PROOF_DIR") or Path(__file__).resolve().parent.parent / "proofs"
)
PROOF_INDEX = PROOF_DIR / "index.json"


def _kellogg_version() -> str:
    import kellogg

    return getattr(kellogg, "__version__", "")


@dataclass(frozen=True)
class Proof:
    claim_id: str
    blob: bytes
    sha256: str


class ProofTamperedError(RuntimeError):
    """A proof artifact exists but does not match its indexed digest."""


def load_proof(claim_id: str) -> Proof | None:
    if not PROOF_INDEX.exists():
        return None
    try:
        index = json.loads(PROOF_INDEX.read_text(encoding="utf-8"))
        entry = index.get(claim_id)
        if not entry:
            return None
        path = PROOF_DIR / entry["path"]
        blob = path.read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        if digest != entry["sha256"]:
            raise ProofTamperedError(f"proof artifact digest mismatch for {claim_id}")
        return Proof(claim_id, blob, digest)
    except (OSError, KeyError, TypeError, ValueError):
        return None


def verify_artifact(proof: Proof) -> bool:
    """Minimal checked-artifact contract; domain-specific proof checkers plug in here."""
    try:
        document = json.loads(proof.blob.decode("utf-8"))
        return document.get("claim_id") == proof.claim_id and document.get("checked") is True
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return False


def govern(claim_id: str) -> GovernanceValue:
    proof = load_proof(claim_id)
    if proof is None:
        return GovernanceValue({"state": "unproven", "claim_id": claim_id})
    if not verify_artifact(proof):
        return GovernanceValue({"state": "unproven", "claim_id": claim_id, "reason": "bad_proof"})
    return GovernanceValue({"state": "proven", "claim_id": claim_id, "proof_sha256": proof.sha256})


def dump(obj, filename):
    if not isinstance(obj, TensorClassifier):
        raise TypeError("tensor persistence accepts TensorClassifier only")
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj.to_artifact(), sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )


def load(filename):
    path = Path(filename)
    raw = path.read_bytes()
    if raw.startswith(b"\x80"):
        raise ValueError("pickle/joblib artifacts are rejected; retrain in tensor JSON format")
    artifact = json.loads(raw.decode("utf-8"))
    classes = {
        "exact_linear": TensorModelAPI,
        "random_forest_contract": TensorModelAPI,
        "gradient_boosting_contract": TensorModelAPI,
        "xgboost_contract": TensorModelAPI,
        "lightgbm_contract": TensorModelAPI,
    }
    model_cls = classes.get(artifact.get("model"), TensorClassifier)
    return model_cls.from_artifact(artifact)


def save(model: TensorClassifier, path) -> None:
    """Canonical JSON persistence alias from the public specification."""
    dump(model, path)


def verify(model: TensorClassifier) -> GovernanceValue:
    """Recompute the authority commitments; this is checked, not proven."""
    try:
        if not isinstance(model, TensorClassifier):
            return GovernanceValue({"status": "unproven", "reason": "wrong_type"})
        expected_kernel = model.kernel_commitment()
        logged_kernel = next(
            (value for domain, value in model.commit_log if domain == "kernel"), None
        )
        if logged_kernel != expected_kernel:
            return GovernanceValue({"status": "unproven", "reason": "tamper"})
        return GovernanceValue(
            {
                "status": "checked",
                "theorem_proven": False,
                "commitments": len(model.commit_log),
            }
        )
    except Exception as exc:
        return GovernanceValue({"status": "unproven", "reason": str(exc)})


def fit(name: str, X, y, **params) -> TensorClassifier:
    """Fit exact_linear, or a deprecated alias of it, by name.

    Field-channel note: exact_linear is declared to operate in F4 =
    Q(√2) + iQ(√2). The public fit path casts inputs through float
    before F4 construction, so only the rational channel a is
    populated. The √2 and imaginary channels are real but dormant
    unless the caller bypasses fit and supplies F4 coefficients
    directly. sign_sigma degenerates to integer comparison on the
    public path. 1+i raises PlaneViolation.

    Algorithm note: fit computes w = μ₁ − μ₀ and
    b = −w · ((μ₁ + μ₀)/2). It is a nearest-centroid classifier
    expressed as an exact linear threshold. It is not a forest,
    booster, or fitted regression. n_estimators, max_depth,
    learning_rate, random_state, and class_prior_exact_ are stored
    but never read by fit. rf, xgb, lgbm, gb construct this same
    object and warn. See docs/kellogg/exact_linear_algorithm_audit.md
    and docs/kellogg/exact_linear_field_audit.md.
    """
    if name not in _DEPRECATED and name != CANONICAL:
        raise ValueError(f"Unknown model name: {name}")
    if name in _DEPRECATED:
        _deprecated_alias(name)(**params)
    return exact_linear(**params).fit(X, y)


def predict(model: TensorClassifier, X):
    """Predict with a fitted exact linear model.

    Field-channel note: exact_linear is declared to operate in F4 =
    Q(√2) + iQ(√2). The public fit path casts inputs through float
    before F4 construction, so only the rational channel a is
    populated. The √2 and imaginary channels are real but dormant
    unless the caller bypasses fit and supplies F4 coefficients
    directly. sign_sigma degenerates to integer comparison on the
    public path. 1+i raises PlaneViolation.

    Algorithm note: fit computes w = μ₁ − μ₀ and
    b = −w · ((μ₁ + μ₀)/2). It is a nearest-centroid classifier
    expressed as an exact linear threshold. It is not a forest,
    booster, or fitted regression. n_estimators, max_depth,
    learning_rate, random_state, and class_prior_exact_ are stored
    but never read by fit. rf, xgb, lgbm, gb construct this same
    object and warn. See docs/kellogg/exact_linear_algorithm_audit.md
    and docs/kellogg/exact_linear_field_audit.md.
    """
    return model.predict(X)


def predict_proba(model: TensorClassifier, X):
    return model.predict_proba(X)


# Public compatibility names expected by toe.engine.
# Vendor names are retained only as construction-compatible class aliases;
# the actual canonical model identity is always ``exact_linear``.
RandomForestClassifier = TensorModelAPI
GradientBoostingClassifier = TensorModelAPI
XGBClassifier = TensorModelAPI
LGBMClassifier = TensorModelAPI
StandardScaler = TensorStandardScaler
SimpleImputer = TensorSimpleImputer
TfidfVectorizer = TensorTfidfVectorizer
cross_val_score = tensor_cross_val_score

# Runtime belt-and-suspenders guard: the training module must not expose or
# import the field-only square-root helper.
if "sqrt_f" in globals():
    raise ImportError("sqrt_f is forbidden in the TOE training module")

__all__ = [
    "FIELD_ID",
    "ARTIFACT_SCHEMA",
    "MLA1517_VERSION",
    "SUBSTRATE_TAG",
    "TOE_VERSION",
    "F4",
    "Qsqrt2",
    "TensorState",
    "SchemaTag",
    "Plane",
    "PlaneViolation",
    "ExactValue",
    "DiagnosticValue",
    "GovernanceValue",
    "canonical_bytes",
    "commit",
    "merkle_root",
    "measure",
    "plane_multiply",
    "apply_unitary",
    "Unitary",
    "joint",
    "partial_trace",
    "center_fit",
    "center_apply",
    "range_fit",
    "range_apply",
    "zscore_fit_diagnostic",
    "zscore_apply_diagnostic",
    "preprocess_exact",
    "MODE",
    "TFIDF_MODE",
    "tfidf_apply",
    "from_int",
    "from_rat",
    "re_encode",
    "witness_scalar",
    "assert_exact",
    "median_f",
    "TensorStandardScaler",
    "TensorSimpleImputer",
    "TensorTfidfVectorizer",
    "TensorClassifier",
    "TensorModelAPI",
    "TensorRandomForestClassifier",
    "TensorGradientBoostingClassifier",
    "TensorXGBClassifier",
    "TensorLGBMClassifier",
    "TensorSentimentAnalyzer",
    "CANONICAL",
    "exact_linear",
    "rf",
    "xgb",
    "lgbm",
    "gb",
    "RandomForestClassifier",
    "GradientBoostingClassifier",
    "XGBClassifier",
    "LGBMClassifier",
    "StandardScaler",
    "SimpleImputer",
    "TfidfVectorizer",
    "cross_val_score",
    "exact_precision",
    "exact_recall",
    "exact_f1",
    "exact_accuracy",
    "precision_score",
    "recall_score",
    "f1_score",
    "accuracy_score",
    "dump",
    "load",
    "save",
    "verify",
    "Proof",
    "ProofTamperedError",
    "load_proof",
    "verify_artifact",
    "govern",
    "joint_for_cv",
    "Fold",
    "fit",
    "predict",
    "predict_proba",
]
