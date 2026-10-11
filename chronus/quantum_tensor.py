"""Chronus quantum tensor substrate — first-principles quantum mathematics.

The substrate executes the quantum algebraic theses — superposition,
interference, unitarity, measurement and tensor composition — as exact
finite-dimensional linear algebra over the complex field. It is not married
to one execution backend.

Backend policy (owner specification):

* ``chronus-igpu`` (default) — the independent Chronus iGPU surface. On
  Apple silicon it executes on the Metal GPU through MLX (``complex64``);
  on hosts without an Apple iGPU the same independent surface executes on
  the NumPy ``complex128`` CPU lane. The independent surface is always
  available.
* ``auto`` — host-augmentation mode. The client may already have
  accelerators (CUDA GPU, Apple iGPU); auto probes them in order
  (CUDA -> Metal/MLX) and binds the first usable device, falling back to
  the independent surface.
* Explicit names — ``numpy``, ``mlx``, ``metal``, ``cupy``/``cuda`` — are
  fail-closed: an unavailable explicit request raises
  :class:`ChronusQuantumTensorUnavailable` instead of silently substituting
  another device.

Mathematics implemented:

* QuantumTensorState semantics via plain functions on state vectors:
  normalization, tensor (Kronecker) composition, Born probabilities,
  density operators, partial traces, von Neumann entropy, observable
  expectations ``Tr(rho M)`` / ``<psi|M|psi>``.
* Unitary evolution ``U = exp(-iHt/hbar)`` by eigendecomposition of
  Hermitian generators; every produced operator is audited for
  ``U^dagger U = I`` and rejected when the audit fails.
* Compute-dense transformations as CPTP Kraus maps
  ``E(rho) = sum K_m rho K_m^dagger`` with completeness verified, and
  measurements as POVMs ``{E_m >= 0, sum E_m = I}`` with Lueders
  post-measurement states.
* Hadamard tensor addition as linear combination of unitaries on an
  ancillary control register, returning both post-selection branches and
  their Born-rule success probabilities.
* Lossless left-canonical MPS/TT factorization by sequential SVD. Bond
  budgets are fail-closed: an over-budget request is refused rather than
  silently truncated.
* The Lucas ladder as the discrete spectrum of the substrate Hamiltonian
  ``H_L = hbar*omega (a^dagger a + 1/2) + V_Lucas`` with exact integer
  eigenvalues ``eps_n = L_n = phi^n + (-phi)^(-n)``; rung-to-rung scaling
  is the unitary squeeze evolution ``S(xi)``, ``|xi| = ln(L_n / L_m)``,
  inside a bounded Fock space whose level count is enforced.

Truth boundary: everything here is classical simulation of quantum
mathematics — deterministic finite-precision complex linear algebra on
whatever substrate executed it. Unitarity, positivity and completeness are
verified on the returned operators themselves; nothing in this module is a
quantum-hardware execution claim. Exact integer data (Lucas eigenvalues,
resonance rungs) stays exact; dynamical quantities are finite-precision.
"""

from __future__ import annotations

import math
import string
from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Sequence, Tuple

import numpy as np

from lucas.core import lucas as _exact_lucas
from lucas.ladder import SCALE_RUNGS as LUCAS_RESONANCE_RUNGS

__all__ = [
    "CLAIM_BOUNDARY",
    "ChronusQuantumTensorContractError",
    "ChronusQuantumTensorUnavailable",
    "LUCAS_RESONANCE_RUNGS",
    "LucasHamiltonian",
    "MPSFactorization",
    "MeasurementResult",
    "QuantumTensorProbe",
    "SuperpositionResult",
    "apply_kraus_channel",
    "apply_unitary",
    "basis_state",
    "born_probabilities",
    "density_from_state",
    "diagonal_phase_unitary",
    "diagonal_unitary",
    "expectation",
    "fock_ladder_operators",
    "global_phase_unitary",
    "hadamard_tensor_add",
    "kron_states",
    "lucas_eigenvalue",
    "lucas_hamiltonian",
    "lucas_scaling_squeeze",
    "measure_povm",
    "min_fock_levels",
    "mps_factorize",
    "mps_to_state",
    "normalize_state",
    "phase_scale",
    "probe_backends",
    "purity",
    "reduced_density_matrix",
    "resonance_stop",
    "resolve_backend",
    "squeeze_operator",
    "to_host",
    "uniform_state",
    "unitary_error",
    "unitary_operator",
    "unitary_scale",
    "validate_density",
    "validate_kraus",
    "validate_povm",
    "validate_unitary",
    "von_neumann_entropy",
]

CLAIM_BOUNDARY = (
    "finite-dimensional complex linear algebra on a classical substrate "
    "(numpy complex128 / mlx complex64 / cupy complex128); quantum theses "
    "are verified as mathematics on the returned operators — unitarity, "
    "positivity, completeness — never as quantum-hardware execution"
)

_COMPLEX64_TOL = 2e-4
_COMPLEX128_TOL = 1e-9


class ChronusQuantumTensorUnavailable(RuntimeError):
    """A requested execution lane cannot run on this host."""


class ChronusQuantumTensorContractError(ValueError):
    """Input data or a produced operator violated the quantum contract."""


# ---------------------------------------------------------------------------
# Backend resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuantumTensorProbe:
    """Observed availability of one quantum tensor execution lane."""

    backend: str
    available: bool
    device: str
    precision: str
    lane: str
    reason: str
    claim_boundary: str = CLAIM_BOUNDARY

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _Backend:
    """One resolved execution lane with a uniform linalg facade."""

    name: str
    lane: str
    device: str
    precision: str
    xp: Any
    dtype: Any
    gpu: bool
    eigh: Any
    eigvalsh: Any
    svd: Any

    def eval(self, a: Any) -> Any:
        if self.name == "mlx":
            self.xp.eval(a)
        return a

    def to_host(self, a: Any) -> np.ndarray:
        self.eval(a)
        return np.asarray(a)

    def scalar(self, a: Any) -> Any:
        self.eval(a)
        return a.item()

    def array(self, value: Any) -> Any:
        return self.xp.array(value, dtype=self.dtype)

    def eye(self, n: int) -> Any:
        return self.xp.eye(n, dtype=self.dtype)

    def zeros(self, shape: Sequence[int]) -> Any:
        return self.xp.zeros(tuple(shape), dtype=self.dtype)

    @property
    def tol(self) -> float:
        return _COMPLEX64_TOL if self.precision == "complex64" else _COMPLEX128_TOL


