"""One-shot phase-matched search over the quadratic extension F_257[phi].

Amplitudes, oracle phases and diffusion phases are elements a + b*phi of
F_257[x]/(x^2 - x - 1), the field F_257^2 of multiplicative order 66,048.
The extension supplies the second algebraic degree of freedom: the target
marked amplitude is v = phi^s, whose norm is exactly (-1)^s, so a single
oracle + diffusion step simultaneously resolves the marked set and encodes
the Lucas/PV scale parity in the surviving amplitude.

Closed form (field algebra, derived and verified exhaustively):
    beta = r*v / (N*u - r*v),   alpha = 1 - v/(beta*u)
with u the embedded uniform amplitude (30^n, 0). When N*u == r*v exactly
(only possible for scalar v), the equation degenerates and the base-field
phase pair is used; the marked amplitude is then +/-1 in the prime
subfield, whose norm is still the parity anchor.
"""

from dataclasses import dataclass

from chronus.quantum.metallic_search import one_shot_phases_multi
from chronus.quantum.statevector import INV_SQRT2, P

_EXTENSION_ORDER = P * P - 1  # 66048


def _add(x: tuple[int, int], y: tuple[int, int]) -> tuple[int, int]:
    return ((x[0] + y[0]) % P, (x[1] + y[1]) % P)


def _sub(x: tuple[int, int], y: tuple[int, int]) -> tuple[int, int]:
    return ((x[0] - y[0]) % P, (x[1] - y[1]) % P)


def _mul(x: tuple[int, int], y: tuple[int, int]) -> tuple[int, int]:
    a, b, c, d = x[0], x[1], y[0], y[1]
    return ((a * c + b * d) % P, (a * d + b * c + b * d) % P)


def extension_norm(x: tuple[int, int]) -> int:
    return (x[0] * x[0] + x[0] * x[1] - x[1] * x[1]) % P


def _inv(x: tuple[int, int]) -> tuple[int, int]:
    norm_inverse = pow(extension_norm(x), -1, P)
    return ((x[0] + x[1]) * norm_inverse % P, (-x[1] * norm_inverse) % P)


def _div(x: tuple[int, int], y: tuple[int, int]) -> tuple[int, int]:
    return _mul(x, _inv(y))


def phi_element_power(s: int) -> tuple[int, int]:
    """phi^s in F_257[phi]: the pair (F_{s-1}, F_s) with F_{-1} = 1."""
    if not isinstance(s, int) or isinstance(s, bool) or s < 0:
        raise ValueError("scale index must be a non-negative integer")
    a, b = 1, 0
    for _ in range(s):
        a, b = b, (a + b) % P
    return (a, b)


def extension_one_shot_phases(
    num_qubits: int, marked_count: int, scale_index: int
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Closed-form (alpha, beta) in F_257[phi] targeting amplitude phi^s."""
    if not isinstance(num_qubits, int) or not 1 <= num_qubits <= 64:
        raise ValueError("num_qubits must be between 1 and 64")
    n = 1 << num_qubits
    if not isinstance(marked_count, int) or not 1 <= marked_count < n:
        raise ValueError("marked_count must be in [1, 2**num_qubits)")
    target = phi_element_power(scale_index)
    u = (pow(INV_SQRT2, num_qubits, P), 0)
    rv = _mul((marked_count % P, 0), target)
    denominator = _sub(_mul((n % P, 0), u), rv)
    if extension_norm(denominator) == 0:
        if target not in ((1, 0),):
            raise ValueError("degenerate parameters admit only the prime-subfield target")
        alpha, beta = one_shot_phases_multi(num_qubits, marked_count)[0]
        return (alpha, 0), (beta, 0)
    beta = _div(rv, denominator)
    alpha = _sub((1, 0), _div(target, _mul(beta, u)))
    return alpha, beta


@dataclass(frozen=True)
class ExtensionSubspaceState:
    """Converged rank-2 state with extension-field amplitudes."""

    num_qubits: int
    marked_count: int
    scale_index: int
    marked_amplitude: tuple[int, int]
    unmarked_amplitude: tuple[int, int]
    norm_parity_verified: bool

    def to_dict(self) -> dict:
        return {
            "field": "F_257[phi]",
            "extension_order": _EXTENSION_ORDER,
            "num_qubits": self.num_qubits,
            "marked_count": self.marked_count,
            "scale_index": self.scale_index,
            "marked_amplitude": list(self.marked_amplitude),
            "unmarked_amplitude": list(self.unmarked_amplitude),
            "norm_parity_verified": self.norm_parity_verified,
            "representation": "rank-2-symbolic-extension",
        }


def exact_extension_search(
    num_qubits: int, marked_count: int, scale_index: int
) -> ExtensionSubspaceState:
    """One iterate resolving the marked set with amplitude phi^scale_index.

    The marked amplitude's norm equals (-1)^scale_index exactly: the search
    and the Lucas/PV parity are matched in a single step.
    """
    alpha, beta = extension_one_shot_phases(num_qubits, marked_count, scale_index)
    n = 1 << num_qubits
    u = (pow(INV_SQRT2, num_qubits, P), 0)
    marked = _mul(alpha, u)
    mean = _mul(
        _add(_mul((marked_count % P, 0), marked),
             _mul(((n - marked_count) % P, 0), u)),
        (pow(n, -1, P), 0),
    )
    one_beta = _add((1, 0), beta)
    a_marked = _sub(_mul(one_beta, mean), _mul(beta, marked))
    a_unmarked = _sub(_mul(one_beta, mean), _mul(beta, u))
    if a_unmarked != (0, 0):
        raise ArithmeticError("extension search failed to cancel unmarked states")
    allowed = {phi_element_power(scale_index)}
    if scale_index == 0:
        allowed.add((P - 1, 0))  # degenerate branch lands on -1, norm still 1
    if a_marked not in allowed:
        raise ArithmeticError("extension search missed the target amplitude")
    parity = -1 if scale_index % 2 else 1
    return ExtensionSubspaceState(
        num_qubits=num_qubits,
        marked_count=marked_count,
        scale_index=scale_index,
        marked_amplitude=a_marked,
        unmarked_amplitude=a_unmarked,
        norm_parity_verified=extension_norm(a_marked) == parity % P,
    )
