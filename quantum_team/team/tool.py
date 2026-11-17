"""The QuantumTool — the only surface the agent team sees.

solve_allocation: subspace-exact adiabatic evolution in (C^A)^{tensor T};
invalid assignments are unrepresentable, validity needs no penalty.
select_generation: fitness enters as phase only; the Grover round count
comes from the theorem via M_eff = sum f_i^2 — no classical peeking, no
scanned schedules. Returned 'probabilities' fields are simulation-only
diagnostics; on hardware only the samples exist."""

from __future__ import annotations

import numpy as np

from quantum import (State, apply_diffusion, apply_phase,
                     brute_force_optimum, decode_allocation, evolve,
                     problem_diagonal)


class QuantumTool:
    def solve_allocation(self, *, cost, coupled=(), load_limit=None,
                         conflict_pen=8.0, load_pen=6.0,
                         total_time=None, steps=None) -> dict:
        cost = np.asarray(cost, dtype=float)
        T, A = cost.shape
        load_limit = (load_limit if load_limit is not None
                      else max(1, (T + A - 1) // A))

        diag = problem_diagonal(T, A, cost, list(coupled), load_limit,
                                conflict_pen, load_pen)
        if total_time is None:
            # np.ptp, not ndarray.ptp: the method was removed in NumPy 2.0.
            total_time = 12.0 + 1.5 * float(np.ptp(diag))
        if steps is None:
            steps = max(400, int(40 * total_time))

        psi = evolve(diag, T, A, total_time, steps)
        probs = np.abs(psi) ** 2
        assignment = decode_allocation(probs, T, A)
        opt_cost, opt_assign = brute_force_optimum(
            T, A, cost, list(coupled), load_limit, conflict_pen, load_pen)
        return {"assignments": assignment,
                "optimal_cost": opt_cost, "optimal_assignment": opt_assign,
                "probabilities": probs}

    def select_generation(self, fitness, k, rng=None) -> dict:
        rng = rng or np.random.default_rng()
        f = np.asarray(fitness, dtype=float)
        f = f - f.min() if f.min() < 0 else f.copy()
        f = f / f.max() if f.max() > 0 else np.zeros_like(f)
        n = len(f)

        m_eff = max(1.0, float(np.sum(f ** 2)))          # Grover theorem input
        rounds = max(1, int(np.floor((np.pi / 4.0) * np.sqrt(n / m_eff))))

        state = State.uniform(n)
        for _ in range(rounds):
            state = apply_phase(state, f)
            state = apply_diffusion(state)

        probs = state.probs()
        parents = list(rng.choice(n, size=k, replace=False,
                                  p=probs / probs.sum()))
        top = sorted(np.argsort(f)[-k:])
        return {"parent_indices": parents, "rounds": rounds,
                "born_mass_on_topk": float(probs[top].sum()),
                "probabilities": probs}