_MLX: Any = None
_MLX_FAILED = False


def _mlx_module() -> Any:
    global _MLX, _MLX_FAILED
    if _MLX is not None:
        return _MLX
    if _MLX_FAILED:
        raise ChronusQuantumTensorUnavailable("mlx import previously failed")
    try:
        import mlx.core as mx

        _MLX = mx
        return mx
    except Exception as exc:  # pragma: no cover - platform dependent
        _MLX_FAILED = True
        raise ChronusQuantumTensorUnavailable(
            f"MLX lane unavailable: {type(exc).__name__}: {exc}"
        ) from exc


def _numpy_backend(lane: str) -> _Backend:
    return _Backend(
        name="numpy",
        lane=lane,
        device="cpu",
        precision="complex128",
        xp=np,
        dtype=np.complex128,
        gpu=False,
        eigh=np.linalg.eigh,
        eigvalsh=np.linalg.eigvalsh,
        svd=lambda a: np.linalg.svd(a, full_matrices=False),
    )


def _mlx_backend(lane: str, *, require_gpu: bool) -> _Backend:
    mx = _mlx_module()
    device = str(mx.default_device())
    if require_gpu and "gpu" not in device.lower():
        raise ChronusQuantumTensorUnavailable(
            f"MLX is importable but the active device is not a GPU: {device}"
        )

    def _spectral(fn):
        def run(a):
            # MLX eigh/eigvalsh/svd execute on the CPU stream even when the
            # array lives on the GPU device; the result remains usable on
            # any stream after eval.
            with mx.stream(mx.cpu):
                out = fn(a)
                mx.eval(*out)
            return out

        return run

    return _Backend(
        name="mlx",
        lane=lane,
        device=f"mlx:{device}",
        precision="complex64",
        xp=mx,
        dtype=mx.complex64,
        gpu="gpu" in device.lower(),
        eigh=_spectral(mx.linalg.eigh),
        eigvalsh=_spectral(lambda a: (mx.linalg.eigvalsh(a),)),
        svd=_spectral(mx.linalg.svd),
    )


def _cupy_backend(lane: str) -> _Backend:
    try:
        from .native_tensor import _best_cuda_device, _cupy_property, _decode_device_name
        cp = __import__("cupy")
        index, props = _best_cuda_device(cp)
        cp.cuda.Device(index).use()
        name = _decode_device_name(_cupy_property(props, "name", f"cuda:{index}"))
    except ChronusQuantumTensorUnavailable:
        raise
    except Exception as exc:
        from .native_tensor import ChronusNativeTensorUnavailable

        if isinstance(exc, ChronusNativeTensorUnavailable):
            raise ChronusQuantumTensorUnavailable(str(exc)) from exc
        raise ChronusQuantumTensorUnavailable(
            f"CUDA lane unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    return _Backend(
        name="cupy",
        lane=lane,
        device=f"cuda:{index}:{name}",
        precision="complex128",
        xp=cp,
        dtype=cp.complex128,
        gpu=True,
        eigh=cp.linalg.eigh,
        eigvalsh=cp.linalg.eigvalsh,
        svd=lambda a: cp.linalg.svd(a, full_matrices=False),
    )


_BACKEND_CACHE: dict[str, _Backend] = {}
_BACKEND_NAMES = ("chronus-igpu", "auto", "numpy", "mlx", "metal", "cupy", "cuda")


def resolve_backend(backend: str = "chronus-igpu") -> _Backend:
    """Resolve an execution lane; explicit names fail closed."""
    key = str(backend or "chronus-igpu").strip().lower()
    if key in _BACKEND_CACHE:
        return _BACKEND_CACHE[key]
    built = _build_backend(key)
    _BACKEND_CACHE[key] = built
    return built


def _build_backend(key: str) -> _Backend:
    if key == "chronus-igpu":
        # The independent surface: Apple iGPU through MLX/Metal where that
        # silicon exists, else the same surface on the NumPy complex128 lane.
        import platform

        if platform.system() == "Darwin" and platform.machine() == "arm64":
            try:
                return _mlx_backend("chronus-igpu", require_gpu=True)
            except ChronusQuantumTensorUnavailable:
                pass
        return _numpy_backend("chronus-igpu")
    if key == "auto":
        # Host augmentation: bind the client's existing accelerators first.
        for builder in (lambda: _cupy_backend("augmentation"),
                        lambda: _mlx_backend("augmentation", require_gpu=True)):
            try:
                return builder()
            except ChronusQuantumTensorUnavailable:
                continue
        return _build_backend("chronus-igpu")
    if key == "numpy":
        return _numpy_backend("explicit")
    if key == "mlx":
        return _mlx_backend("explicit", require_gpu=False)
    if key == "metal":
        return _mlx_backend("explicit", require_gpu=True)
    if key in ("cupy", "cuda"):
        return _cupy_backend("explicit")
    raise ChronusQuantumTensorContractError(
        f"unknown quantum backend {key!r}; expected one of {list(_BACKEND_NAMES)}"
    )


def probe_backends() -> list[QuantumTensorProbe]:
    """Probe every named lane plus each policy surface."""
    probes: list[QuantumTensorProbe] = []
    for name in _BACKEND_NAMES:
        try:
            b = resolve_backend(name)
            probes.append(
                QuantumTensorProbe(
                    backend=name,
                    available=True,
                    device=b.device,
                    precision=b.precision,
                    lane=b.lane,
                    reason="",
                )
            )
        except Exception as exc:
            probes.append(
                QuantumTensorProbe(
                    backend=name,
                    available=False,
                    device="",
                    precision="",
                    lane="",
                    reason=f"{type(exc).__name__}: {exc}",
                )
            )
    return probes


