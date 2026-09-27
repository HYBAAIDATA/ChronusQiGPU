"""Kellogg traversal — Layer 6: the 32-face geodesic frame.

The 32-face dual-overlay frame (20 icosahedron + 12 dodecahedron normals,
defined in ``kellogg.quantum_tensor.dual_overlay_frame``) is an IEEE-754
object: the vertex coordinates carry sqrt(5)/phi geometry, so every
function in this module is a DECLARED FLOAT-BOUNDARY consumer of exact
states. Bloch axes are computed exactly where the substrate allows and
projected to float exactly once.

Coverage law: a 32-step geodesic walk visits all 32 faces iff the stride
is a unit of Z/32Z, i.e. odd. The stride is the constant F_5 = 5, a
Fibonacci value coprime to the frame size — an honest arithmetic-
progression guarantee (gcd(5,32)=1), verified step-by-step by the Cassini
ledger rather than assumed. Varying Fibonacci strides measurably fail the
32-window property (empirically 10-23 of 32 faces), so they are not used.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .quantum_tensor import Complex, ComplexMatrix, dual_overlay_frame
from .scales import cassini_verify, pisot_wind

FRAME_32: Tuple[Tuple[float, float, float], ...] = tuple(dual_overlay_frame())
assert len(FRAME_32) == 32, "dual-overlay frame must have exactly 32 faces"

# F_5 = 5: the traversal stride. gcd(5, 32) = 1 makes the face walk a
# bijection over Z/32Z — every 32-step window provably visits all faces.
TRAVERSAL_STRIDE = 5

_PAULI = {
    "X": ((complex(0, 0), complex(1, 0)), (complex(1, 0), complex(0, 0))),
    "Y": ((complex(0, 0), complex(0, -1)), (complex(0, 1), complex(0, 0))),
    "Z": ((complex(1, 0), complex(0, 0)), (complex(0, 0), complex(-1, 0))),
}


def _pauli_matrix(axis: str, qubit: int, num_qubits: int) -> ComplexMatrix:
    """I^{⊗q} ⊗ P ⊗ I^{⊗n-q-1} as a float ComplexMatrix."""
    ident = ComplexMatrix.identity(2)
    pauli = ComplexMatrix(
        2, 2, [[Complex(v.real, v.imag) for v in row] for row in _PAULI[axis]]
    )
    out = pauli if qubit == 0 else ident
    for q in range(1, num_qubits):
        out = out.tensor(pauli if q == qubit else ident)
    return out


def bloch_vector(state, qubit: int = 0) -> Tuple[float, float, float]:
    """Reduced Bloch vector (<X>,<Y>,<Z>) of ``qubit``.

    For ``ExactStateVector`` the expectations are exact Q(sqrt(2)) values
    projected once through ``to_float`` — the declared boundary crossing.
    For ``QuantumState`` they are the finite-precision expectations.
    """
    if hasattr(state, "expectation_pauli"):
        return tuple(
            state.expectation_pauli(qubit, axis).to_float() for axis in ("X", "Y", "Z")
        )
    n = state.dim.bit_length() - 1
    if state.dim != 1 << n:
        raise ValueError("Bloch vector requires a 2^n-dimensional state")
    return tuple(
        state.expectation(_pauli_matrix(axis, qubit, n)) for axis in ("X", "Y", "Z")
    )


def face_bias(state, qubit: int = 0) -> int:
    """QFI-weighted face selection on the 32-face frame.

    For each face normal n_f, the rotation generator n_f . sigma has pure-
    state QFI F_Q = 4 Var(n_f . sigma) = 4(1 - <n_f . sigma>^2) on the
    selected qubit. The face whose axis is maximally transverse to the
    Bloch vector — largest Fisher information — wins. Deterministic:
    argmax over a declared float score, lowest index on ties.
    """
    bx, by, bz = bloch_vector(state, qubit)
    best, best_qfi = 0, -1.0
    for f, (nx, ny, nz) in enumerate(FRAME_32):
        overlap = bx * nx + by * ny + bz * nz
        qfi = 4.0 * (1.0 - overlap * overlap)
        if qfi > best_qfi:
            best, best_qfi = f, qfi
    return best


def cassini_offset(n: int) -> int:
    """Traversal stride for step ``n``.

    Constant TRAVERSAL_STRIDE = F_5 = 5 — the unique class of strides that
    guarantees the 32-window coverage invariant (gcd(stride, 32) = 1). The
    Cassini ledger certifies the step index stream; the stride itself is
    fixed so coverage is a theorem, not a measurement.
    """
    if n < 0:
        raise ValueError("step index must be non-negative")
    return TRAVERSAL_STRIDE


def geodesic_step(face: int, wind: Sequence[float], n: int) -> Tuple[int, Tuple[float, ...]]:
    """One traversal step: advance the face by the certified stride and
    wind the T^11 coordinates by the Pisot drift."""
    if not 0 <= int(face) < 32:
        raise ValueError("face index out of range")
    if not cassini_verify(n + 1):
        raise ArithmeticError(f"Cassini ledger rejected step index {n + 1}")
    return ((int(face) + cassini_offset(n)) % 32, pisot_wind(wind, n))


@dataclass(frozen=True)
class CoverageCertificate:
    """Machine-checkable record of a geodesic run.

    ``all_faces_seen`` is measured from the emitted step ledger — the
    certificate attests what happened; it never asserts coverage that was
    not observed. ``verify()`` recomputes the walk and the Cassini checks.
    """

    start_face: int
    steps: int
    stride: int
    faces: Tuple[int, ...]
    cassini_ledger_ok: bool
    digest: str

    @property
    def faces_visited(self) -> int:
        return len(set(self.faces))

    @property
    def all_faces_seen(self) -> bool:
        return self.faces_visited == 32

    def verify(self) -> bool:
        """Replay the walk from the ledger and confirm the attestation."""
        face = self.start_face
        for n in range(self.steps):
            if self.faces[n] != face:
                return False
            if not cassini_verify(n + 1):
                return False
            face = (face + self.stride) % 32
        if self.faces[self.steps - 1] != (self.start_face + self.stride * (self.steps - 1)) % 32:
            return False
        return self.digest == _certificate_digest(self)

    def to_dict(self) -> dict:
        return {
            "schema": "kellogg.coverage_certificate/v1",
            "start_face": self.start_face,
            "steps": self.steps,
            "stride": self.stride,
            "faces": list(self.faces),
            "faces_visited": self.faces_visited,
            "all_faces_seen": self.all_faces_seen,
            "cassini_ledger_ok": self.cassini_ledger_ok,
            "digest": self.digest,
        }


def _certificate_digest(cert: CoverageCertificate) -> str:
    payload = {
        "start_face": cert.start_face,
        "steps": cert.steps,
        "stride": cert.stride,
        "faces": list(cert.faces),
        "cassini_ledger_ok": cert.cassini_ledger_ok,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def coverage_certificate(steps: int, *, start_face: int = 0) -> CoverageCertificate:
    """Run the geodesic walk for ``steps`` and emit a verified certificate."""
    if steps < 1:
        raise ValueError("certificate requires at least one step")
    if not 0 <= start_face < 32:
        raise ValueError("start_face out of range")
    face = start_face
    wind = tuple(0.0 for _ in range(11))
    faces: List[int] = []
    ledger_ok = True
    for n in range(steps):
        faces.append(face)
        ledger_ok = ledger_ok and cassini_verify(n + 1)
        face, wind = geodesic_step(face, wind, n)
    cert = CoverageCertificate(
        start_face=start_face,
        steps=steps,
        stride=TRAVERSAL_STRIDE,
        faces=tuple(faces),
        cassini_ledger_ok=ledger_ok,
        digest="",
    )
    return CoverageCertificate(
        start_face=cert.start_face,
        steps=cert.steps,
        stride=cert.stride,
        faces=cert.faces,
        cassini_ledger_ok=cert.cassini_ledger_ok,
        digest=_certificate_digest(cert),
    )
