"""D2 — the discrete-to-continuous functor, with honest names.

The consortium demand: Yang-Mills mass gap is a spectral property of an
SU(N) Hamiltonian on 4D spacetime; Navier-Stokes needs a differentiable
L2 field. *Produce the exact functor* from discrete cyber-events into
the continuous claims — or stop borrowing the vocabulary.

This module is that functor, stated precisely. None of its objects are
the continuum theorems:

* **Events -> graph**: each event's feature vector is quantized to a
  vertex on a discrete torus ``Z_L x Z_L``; observed transitions become
  weighted edges. This is the *base space*.

* **Discrete U(1) connection**: vertex ``v`` carries a phase
  ``theta(v) = arg`` of its embedded position; each directed edge
  carries the link variable ``U_e = exp(i * (theta(v) - theta(u)))`` —
  a lattice gauge field. The curl of the connection around a unit
  square (plaquette) is the field strength ``F_p``, a discrete Wilson
  loop. This is the *fiber bundle*: a trivial U(1) principal bundle
  over the event graph.

* **Finite-volume mass gap**: the second eigenvalue ``lambda_2`` of the
  graph Laplacian ``L = D - W`` — the rigorous discrete analogue of a
  spectral gap. It is *not* the continuum SU(N) mass gap and the report
  says so; it is the gap of *this* finite operator on *this* finite
  geometry.

* **Linear confinement analogue**: escape cost
  ``lambda_2 * dist(src, dst)`` — linear in graph distance, matching
  the blueprint's ``cost = lyap * mass_gap * d`` formula with the gap
  computed rather than assumed.

* **Navier-Stokes analogue**: the event stream deposits momentum onto
  the grid, giving a discrete velocity field ``u``. We compute its
  discrete divergence (incompressibility residual), enstrophy
  ``(1/2) * sum |curl u|^2``, and the finite-time Lyapunov exponent of
  the driving map. The blueprint's ``flow_lyapunov <= viscosity`` check
  is then a damping condition on discrete enstrophy growth — a
  finite-time regularity surrogate, *not* a global NS regularity proof.

Everything here is numerically or exactly computable on a laptop; the
report object names every stage and every place the analogy ends.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .. import substrates


def events_to_vertices(events: Sequence[Sequence[float]], L: int = 16) -> np.ndarray:
    """Quantize event feature vectors onto a ``L x L`` discrete torus.

    The embedding is the blueprint's own: an event's 2D position is its
    ``substrates.to_point`` image normalized to the unit square, then
    rounded onto ``Z_L^2``. Periodic boundary conditions apply.
    """
    verts = np.zeros((len(events), 2), dtype=np.int64)
    for i, ev in enumerate(events):
        p = substrates.to_point(np.asarray(ev, dtype=np.float64)[:2])
        verts[i] = (int(p[0] * L) % L, int(p[1] * L) % L)
    return verts


class DiscreteGaugeField:
    """A U(1) lattice gauge field over the event graph on ``Z_L^2``.

    ``phases[v]`` is the U(1) element at vertex ``v`` (argument of the
    embedded position); ``W[u][v]`` is the hopping weight (transition
    count). The connection on edge ``(u, v)`` is
    ``A_uv = theta(v) - theta(u)`` — a real 1-cochain; the plaquette
    holonomy is its curl, a discrete field strength.
    """

    def __init__(self, events: Sequence[Sequence[float]], L: int = 16):
        if not isinstance(L, int) or L < 4:
            raise ValueError("L must be an int >= 4")
        self.L = L
        verts = events_to_vertices(events, L)
        # Vertex phase: argument of the embedded unit-square position,
        # mapped to [0, 2*pi). Equal vertices share a phase — the bundle
        # is trivial, as demanded for the discrete theory.
        self.phases = np.zeros((L, L))
        for v in verts:
            x, y = int(v[0]), int(v[1])
            self.phases[x, y] = 2.0 * np.pi * ((x + y * L) / float(L * L))
        # Undirected adjacency weights from consecutive-event hops.
        self.W = np.zeros((L, L, 4))
        for a, b in zip(verts[:-1], verts[1:]):
            dx, dy = int(b[0] - a[0]), int(b[1] - a[1])
            if (dx, dy) in ((1, 0), (-1, 0)):
                d = 0 if dx == 1 else 1
                self.W[int(a[0]), int(a[1]), d] += 1
            elif (dx, dy) in ((0, 1), (0, -1)):
                d = 2 if dy == 1 else 3
                self.W[int(a[0]), int(a[1]), d] += 1
            # non-neighbor hops are recorded on the torus by shortest leg
            elif (dx, dy) != (0, 0):
                sx = 0 if np.sign(dx) > 0 else 1
                sy = 2 if np.sign(dy) > 0 else 3
                self.W[int(a[0]), int(a[1]), sx] += 1
                self.W[int(a[0]), int(a[1]), sy] += 1

    def connection(self, x: int, y: int, d: int) -> float:
        """The U(1) link angle ``A_(x,y)->d`` on edge direction ``d``.

        Directions: 0=+x, 1=-x, 2=+y, 3=-y (mod L on the torus).
        """
        nx = (x + ((1, -1, 0, 0)[d])) % self.L
        ny = (y + ((0, 0, 1, -1)[d])) % self.L
        return float((self.phases[nx, ny] - self.phases[x, y]) % (2.0 * np.pi))

    def plaquette_holonomy(self, x: int, y: int) -> float:
        """Field strength on the plaquette rooted at ``(x, y)``: the curl
        of the connection around the unit square, reduced mod 2*pi.

        ``F_p = A_x + A_y' - A_x' - A_y`` — the discrete Wilson loop
        argument. Zero for a flat connection; nonzero plaquettes are
        discrete vortices (curvature defects).
        """
        a_x = self.connection(x, y, 0)
        xp = (x + 1) % self.L
        a_y_at_xp = self.connection(xp, y, 2)
        yp = (y + 1) % self.L
        a_x_at_yp = self.connection(x, yp, 0)
        a_y = self.connection(x, y, 2)
        f = (a_x + a_y_at_xp - a_x_at_yp - a_y) % (2.0 * np.pi)
        return float(f if f <= np.pi else f - 2.0 * np.pi)

    def flux_spectrum(self) -> np.ndarray:
        """All L*L plaquette holonomies — the curvature spectrum."""
        return np.array(
            [self.plaquette_holonomy(x, y) for x in range(self.L) for y in range(self.L)]
        )

    def laplacian(self) -> np.ndarray:
        """The combinatorial graph Laplacian of the weighted event graph.

        Built on the ``L*L`` vertex set with symmetric weights
        ``W_uv = W[(u->v)] + W[(v->u)]``.
        """
        n = self.L * self.L
        w = np.zeros((n, n))
        steps = ((1, 0), (-1, 0), (0, 1), (0, -1))
        for x in range(self.L):
            for y in range(self.L):
                u = y * self.L + x
                for d, (dx, dy) in enumerate(steps):
                    w_uv = self.W[x, y, d]
                    if w_uv:
                        nx = (x + dx) % self.L
                        ny = (y + dy) % self.L
                        w[u, ny * self.L + nx] += w_uv
        w = w + w.T  # symmetrize: weight of (u,v) = both directions
        deg = w.sum(axis=1)
        return np.diag(deg) - w

    def spectral_gap(self) -> float:
        """``lambda_2`` — the Fiedler value of the event graph.

        The honest finite-volume analogue of a mass gap: the smallest
        positive eigenvalue of the graph Laplacian. A connected graph
        has lambda_2 > 0; an empty graph returns 0.
        """
        lap = self.laplacian()
        if np.allclose(lap, 0):
            return 0.0
        eigs = np.linalg.eigvalsh(lap)
        positives = eigs[eigs > 1e-10]
        return float(positives[0]) if len(positives) else 0.0

    def graph_distance(self, a: tuple[int, int], b: tuple[int, int]) -> int:
        """Torus graph distance — the lattice ``d`` in the escape cost."""
        dx = abs(a[0] - b[0]) % self.L
        dy = abs(a[1] - b[1]) % self.L
        return min(dx, self.L - dx) + min(dy, self.L - dy)

    def escape_cost(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        """Linear confinement analogue: ``lambda_2 * dist(a, b)``.

        Matches the blueprint's Yang-Mills cost shape
        ``cost = lyap * mass_gap * d`` with the gap being the measured
        finite-volume spectral gap of *this* graph.
        """
        return self.spectral_gap() * self.graph_distance(a, b)


class DiscreteFlowField:
    """Momentum-deposited velocity field from the event stream (NS analogue).

    Consecutive event positions contribute a displacement vector to the
    grid cell at the source vertex; averaging yields a discrete velocity
    ``u(x)`` on ``Z_L^2``. Divergence, curl and enstrophy follow by
    central differences with periodic boundary conditions.
    """

    def __init__(self, events: Sequence[Sequence[float]], L: int = 16):
        self.L = L
        verts = events_to_vertices(events, L)
        accum = np.zeros((L, L, 2))
        count = np.zeros((L, L))
        for a, b in zip(verts[:-1], verts[1:]):
            # Minimal signed torus displacement, component-wise, in
            # [-L/2, L/2] — the local velocity contribution at vertex a.
            disp = ((b - a + self.L // 2) % self.L) - self.L // 2
            accum[int(a[0]), int(a[1])] += disp
            count[int(a[0]), int(a[1])] += 1
        mask = count > 0
        self.u = np.zeros((L, L, 2))
        self.u[mask] = accum[mask] / count[mask, None]

    def divergence(self) -> np.ndarray:
        """``(du_x/dx + du_y/dy)`` by central differences, periodic."""
        ux = self.u[:, :, 0]
        uy = self.u[:, :, 1]
        return (
            np.roll(ux, -1, axis=0)
            - np.roll(ux, 1, axis=0)
            + np.roll(uy, -1, axis=1)
            - np.roll(uy, 1, axis=1)
        ) * 0.5

    def curl(self) -> np.ndarray:
        """Scalar vorticity ``du_y/dx - du_x/dy`` (2D field)."""
        ux = self.u[:, :, 0]
        uy = self.u[:, :, 1]
        return (
            np.roll(uy, -1, axis=0)
            - np.roll(uy, 1, axis=0)
            - (np.roll(ux, -1, axis=1) - np.roll(ux, 1, axis=1))
        ) * 0.5

    def enstrophy(self) -> float:
        """``(1/2) * sum |curl u|^2`` — the discrete enstrophy."""
        w = self.curl()
        return float(0.5 * np.sum(w * w))

    def incompressibility_residual(self) -> float:
        """RMS divergence — how far the deposited field is from solenoidal."""
        return float(np.sqrt(np.mean(self.divergence() ** 2)))

    def finite_time_lyapunov(self, point: Sequence[float], steps: int = 64) -> float:
        """Largest finite-time Lyapunov exponent of the driving map.

        Delegates to ``substrates.lyapunov_at`` — the standard-map
        maximal Lyapunov estimator the blueprint already uses — but
        reports it under its correct name: a finite-time exponent of a
        finite map, not a PDE regularity certificate.
        """
        return substrates.lyapunov_at(point, steps=steps)


def pde_functor_report(events: Sequence[Sequence[float]], L: int = 16) -> dict[str, Any]:
    """The exact functor, end to end, with every stage honestly named."""
    gauge = DiscreteGaugeField(events, L)
    flow = DiscreteFlowField(events, L)
    gap = gauge.spectral_gap()
    flux = gauge.flux_spectrum()
    return {
        "base_space": f"weighted event graph on Z_{L}^2 ({L * L} vertices)",
        "fiber_bundle": "trivial U(1) principal bundle over the event graph",
        "connection": "A_e = theta(v) - theta(u) mod 2pi (1-cochain on edges)",
        "field_strength": {
            "definition": "plaquette holonomy (curl of A), mod 2pi",
            "nontrivial_plaquettes": int(np.sum(np.abs(flux) > 1e-9)),
        },
        "spectral_gap": {
            "value": gap,
            "object": "second eigenvalue of the combinatorial graph Laplacian",
            "honest_label": "finite-volume spectral gap — not the continuum SU(N) mass gap",
        },
        "confinement": {
            "cost_form": "lambda_2 * graph_distance (linear in distance)",
            "note": "matches the blueprint's lyap * mass_gap * d shape with the measured gap",
        },
        "navier_stokes": {
            "field": "momentum-deposited discrete velocity u on Z_L^2",
            "incompressibility_residual": flow.incompressibility_residual(),
            "enstrophy": flow.enstrophy(),
            "finite_time_lyapunov": flow.finite_time_lyapunov((0.5, 0.5)),
            "honest_label": (
                "finite-time Lyapunov + discrete enstrophy damping — "
                "not a global Navier-Stokes regularity proof"
            ),
        },
        "substrate_gap_note": {
            "toe_finite_gauge_gap": substrates.gauge_gap(),
            "already_disclaimed": (
                "toe.poincare_yangmills documents its gap as the first "
                "positive eigenvalue of the 2I quantum-group Laplacian — "
                "not the continuum Yang-Mills mass gap"
            ),
        },
    }


__all__ = [
    "events_to_vertices",
    "DiscreteGaugeField",
    "DiscreteFlowField",
    "pde_functor_report",
]