def to_host(value: Any) -> np.ndarray:
    """Materialize any backend array (or array-like) as a host NumPy array."""
    if _MLX is not None and isinstance(value, _MLX.array):
        _MLX.eval(value)
    return np.asarray(value)


def _is_native(b: _Backend, value: Any) -> bool:
    if b.name == "mlx":
        return isinstance(value, b.xp.array)
    return isinstance(value, b.xp.ndarray)


def _to_backend(b: _Backend, value: Any) -> Any:
    if _is_native(b, value):
        return value if str(value.dtype) == b.precision else b.array(value)
    return b.array(to_host(value))


# ---------------------------------------------------------------------------
# Array helpers
# ---------------------------------------------------------------------------


def _dagger(xp: Any, a: Any) -> Any:
    return xp.swapaxes(xp.conj(a), -1, -2)


def _max_abs(b: _Backend, a: Any) -> float:
    return float(b.scalar(b.xp.max(b.xp.abs(a))))


def _check_finite(b: _Backend, a: Any, name: str) -> None:
    xp = b.xp
    ok = bool(b.scalar(xp.all(xp.isfinite(xp.real(a))))) and bool(
        b.scalar(xp.all(xp.isfinite(xp.imag(a))))
    )
    if not ok:
        raise ChronusQuantumTensorContractError(f"{name} contains non-finite values")


def _as_vector(b: _Backend, value: Any, name: str = "state") -> Any:
    a = b.xp.reshape(_to_backend(b, value), (-1,))
    _check_finite(b, a, name)
    if int(a.shape[0]) < 1:
        raise ChronusQuantumTensorContractError(f"{name} must contain at least one amplitude")
    return a


def _as_matrix(b: _Backend, value: Any, name: str, *, square: bool = True) -> Any:
    a = _to_backend(b, value)
    if len(a.shape) != 2 or (square and int(a.shape[0]) != int(a.shape[1])):
        raise ChronusQuantumTensorContractError(
            f"{name} must be a {'square ' if square else ''}matrix, got shape {tuple(a.shape)}"
        )
    _check_finite(b, a, name)
    return a


def _as_dims(dims: Sequence[int]) -> tuple[int, ...]:
    try:
        out = tuple(int(d) for d in dims)
    except (TypeError, ValueError):
        raise ChronusQuantumTensorContractError(
            f"subsystem dims must be positive integers, got {dims!r}"
        ) from None
    if not out or any(d < 1 for d in out):
        raise ChronusQuantumTensorContractError(
            f"subsystem dims must be positive integers, got {dims!r}"
        )
    if len(out) > 26:
        raise ChronusQuantumTensorContractError("subsystem count exceeds einsum label space (26)")
    return out


def _prod(dims: Sequence[int]) -> int:
    n = 1
    for d in dims:
        n *= int(d)
    return n


def _hermitian_error(b: _Backend, a: Any) -> float:
    return _max_abs(b, a - _dagger(b.xp, a))


def _require_hermitian(b: _Backend, a: Any, atol: float, name: str) -> None:
    err = _hermitian_error(b, a)
    if err > atol:
        raise ChronusQuantumTensorContractError(
            f"{name} is not Hermitian: ||{name} - {name}^dagger||_max = {err:.3e} > {atol:.1e}"
        )


def unitary_error(U: Any, backend: str = "chronus-igpu") -> float:
    """||U U^dagger - I||_max — zero for an exact unitary."""
    b = resolve_backend(backend)
    u = _as_matrix(b, U, "unitary")
    return _max_abs(b, u @ _dagger(b.xp, u) - b.eye(int(u.shape[0])))


def _require_unitary(b: _Backend, u: Any, atol: float, name: str) -> None:
    err = unitary_error(u, b.name) if b.name in _BACKEND_CACHE else _max_abs(
        b, u @ _dagger(b.xp, u) - b.eye(int(u.shape[0]))
    )
    if err > atol:
        raise ChronusQuantumTensorContractError(
            f"{name} is not unitary: ||{name} {name}^dagger - I||_max = {err:.3e} > {atol:.1e}"
        )


def validate_unitary(U: Any, atol: Optional[float] = None, backend: str = "chronus-igpu") -> bool:
    """True iff ``U`` satisfies the unitary contract within ``atol``; raises otherwise."""
    b = resolve_backend(backend)
    u = _as_matrix(b, U, "unitary")
    _require_unitary(b, u, atol if atol is not None else 10 * b.tol, "unitary")
    return True


def validate_density(rho: Any, atol: Optional[float] = None, backend: str = "chronus-igpu") -> bool:
    """True iff ``rho`` is Hermitian, PSD and unit trace; raises otherwise."""
    b = resolve_backend(backend)
    r = _as_matrix(b, rho, "rho")
    tol = atol if atol is not None else 10 * b.tol
    _require_hermitian(b, r, tol, "rho")
    tr = complex(b.scalar(b.xp.trace(r)))
    if abs(tr - 1.0) > tol:
        raise ChronusQuantumTensorContractError(
            f"rho must have unit trace, got Tr(rho) = {tr}"
        )
    w = to_host(b.eigvalsh(r))
    lowest = float(np.min(np.real(w)))
    if lowest < -tol:
        raise ChronusQuantumTensorContractError(
            f"rho is not positive semidefinite: min eigenvalue {lowest:.3e} < {-tol:.1e}"
        )
    return True


# ---------------------------------------------------------------------------
# States, density operators, measurement
# ---------------------------------------------------------------------------


def normalize_state(state: Any, backend: str = "chronus-igpu") -> Any:
    """Return ``state`` scaled to unit L2 norm; rejects zero/non-finite input."""
    b = resolve_backend(backend)
    v = _as_vector(b, state)
    n = float(b.scalar(b.xp.linalg.norm(v)))
    if not math.isfinite(n) or n <= 0.0:
        raise ChronusQuantumTensorContractError(
            "cannot normalize a zero or degenerate state vector"
        )
    return v / n


