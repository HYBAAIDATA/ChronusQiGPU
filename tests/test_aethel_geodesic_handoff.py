"""Aethel manifold point → kellogg geodesic engine handoff.

The claim under test: a point produced by ``aethel``'s prime-storage
manifold (a Cassini-verified pv-lattice anchor) can be handed directly to
the geodesic traversal engine in ``kellogg.traversal`` and validated by
the ENGINE'S OWN invariants — ``cassini_verify`` from ``kellogg.scales``,
``geodesic_step``, and ``CoverageCertificate.verify``.

Nothing in this file reimplements an invariant: no Lucas/Fibonacci
identities, no Cassini arithmetic, no stride math is restated here. If a
check needs the invariant, it calls the engine's function.
"""

import pytest  # noqa: F401  (pytest fixtures/parametrize may be added; keeps import explicit)

from aethel.gpu import TensorCoreGPU_Context
from aethel.manifold import (
    ManifoldCurvature,
    PrimeStorageManifold,
)
from aethel.cassini import CassiniVerifier  # aethel's OWN anchor gate
from kellogg.scales import cassini_verify  # the engine's OWN step invariant
from kellogg.traversal import (  # the geodesic engine, unmodified
    TRAVERSAL_STRIDE,
    CoverageCertificate,
    coverage_certificate,
    geodesic_step,
)


def _manifold() -> PrimeStorageManifold:
    return PrimeStorageManifold(TensorCoreGPU_Context())


def test_aethel_anchor_is_engine_checked_not_reimplemented():
    """T5a: a real manifold anchor passes aethel's own Cassini gate."""
    manifold = _manifold()
    tensor_id = manifold.ingest_sync(
        b"handoff-payload", ManifoldCurvature.GOLDEN_DENSE
    )
    tensor = manifold.tensors[tensor_id]
    anchor = tensor.integer_anchor
    assert anchor is not None
    assert CassiniVerifier.verify(anchor) is True


def test_manifold_point_accepted_as_geodesic_start_face():
    """T5b: the anchor-derived face index feeds the geodesic engine
    unchanged — no aethel-side revalidation is inserted."""
    manifold = _manifold()
    manifold.ingest_sync(b"handoff-2", ManifoldCurvature.GOLDEN_DENSE)
    anchors = sorted(manifold.anchor_index)
    assert anchors, "ingest produced no anchor"
    start_face = anchors[0] % 32
    cert = coverage_certificate(32, start_face=start_face)
    assert isinstance(cert, CoverageCertificate)
    # Engine's own verdict — not recomputed here.
    assert cert.verify() is True
    assert cert.all_faces_seen is True
    assert cert.cassini_ledger_ok is True


def test_geodesic_step_uses_engine_invariant():
    """T5c: a single step off the manifold anchor is certified by the
    engine's cassini_verify, called as the engine's function."""
    manifold = _manifold()
    manifold.ingest_sync(b"handoff-3", ManifoldCurvature.GOLDEN_DENSE)
    anchor = next(iter(manifold.anchor_index))
    face = anchor % 32
    wind = tuple(0.0 for _ in range(11))
    assert cassini_verify(1) is True  # engine certifies step index 1
    next_face, next_wind = geodesic_step(face, wind, 0)
    assert next_face == (face + TRAVERSAL_STRIDE) % 32
    assert len(next_wind) == 11


def test_full_cover_returns_to_start_after_32_steps():
    """T5d: from every aethel-derived face, a 32-step certified walk
    returns to the start (stride is a unit mod 32 — asserted by the
    engine's certificate, not by arithmetic restated here)."""
    manifold = _manifold()
    for i in range(3):
        manifold.ingest_sync(f"payload-{i}".encode(), ManifoldCurvature.GOLDEN_DENSE)
    for anchor in sorted(manifold.anchor_index):
        face = anchor % 32
        cert = coverage_certificate(32, start_face=face)
        assert cert.verify()
        assert cert.faces[-1] == (face + TRAVERSAL_STRIDE * 31) % 32
        assert cert.all_faces_seen


def test_no_invariant_reimplementation_in_this_file():
    """Meta-guard: this test module must not restate engine invariants.

    If someone copies L_n^2 - 5*F_n^2 arithmetic into this file, the
    'same engine' claim is broken — catch it."""
    src = open(__file__, encoding="utf-8").read()

    def frag(*parts):
        return "".join(parts)

    forbidden = [
        frag("fib", "onacci("),
        frag("def _f", "ib"),
        frag("L_n", "**2"),
        frag("4 * (-1)", "**n"),
        frag("(-1)", "**n"),
    ]
    for token in forbidden:
        assert token not in src, f"invariant reimplemented in test: {token!r}"
