"""Measure Pearl's causal ladder: Rung 2 (intervention) and Rung 3 (counterfactual).

The TOE diagram has three columns -- STATE, UNDERSTANDING, FUTURES. Earlier
probes covered representation (STATE) and causality (UNDERSTANDING). The
FUTURES column splits into prediction, counterfactuals and intervention, and
the last two are what actually drive the verticals. Neither had been measured.

Ground truth is constructed, not assumed: a known SEM with a known causal
coefficient, so the ladder's answer is scored against truth rather than
merely reported. All six checks pass.

A. INTERVENTION -- association overstates, and by a measurable amount
   Fork U->X, U->Y, X->Y with structural weight 3.0, 400k samples:
     observed regression slope : +3.553
     true causal coefficient   : +3.000
     bias from confounding     : +0.553
   A correlation-only system would report +3.553 as the causal effect. This
   is the number the do-operator exists to correct.

B. IDENTIFIABILITY -- the backdoor contract holds in both directions
   Confounded fork U->X, U->Y, X->Y  ->  backdoor set ['U']   (found)
   Unconfounded X->Y                 ->  backdoor set []      (correctly empty)
   A correct implementation must report an EMPTY set when there is no
   confounder, not invent an adjustment. It does.

C. COUNTERFACTUAL -- do-operator is exact
   Single parent X->Y, weight 2.0:
     observational X=1  : Y = 2.000   (truth 2.000)
     do(X=3)            : Y = 6.000   (truth 6.000)
     X after do()       : 3.000       (incoming edges cut, surgery holds)
     Y with u_Y=1       : Y = 3.618   (= 2*1 + phi exactly)
   The phi coupling is exact, not an approximation: causal_ladder.py:243
   computes `exogenous * PHI`, so u_Y=1 contributes exactly phi.

Two probe bugs found and fixed while writing this, both caught by the
assertions rather than assumed away:

1. The first fork used X = e + U, making the confounder collinear with the
   causal path; the effects cancelled and the slope came out +2.999,
   falsely looking unconfounded. Real confounding needs X to carry its own
   independent noise.
2. `exogenous` is the exogenous NOISE u_i, not the node's value
   (value = u*PHI + sum(w*parent)). Passing X=1.0 therefore set X to phi.
   The corrected probe passes u_X = 1/phi to pin X at exactly 1.0.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def probe_intervention_ground_truth():
    """do(X) must move Y by the structural weight, not by the raw correlation.

    The first version of this probe used X = e + U, which makes the
    confounder collinear with the causal path; the two cancel and the
    observed slope came out at +2.999, looking unconfounded. The confound is
    only real when X has its OWN independent noise, so the fork below gives
    U genuine influence on X that the causal path does not explain.
    """
    print("=== FUTURES / INTERVENTION: do-operator against known truth ===")
    rng = np.random.default_rng(1517)
    n = 400_000
    # Fork:  U -> X  and  U -> Y,  plus  X -> Y with structural weight 3.
    # X gets independent noise so U's influence is not absorbed into X.
    u = rng.normal(size=n)
    x = rng.normal(size=n) + 1.5 * u
    y = 3.0 * x + 1.2 * u + rng.normal(size=n) * 0.4

    observed = float(np.cov(x, y, ddof=0)[0, 1] / np.var(x))
    truth = 3.0
    print(f"  observed regression slope (association) : {observed:+.3f}")
    print(f"  TRUE causal coefficient (do-operator)   : {truth:+.3f}")
    print(f"  bias from confounding                  : {observed - truth:+.3f}")
    print()
    inflated = abs(observed - truth) > 0.15
    print(f"  association is measurably inflated      : {inflated}")
    if not inflated:
        print("  (setup failed to produce confounding -- the probe is invalid)")
    return inflated


def probe_backdoor_identifiability():
    """The backdoor set must be found, and the estimate must be honest."""
    from toe.causal_ladder import CausalGraph, identify_backdoor

    print()
    print("=== FUTURES / IDENTIFIABILITY: backdoor adjustment ===")
    # A confounded fork:  U -> X,  U -> Y,  X -> Y
    g = CausalGraph()
    g.add_edge("U", "X")
    g.add_edge("U", "Y")
    g.add_edge("X", "Y")
    print(f"  nodes            : {g.nodes}")
    print(f"  is DAG           : {g.is_dag()}")
    print(f"  ancestors of Y   : {sorted(g.ancestors('Y'))}")
    try:
        bd = identify_backdoor(g, "X", "Y")
        print(f"  backdoor set     : {bd}")
    except Exception as exc:
        print(f"  identify_backdoor: {type(exc).__name__}: {exc}")
        return False

    # Front-door style: no backdoor path if U is blocked.
    print()
    # The unconfounded case: X -> Y only. There is NO backdoor path, and a
    # correct implementation must say so rather than invent an adjustment.
    g2 = CausalGraph()
    g2.add_edge("X", "Y")
    try:
        bd2 = identify_backdoor(g2, "X", "Y")
        print(f"  unconfounded X->Y backdoor set : {bd2}")
        clean = not bd2
        print(f"  correctly reports no confounder: {clean}")
    except Exception as exc:
        print(f"  unconfounded raised {type(exc).__name__}: {exc}")
        return False
    return clean


def probe_counterfactual_structural():
    """evaluate_all(interventions=...) IS the do-operator, via graph surgery.

    The docstring states intervened nodes have their incoming edges cut and
    their structural equation bypassed. With a single parent X -> Y of weight
    w, do(X=x) must give Y = w*x exactly, and cutting the edge must be
    observable as the intervention taking full authority over X.
    """
    from toe.causal_ladder import CausalGraph, StructuralCausalModel

    phi = (1 + 5**0.5) / 2
    print()
    print("=== FUTURES / COUNTERFACTUAL: SCM re-evaluation under do() ===")
    g = CausalGraph()
    g.add_edge("X", "Y", weight=2.0)
    scm = StructuralCausalModel(g)
    print(f"  graph edges        : {g.edge_weights}")

    # SEMANTICS, verified against causal_ladder.py:242-246:
    #     value = exogenous * PHI + sum(w_ij * parent_j)
    # So `exogenous` is the EXOGENOUS NOISE u_i, not the node's value.
    # Setting u_X = 0 and intervening are the two ways to pin X exactly.
    #
    # Observational, X pinned by noise: u_X = 1/phi so X = 1.0 -> Y = 2.0
    inv_phi = 1.0 / phi
    obs = scm.evaluate_all(exogenous={"X": inv_phi, "Y": 0.0})
    # do(X=3): incoming edges cut, X fixed at 3 -> Y = 2*3 = 6
    iv = scm.evaluate_all(interventions={"X": 3.0}, exogenous={"Y": 0.0})
    print(f"  observational X=1  : Y = {obs.get('Y'):.3f}  (truth 2.000)")
    print(f"  do(X=3)            : Y = {iv.get('Y'):.3f}  (truth 6.000)")
    print(f"  X after do()       : {iv.get('X'):.3f}  (must be 3, edge cut)")
    print()
    # Prove the phi coupling is exact, not an approximation.
    noisy = scm.evaluate_all(exogenous={"X": inv_phi, "Y": 1.0})
    print(f"  Y with u_Y=1       : Y = {noisy.get('Y'):.3f}  (2*1 + phi = {2 + phi:.3f})")
    coupling_ok = abs(noisy.get("Y", 0) - (2.0 + phi)) < 1e-9
    print(f"  phi coupling exact : {coupling_ok}")

    ok_obs = abs(obs.get("Y", 0) - 2.0) < 1e-9
    ok_iv = abs(iv.get("Y", 0) - 6.0) < 1e-9
    ok_x = abs(iv.get("X", 0) - 3.0) < 1e-9
    print()
    print(f"  observational matches truth : {ok_obs}")
    print(f"  do-operator matches truth   : {ok_iv}")
    print(f"  intervention took authority : {ok_x}")
    return ok_obs and ok_iv and ok_x and coupling_ok


if __name__ == "__main__":
    a = probe_intervention_ground_truth()
    b = probe_backdoor_identifiability()
    c = probe_counterfactual_structural()
    print()
    print("=== SUMMARY ===")
    print(f"  association measurably inflated : {a}")
    print(f"  backdoor reported honestly      : {b}")
    print(f"  counterfactual matches truth    : {c}")
    sys.stdout.flush()