def basis_state(dims: Sequence[int] | int, index: int = 0, backend: str = "chronus-igpu") -> Any:
    """Computational-basis state ``|index>`` in the product space of ``dims``."""
    b = resolve_backend(backend)
    if isinstance(dims, int):
        dims = (dims,)
    shape = _as_dims(dims)
    size = _prod(shape)
    i = int(index)
    if not 0 <= i < size:
        raise ChronusQuantumTensorContractError(
            f"basis index {index} out of range for dimension {size}"
        )
    amps = [0j] * size
    amps[i] = 1.0 + 0.0j
    return b.array(amps)


def uniform_state(dims: Sequence[int] | int, backend: str = "chronus-igpu") -> Any:
    """Equal-amplitude superposition over the full product basis."""
    b = resolve_backend(backend)
    if isinstance(dims, int):
        dims = (dims,)
    size = _prod(_as_dims(dims))
    amp = 1.0 / math.sqrt(size)
    return b.array([amp + 0.0j] * size)


def kron_states(state_a: Any, state_b: Any, backend: str = "chronus-igpu") -> Any:
    """Tensor composition ``|a> (x) |b>`` of two normalized states."""
    b = resolve_backend(backend)
    return b.xp.kron(_as_vector(b, state_a, "state_a"), _as_vector(b, state_b, "state_b"))


def density_from_state(state: Any, backend: str = "chronus-igpu") -> Any:
    """Pure-state density operator ``|psi><psi|``."""
    b = resolve_backend(backend)
    v = normalize_state(state, b.name)
    return b.xp.einsum("i,j->ij", v, b.xp.conj(v))


def born_probabilities(state: Any, backend: str = "chronus-igpu") -> Any:
    """Born rule: ``p_k = |alpha_k|^2`` for the normalized ray."""
    b = resolve_backend(backend)
    v = normalize_state(state, b.name)
    return b.xp.abs(v) ** 2


def reduced_density_matrix(
    state: Any,
    subsystem_dims: Sequence[int],
    keep: Sequence[int],
    backend: str = "chronus-igpu",
) -> Any:
    """Partial trace ``rho_keep = Tr_complement(|psi><psi|)``.

    ``subsystem_dims`` gives the local Hilbert-space dimensions; ``keep``
    lists the subsystem indices retained. Computed directly from the state
    tensor — the full density operator is never materialized.
    """
    b = resolve_backend(backend)
    dims = _as_dims(subsystem_dims)
    d = len(dims)
    keep_set = sorted({int(k) for k in keep})
    if not keep_set or any(k < 0 or k >= d for k in keep_set):
        raise ChronusQuantumTensorContractError(
            f"keep must be non-empty indices into {d} subsystems, got {list(keep)!r}"
        )
    v = normalize_state(state, b.name)
    if int(v.shape[0]) != _prod(dims):
        raise ChronusQuantumTensorContractError(
            f"state dimension {int(v.shape[0])} does not match product of subsystem dims {_prod(dims)}"
        )
    letters = string.ascii_letters
    left = list(letters[:d])
    fresh = letters[d : d + len(keep_set)]
    right = list(left)  # traced subsystems share the left label -> summed
    for pos, k in enumerate(keep_set):
        right[k] = fresh[pos]
    out = "".join(left[k] for k in keep_set) + "".join(fresh)
    psi_t = b.xp.reshape(v, dims)
    rho_t = b.xp.einsum(
        f"{''.join(left)},{''.join(right)}->{out}", psi_t, b.xp.conj(psi_t)
    )
    rd = _prod([dims[k] for k in keep_set])
    return b.xp.reshape(rho_t, (rd, rd))


def von_neumann_entropy(
    rho: Any, base: float = 2.0, backend: str = "chronus-igpu"
) -> float:
    """``S(rho) = -Tr(rho log rho)`` in the requested log base.

    Eigenvalues at or below the zero threshold obey the ``0 log 0 = 0``
    convention — they are skipped rather than evaluated, so pure states
    yield exactly 0 without NaN leakage.
    """
    b = resolve_backend(backend)
    r = _as_matrix(b, rho, "rho")
    tr = complex(b.scalar(b.xp.trace(r)))
    if abs(tr - 1.0) > 10 * b.tol:
        raise ChronusQuantumTensorContractError(
            f"entropy requires a unit-trace density matrix, got Tr(rho) = {tr}"
        )
    w = np.real(to_host(b.eigvalsh(r)))
    zero_tol = max(10 * b.tol, 1e-7)
    log_base = math.log(base)
    s = 0.0
    for lam in w:
        if lam > zero_tol:
            s -= float(lam) * math.log(float(lam)) / log_base
        elif lam < -zero_tol:
            raise ChronusQuantumTensorContractError(
                f"rho is not positive semidefinite: eigenvalue {float(lam):.3e}"
            )
    return float(s)


def purity(rho: Any, backend: str = "chronus-igpu") -> float:
    """``Tr(rho^2)`` — 1 for pure states, ``1/d`` for the maximally mixed state."""
    b = resolve_backend(backend)
    r = _as_matrix(b, rho, "rho")
    return float(np.real(complex(b.scalar(b.xp.trace(r @ r)))))


def expectation(state_or_rho: Any, observable: Any, backend: str = "chronus-igpu") -> Any:
    """``<psi|M|psi>`` for a state vector or ``Tr(rho M)`` for a density matrix.

    Returns a real float when the imaginary residue is negligible, else a
    complex value — Hermitian observables always land on the real branch.
    """
    b = resolve_backend(backend)
    m = _as_matrix(b, observable, "observable")
    n = int(m.shape[0])
    arg = _to_backend(b, state_or_rho)
    if len(arg.shape) == 1:
        psi = normalize_state(arg, b.name)
        if int(psi.shape[0]) != n:
            raise ChronusQuantumTensorContractError(
                f"observable dimension {n} disagrees with state dimension {int(psi.shape[0])}"
            )
        val = b.xp.sum(b.xp.conj(psi) * (m @ psi))
    else:
        r = _as_matrix(b, state_or_rho, "rho")
        if int(r.shape[0]) != n:
            raise ChronusQuantumTensorContractError(
                f"observable dimension {n} disagrees with rho dimension {int(r.shape[0])}"
            )
        val = b.xp.trace(r @ m)
    c = complex(b.scalar(val))
    if abs(c.imag) <= 1e-5 * max(1.0, abs(c.real)):
        return float(c.real)
    return c


# ---------------------------------------------------------------------------
# Unitary evolution
# ---------------------------------------------------------------------------


def _unitary_from_eigendecomposition(b: _Backend, w: Any, V: Any, phase: Any) -> Any:
    U = (V * phase) @ _dagger(b.xp, V)
    err = _max_abs(b, U @ _dagger(b.xp, U) - b.eye(int(U.shape[0])))
    if err > 10 * b.tol:
        raise ChronusQuantumTensorContractError(
            f"produced operator failed the unitary audit: ||U U^dagger - I||_max = {err:.3e}"
        )
    return U


def unitary_operator(
    hamiltonian: Any,
    time: float,
    hbar: float = 1.0,
    backend: str = "chronus-igpu",
) -> Any:
    """``U = exp(-i H t / hbar)`` for Hermitian ``H``, audited ``U U^dagger = I``."""
    b = resolve_backend(backend)
    H = _as_matrix(b, hamiltonian, "hamiltonian")
    _require_hermitian(b, H, 10 * b.tol, "hamiltonian")
    w, V = b.eigh(H)
    phase = b.xp.exp(w * (-1j * (float(time) / float(hbar))))
    return _unitary_from_eigendecomposition(b, w, V, phase)


def unitary_scale(
    hamiltonian: Any,
    state: Any,
    time: float,
    hbar: float = 1.0,
    backend: str = "chronus-igpu",
) -> Any:
    """Evolve ``state``: returns ``exp(-iHt/hbar) |psi>``."""
    b = resolve_backend(backend)
    U = unitary_operator(hamiltonian, time, hbar=hbar, backend=b.name)
    v = normalize_state(state, b.name)
    return U @ v


def apply_unitary(U: Any, state: Any, backend: str = "chronus-igpu") -> Any:
    """Apply a caller-supplied unitary after verifying ``U U^dagger = I``."""
    b = resolve_backend(backend)
    u = _as_matrix(b, U, "unitary")
    _require_unitary(b, u, 10 * b.tol, "unitary")
    v = normalize_state(state, b.name)
    if int(v.shape[0]) != int(u.shape[0]):
        raise ChronusQuantumTensorContractError(
            f"unitary dimension {int(u.shape[0])} disagrees with state dimension {int(v.shape[0])}"
        )
    return u @ v


def phase_scale(state: Any, alpha: complex, backend: str = "chronus-igpu") -> Any:
    """Multiply the ray by a unit-modulus scalar ``alpha = e^{i theta}``.

    Any other modulus is refused: real amplitude scaling is not a channel
    on normalized states — the ray is invariant and the norm contract
    would silently absorb it. Use :func:`hadamard_tensor_add` or a Kraus
    map when a non-unitary map is actually intended.
    """
    a = complex(alpha)
    if abs(abs(a) - 1.0) > 1e-5:
        raise ChronusQuantumTensorContractError(
            f"phase_scale requires |alpha| = 1, got |alpha| = {abs(a):.6g}; "
            "non-unitary amplitude scaling is not a physical operation on normalized states"
        )
    b = resolve_backend(backend)
    return normalize_state(state, b.name) * a


def global_phase_unitary(theta: float, dim: int, backend: str = "chronus-igpu") -> Any:
    """``exp(-i theta) I`` — the uniform-driver evolution e^{-i omega_0 t} I."""
    b = resolve_backend(backend)
    return b.eye(int(dim)) * complex(np.exp(-1j * float(theta)))


def diagonal_phase_unitary(angles: Sequence[float], backend: str = "chronus-igpu") -> Any:
    """``diag(e^{i theta_j})`` — per-basis-state phase shifts."""
    b = resolve_backend(backend)
    phasors = [complex(np.exp(1j * float(t))) for t in angles]
    return b.xp.diag(b.array(phasors))


def diagonal_unitary(phasors: Sequence[complex], backend: str = "chronus-igpu") -> Any:
    """``diag(z_j)`` requiring ``|z_j| = 1`` for every entry."""
    b = resolve_backend(backend)
    zs = [complex(z) for z in phasors]
    bad = [z for z in zs if abs(abs(z) - 1.0) > 1e-5]
    if bad:
        raise ChronusQuantumTensorContractError(
            f"diagonal unitary requires unit-modulus entries, got {bad[:3]}"
        )
    return b.xp.diag(b.array(zs))


def hadamard_tensor_add(state_a: Any, state_b: Any, backend: str = "chronus-igpu") -> "SuperpositionResult":
    """Coherent addition on an ancillary control qubit.

    Builds ``(|0>|psi> + |1>|phi>) / sqrt(2)``, applies ``H (x) I``, and
    returns both measurement branches: ancilla ``|0>`` carries
    ``(|psi>+|phi>)/2`` (the sum, success probability ``p_plus``) and
    ancilla ``|1>`` carries ``(|psi>-|phi>)/2``. For normalized inputs
    ``p_plus = (1 + Re<psi|phi>) / 2``.
    """
    b = resolve_backend(backend)
    psi = normalize_state(state_a, b.name)
    phi = normalize_state(state_b, b.name)
    if int(psi.shape[0]) != int(phi.shape[0]):
        raise ChronusQuantumTensorContractError(
            "hadamard add requires equal state dimensions"
        )
    plus = (psi + phi) / 2.0
    minus = (psi - phi) / 2.0
    p_plus = float(b.scalar(b.xp.sum(b.xp.abs(plus) ** 2)))
    p_minus = float(b.scalar(b.xp.sum(b.xp.abs(minus) ** 2)))
    plus_state = plus / math.sqrt(p_plus) if p_plus > b.tol else None
    minus_state = minus / math.sqrt(p_minus) if p_minus > b.tol else None
    return SuperpositionResult(
        plus_state=plus_state,
        minus_state=minus_state,
        plus_unnormalized=plus,
        minus_unnormalized=minus,
        p_plus=p_plus,
        p_minus=p_minus,
        backend=b.name,
    )


@dataclass(frozen=True)
class SuperpositionResult:
    """Both branches of the ancillary-control addition."""

    plus_state: Any
    minus_state: Any
    plus_unnormalized: Any
    minus_unnormalized: Any
    p_plus: float
    p_minus: float
    backend: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "p_plus": self.p_plus,
            "p_minus": self.p_minus,
            "plus_resolved": self.plus_state is not None,
            "minus_resolved": self.minus_state is not None,
            "backend": self.backend,
            "claim_boundary": CLAIM_BOUNDARY,
        }


# ---------------------------------------------------------------------------
# Channels and POVM measurement
# ---------------------------------------------------------------------------


def validate_kraus(
    kraus_ops: Sequence[Any],
    atol: Optional[float] = None,
    backend: str = "chronus-igpu",
) -> float:
    """Return the completeness defect ``||sum K^dagger K - I||_max``; raise if it exceeds ``atol``."""
    b = resolve_backend(backend)
    ops = [_as_matrix(b, k, f"kraus[{i}]") for i, k in enumerate(kraus_ops)]
    if not ops:
        raise ChronusQuantumTensorContractError("a Kraus channel needs at least one operator")
    n = int(ops[0].shape[0])
    if any(int(k.shape[0]) != n for k in ops):
        raise ChronusQuantumTensorContractError("Kraus operators must share one dimension")
    acc = b.zeros((n, n))
    for k in ops:
        acc = acc + _dagger(b.xp, k) @ k
    err = _max_abs(b, acc - b.eye(n))
    tol = atol if atol is not None else 10 * b.tol
    if err > tol:
        raise ChronusQuantumTensorContractError(
            f"Kraus completeness violated: ||sum K^dagger K - I||_max = {err:.3e} > {tol:.1e}"
        )
    return err


def apply_kraus_channel(
    rho: Any,
    kraus_ops: Sequence[Any],
    atol: Optional[float] = None,
    backend: str = "chronus-igpu",
) -> Any:
    """CPTP map ``E(rho) = sum K_m rho K_m^dagger`` — completeness is verified first."""
    b = resolve_backend(backend)
    ops = [_as_matrix(b, k, f"kraus[{i}]") for i, k in enumerate(kraus_ops)]
    validate_kraus(ops, atol=atol, backend=b.name)
    r = _as_matrix(b, rho, "rho")
    if int(r.shape[0]) != int(ops[0].shape[0]):
        raise ChronusQuantumTensorContractError(
            "Kraus operator dimension disagrees with rho"
        )
    out = b.zeros(tuple(r.shape))
    for k in ops:
        out = out + k @ r @ _dagger(b.xp, k)
    tr = abs(complex(b.scalar(b.xp.trace(out))) - 1.0)
    if tr > 10 * b.tol:
        raise ChronusQuantumTensorContractError(
            f"channel output lost trace: |Tr(E(rho)) - 1| = {tr:.3e}"
        )
    return out


def validate_povm(
    effects: Sequence[Any],
    atol: float = 1e-5,
    backend: str = "chronus-igpu",
) -> bool:
    """True iff every effect is Hermitian PSD and ``sum E_m = I``; raises otherwise."""
    b = resolve_backend(backend)
    ops = [_as_matrix(b, e, f"effect[{i}]") for i, e in enumerate(effects)]
    if not ops:
        raise ChronusQuantumTensorContractError("a POVM needs at least one effect")
    n = int(ops[0].shape[0])
    total = b.zeros((n, n))
    for i, e in enumerate(ops):
        if int(e.shape[0]) != n:
            raise ChronusQuantumTensorContractError(
                f"effect[{i}] dimension {int(e.shape[0])} disagrees with {n}"
            )
        herr = _hermitian_error(b, e)
        if herr > atol:
            raise ChronusQuantumTensorContractError(
                f"effect[{i}] is not Hermitian: ||E - E^dagger||_max = {herr:.3e}"
            )
        lowest = float(np.min(np.real(to_host(b.eigvalsh(e)))))
        if lowest < -atol:
            raise ChronusQuantumTensorContractError(
                f"effect[{i}] is not positive semidefinite: min eigenvalue {lowest:.3e}"
            )
        total = total + e
    err = _max_abs(b, total - b.eye(n))
    if err > atol:
        raise ChronusQuantumTensorContractError(
            f"POVM completeness violated: ||sum E_m - I||_max = {err:.3e} > {atol:.1e}"
        )
    return True


def _matrix_sqrt(b: _Backend, a: Any) -> Any:
    w, V = b.eigh(a)
    wl = np.maximum(np.real(to_host(w)), 0.0)
    D = b.xp.diag(b.array(np.sqrt(wl).astype(np.complex128)))
    return V @ D @ _dagger(b.xp, V)


@dataclass(frozen=True)
class MeasurementResult:
    """Born-rule outcome probabilities and Lueders post-measurement states."""

    probabilities: tuple[float, ...]
    post_states: tuple[Any, ...]
    backend: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "probabilities": list(self.probabilities),
            "post_state_count": sum(1 for s in self.post_states if s is not None),
            "backend": self.backend,
            "claim_boundary": CLAIM_BOUNDARY,
        }


def measure_povm(
    system: Any,
    effects: Sequence[Any],
    backend: str = "chronus-igpu",
) -> MeasurementResult:
    """POVM measurement: ``p_m = <psi|E|psi>`` or ``Tr(E rho)``.

    Post-measurement states use the Lueders instrument ``K_m = E_m^{1/2}``:
    ``psi' = K psi / sqrt(p)`` or ``rho' = K rho K / p``. Outcomes with
    negligible probability carry ``None`` as their post state.
    """
    b = resolve_backend(backend)
    ops = [_as_matrix(b, e, f"effect[{i}]") for i, e in enumerate(effects)]
    validate_povm(ops, backend=b.name)
    arg = _to_backend(b, system)
    probs: list[float] = []
    posts: list[Any] = []
    if len(arg.shape) == 1:
        psi = normalize_state(arg, b.name)
        for e in ops:
            p = float(np.real(complex(b.scalar(b.xp.sum(b.xp.conj(psi) * (e @ psi))))))
            p = max(p, 0.0)
            probs.append(p)
            if p > b.tol:
                K = _matrix_sqrt(b, e)
                posts.append((K @ psi) / math.sqrt(p))
            else:
                posts.append(None)
    else:
        r = _as_matrix(b, arg, "rho")
        for e in ops:
            p = float(np.real(complex(b.scalar(b.xp.trace(e @ r)))))
            p = max(p, 0.0)
            probs.append(p)
            if p > b.tol:
                K = _matrix_sqrt(b, e)
                posts.append(K @ r @ K / p)
            else:
                posts.append(None)
    return MeasurementResult(tuple(probs), tuple(posts), b.name)


# ---------------------------------------------------------------------------
# Lossless MPS/TT factorization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MPSFactorization:
    """A left-canonical matrix-product factorization of a state tensor.

    ``tensors[k]`` has shape ``(bond_left, n_k, bond_right)`` and satisfies
    the isometry contract ``sum_i A^k[i]^dagger A^k[i] = I``. Bond
    dimensions are the Schmidt ranks; ``entanglement_entropies`` are the
    von Neumann entropies of each successive bipartition cut.
    """

    dims: tuple[int, ...]
    tensors: tuple[Any, ...]
    singular_values: tuple[Any, ...]
    bond_dims: tuple[int, ...]
    entanglement_entropies: tuple[float, ...]
    isometry_error: float
    reconstruction_error: float
    lossless: bool
    backend: str
    claim_boundary: str = CLAIM_BOUNDARY

    def as_dict(self) -> dict[str, Any]:
        return {
            "dims": list(self.dims),
            "bond_dims": list(self.bond_dims),
            "entanglement_entropies": list(self.entanglement_entropies),
            "isometry_error": self.isometry_error,
            "reconstruction_error": self.reconstruction_error,
            "lossless": self.lossless,
            "backend": self.backend,
            "claim_boundary": self.claim_boundary,
        }


def _entropy_of_singular_values(b: _Backend, s: Any) -> float:
    p = np.real(to_host(s)) ** 2
    p = p / max(p.sum(), 1e-300)
    return float(-np.sum(p[p > 1e-15] * np.log2(p[p > 1e-15])))


def mps_factorize(
    state: Any,
    dims: Sequence[int],
    max_bond: Optional[int] = None,
    sv_tol: Optional[float] = None,
    backend: str = "chronus-igpu",
) -> MPSFactorization:
    """Sequential-SVD factorization ``C = A^1 l_1 A^2 l_2 ... A^d`` (lossless).

    Every kept singular value is retained; truncation is never silent — a
    required bond dimension above ``max_bond`` is refused with a stated
    reason rather than approximated.
    """
    b = resolve_backend(backend)
    shape = _as_dims(dims)
    d = len(shape)
    v = normalize_state(state, b.name)
    if int(v.shape[0]) != _prod(shape):
        raise ChronusQuantumTensorContractError(
            f"state dimension {int(v.shape[0])} does not match product of dims {_prod(shape)}"
        )
    svd_cut = sv_tol if sv_tol is not None else b.tol
    tensors: list[Any] = []
    sigmas: list[Any] = []
    bond_dims: list[int] = []
    entropies: list[float] = []
    current = v
    bond_left = 1
    for k in range(d - 1):
        nk = shape[k]
        M = b.xp.reshape(current, (bond_left * nk, -1))
        U, s, Vt = b.svd(M)
        sv = np.real(to_host(s))
        s0 = float(sv[0]) if sv.size else 0.0
        rank = int(np.sum(sv > svd_cut * max(s0, 1e-300))) or 1
        if max_bond is not None and rank > int(max_bond):
            raise ChronusQuantumTensorContractError(
                f"bond dimension {rank} required at cut {k} exceeds max_bond {max_bond}; "
                "refused rather than silently truncated"
            )
        U_r = U[:, :rank]
        s_r = s[:rank]
        Vt_r = Vt[:rank, :]
        tensors.append(b.xp.reshape(U_r, (bond_left, nk, rank)))
        sigmas.append(s_r)
        bond_dims.append(rank)
        entropies.append(_entropy_of_singular_values(b, s_r))
        current = b.xp.reshape(s_r, (-1, 1)) * Vt_r
        bond_left = rank
    tensors.append(b.xp.reshape(current, (bond_left, shape[-1], 1)))

    iso_err = 0.0
    for k, t in enumerate(tensors[:-1]):
        r = int(t.shape[-1])
        m2 = b.xp.reshape(t, (-1, r))
        iso_err = max(iso_err, _max_abs(b, _dagger(b.xp, m2) @ m2 - b.eye(r)))
    mps = MPSFactorization(
        dims=shape,
        tensors=tuple(tensors),
        singular_values=tuple(sigmas),
        bond_dims=tuple(bond_dims),
        entanglement_entropies=tuple(entropies),
        isometry_error=float(iso_err),
        reconstruction_error=0.0,
        lossless=True,
        backend=b.name,
    )
    rebuilt = mps_to_state(mps, backend=b.name)
    recon = _max_abs(b, b.xp.reshape(rebuilt, (-1,)) - v)
    return MPSFactorization(
        dims=shape,
        tensors=tuple(tensors),
        singular_values=tuple(sigmas),
        bond_dims=tuple(bond_dims),
        entanglement_entropies=tuple(entropies),
        isometry_error=float(iso_err),
        reconstruction_error=float(recon),
        lossless=bool(recon <= 10 * b.tol),
        backend=b.name,
    )


def mps_to_state(mps: MPSFactorization, backend: str = "chronus-igpu") -> Any:
    """Contract the tensor chain back to a normalized flat state vector."""
    b = resolve_backend(backend)
    acc = mps.tensors[0]
    for t in mps.tensors[1:]:
        acc = b.xp.tensordot(acc, t, axes=([-1], [0]))
    flat = b.xp.reshape(acc, (-1,))
    return flat / b.xp.linalg.norm(flat)


# ---------------------------------------------------------------------------
# Lucas spectrum: H_L, Fock ladder, squeeze evolution
# ---------------------------------------------------------------------------


def resonance_stop(n: int) -> int:
    """Exact Lucas eigenvalue ``eps_n = L_n`` at rung ``n``."""
    return _exact_lucas(int(n))


def lucas_eigenvalue(n: int) -> int:
    return _exact_lucas(int(n))


@dataclass(frozen=True)
class LucasHamiltonian:
    """The Lucas quantization Hamiltonian ``H_L = H_0 + V_Lucas``.

    ``eigenvalues_exact`` carries the exact integers ``L_n``; the matrix
    entries are backend floats, exactly representable only while
    ``matrix_exact`` is true (``L_n < 2^24`` for complex64, ``< 2^53``
    for complex128).
    """

    hamiltonian: Any
    driver: Any
    potential: Any
    eigenvalues_exact: tuple[int, ...]
    n_levels: int
    hbar_omega: float
    matrix_exact: bool
    backend: str
    claim_boundary: str = CLAIM_BOUNDARY

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_levels": self.n_levels,
            "hbar_omega": self.hbar_omega,
            "eigenvalues_exact": list(self.eigenvalues_exact),
            "matrix_exact": self.matrix_exact,
            "backend": self.backend,
            "claim_boundary": self.claim_boundary,
        }


def lucas_hamiltonian(
    n_levels: int,
    hbar_omega: float = 1.0,
    backend: str = "chronus-igpu",
) -> LucasHamiltonian:
    """Diagonal ``H_L`` with spectrum ``eps_n = L_n = phi^n + (-phi)^{-n}``."""
    b = resolve_backend(backend)
    n = int(n_levels)
    if n < 1:
        raise ChronusQuantumTensorContractError("lucas_hamiltonian needs n_levels >= 1")
    eps = [_exact_lucas(k) for k in range(n)]
    hw = float(hbar_omega)
    hl = np.diag(np.asarray(eps, dtype=np.complex128))
    h0 = np.diag((np.arange(n) + 0.5) * hw).astype(np.complex128)
    H_L = b.array(hl)
    H_0 = b.array(h0)
    V = H_L - H_0
    limit = (1 << 24) if b.precision == "complex64" else (1 << 53)
    return LucasHamiltonian(
        hamiltonian=H_L,
        driver=H_0,
        potential=V,
        eigenvalues_exact=tuple(eps),
        n_levels=n,
        hbar_omega=hw,
        matrix_exact=bool(eps[-1] < limit),
        backend=b.name,
    )


def fock_ladder_operators(n_levels: int, backend: str = "chronus-igpu") -> tuple[Any, Any]:
    """Truncated Fock-space ladder operators ``a`` and ``a^dagger``."""
    b = resolve_backend(backend)
    n = int(n_levels)
    if n < 2:
        raise ChronusQuantumTensorContractError("fock ladder needs n_levels >= 2")
    a = np.zeros((n, n), dtype=np.complex128)
    for k in range(1, n):
        a[k - 1, k] = math.sqrt(k)
    A = b.array(a)
    return A, _dagger(b.xp, A)


def min_fock_levels(xi_magnitude: float) -> int:
    """Fock levels required before ``sinh^2|xi|`` photons stay inside the space."""
    return int(math.ceil(4.0 * math.sinh(abs(float(xi_magnitude))) ** 2)) + 16


def _antihermitian_exp(b: _Backend, G: Any) -> Any:
    """``exp(G)`` for anti-Hermitian ``G`` via the Hermitian generator ``iG``."""
    H = G * 1j
    w, V = b.eigh(H)
    phase = b.xp.exp(w * (-1j))
    return _unitary_from_eigendecomposition(b, w, V, phase)


def squeeze_operator(
    xi: complex,
    n_levels: int,
    backend: str = "chronus-igpu",
) -> Any:
    """``S(xi) = exp(1/2 (xi* a^2 - xi a^dagger^2))`` in a bounded Fock space.

    The Fock bound is enforced: ``sinh^2|xi|`` mean photons must fit the
    truncated ladder, otherwise the evolution leaks amplitude past the top
    level and the request is refused with the required level count.
    """
    b = resolve_backend(backend)
    x = complex(xi)
    n = int(n_levels)
    need = min_fock_levels(abs(x))
    if n < need:
        raise ChronusQuantumTensorContractError(
            f"squeezing |xi| = {abs(x):.4g} needs >= {need} Fock levels "
            f"(sinh^2|xi| = {math.sinh(abs(x)) ** 2:.4g}); got {n}"
        )
    a, adag = fock_ladder_operators(n, backend=b.name)
    G = 0.5 * (complex(np.conj(x)) * (a @ a) - x * (adag @ adag))
    return _antihermitian_exp(b, G)


def lucas_scaling_squeeze(
    source_index: int,
    target_index: int,
    n_levels: int,
    backend: str = "chronus-igpu",
) -> Any:
    """Rung-to-rung squeeze ``|xi| = ln(L_target / L_source)``."""
    ln, lm = _exact_lucas(int(target_index)), _exact_lucas(int(source_index))
    if ln <= 0 or lm <= 0:
        raise ChronusQuantumTensorContractError(
            f"Lucas rungs must be positive: L_{source_index} = {lm}, L_{target_index} = {ln}"
        )
    xi = math.log(ln / lm)
    return squeeze_operator(xi, n_levels, backend=backend)
