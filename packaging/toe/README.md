# TOE — a domain-general mathematical intelligence engine

TOE takes a problem from almost any domain, reduces it to one domain-neutral
form, and runs the same reasoning cycle over it:

```
observe → represent → understand (association, structure, causal effect)
        → explore futures → value of information → precision
        → decide / plan → arbitrate → explain → self-check → receipt
outcome → prediction error → model revision → memory → durable custody
```

Changing the domain changes the **adapter** that translates the problem, not the
machine that reasons about it.

```python
import toe
from toe.planning import OperatorSpec
from toe.policy import Objective

problem = toe.Problem(
    domain="operations",
    state={"x": 0.0, "z": 0.0},
    structure=toe.Structure.of([("x", "y", 2.0), ("z", "y", 1.0)]),   # an assumption
    operators=(OperatorSpec("raise_x", "x", (1.0,)), OperatorSpec("raise_z", "z", (1.0,))),
    objective=Objective("y"),
    uncertain={"edge:x->y": (0.2, 1.0, 2.0)},
    noise_sd={"x": 1.0, "z": 1.0, "y": 0.05},
)
machine = toe.TOEMachine()
episode = machine.run(problem)
episode["status"]                      # 'ACQUIRE_EVIDENCE' — the decision could flip
episode["meta"]["evidence_plan"]       # [{'experiment': 'intervene on x and observe y', ...}]
machine.learn(episode, observed_rows)  # bind outcomes → assess → revise
machine.run(problem)["status"]         # 'ACT' once the evidence settles it
```

## Where it came from

TOE was discovered while expressed as an HR application — an employee-churn engine
(`toe.engine.PredictiveEngine`) whose columns were *employee*, *churn*, *promotion*,
*compensation*. That vocabulary is the lineage, not the product. The original surface
is kept as an adapter (`toe.adapters.legacy_hr`, extra `legacy-hr`), next to the
other domain adapters, over the same backend.

## One backend, many problem forms (measured)

`toe.voyage.cross_domain_voyage()` sends eight different problem classes through **one**
`TOEMachine`: tabular records with a hidden confounder, an explicit causal system with
a budget trap, a walled graph, a controlled time series, Python source structure, an
integer sequence, a precision-critical linear system, and the legacy HR records. The
trace of every backend callable is recorded; no adapter code appears in it, and the
reasoning core never imports an adapter. That is the claim, and the evidence for it is
limited to these classes. TOE does **not** claim to solve every problem.

## What it does — with evidence classes

| Capability | Status |
|---|---|
| Multi-representation state bound to one observation digest (statistical, tensor, temporal, algebraic, geometric, topological, causal graph) | MEASURED |
| Association vs discovered structure vs supplied structure vs identified effect — effects released only when identified; refusal otherwise | MEASURED |
| Supplied-graph check: testable implications contradicted by data → structure flagged, effects withheld | MEASURED (Markov-equivalent wrong graphs are undetectable) |
| Interventions (do-surgery) and unit-level counterfactuals (abduction) on linear SCMs; exact Q(φ) path | MEASURED |
| Futures as distributions, labelled *predicted*, never observed | MEASURED |
| Planning over the futures model (chance constraints on quantiles) vs greedy | MEASURED |
| Value of information: act when invariant, request a specific experiment when not | MEASURED |
| Adaptive precision: float64 with a declared error bound, exact arithmetic inside it | MEASURED on CPython 3.11 (60/60 vs 28/60 float-only); no difference on 3.12, whose float `sum()` is compensated — exact escalation makes the decision interpreter-invariant |
| Disagreement between surfaces arbitrated by declared authority, never averaged | MEASURED |
| World-model revision from observed consequences; contradiction widens uncertainty and requests evidence | MEASURED |
| Durable learning state through THESEUS custody; restart recovers; tampering fails closed | MEASURED (needs THESEUS) |
| Geometric reasoning: Poincaré ball on the φ-weighted 11D metric, hyperbolic tree embedding, greedy routing, spectral geometry | MEASURED |

The held-out ablation study (`scripts/toe_ablation_study.py` in the repository) shows each
capability changing outcomes when its precondition holds, with a negative control showing
parity when it does not.

## What TOE is not

- **Not a mining validity predicate.** In PYTHIA's mining workload TOE advises an
  operational setting; PYTHIA authorises; double-SHA256 and the target comparison alone
  decide validity.
- **Not a physical quantum computer.** TOE executes quantum-mathematical formalism in
  software (through KELLOGG). It makes no physical-QPU claim and no quantum-advantage claim.
- **Not a proof of continuum Yang–Mills.** The finite golden-icosian construction
  (2I, the 600-cell, a positive finite Laplacian gap (3−√5)/4) is computationally verified
  in the research code TOE reads; the continuum problem remains open.
- **Not "the same φ, therefore the same phenomenon".** Shared mathematical structure is
  evidence of structural unity only.

## Ownership

| System | Owns | Relation to TOE |
|---|---|---|
| **TOE** | domain-general world modelling, causal inference, futures, planning, VOI, precision, explanation, revision | this package |
| **KELLOGG** (`kellogg-tensor`) | tensor mathematics, exact fields (Q(φ), Q(ζ8)) | required dependency; consumed, never copied |
| **EUCLID** | orchestration — decides when TOE is asked | consumer |
| **PYTHIA** | mining authority | consumer |
| **TURING** | virtual quantum computer execution | TOE may request computation |
| **THESEUS** | durable custody | optional integration for persistence |
| **OVID** | authorised representation transformation | not bundled |

Without THESEUS installed, persistence is reported **UNAVAILABLE** — TOE keeps no private
store.

## Install

Approved first-public distribution: **`hyba-toe==1.0.0`**, per `OWNER_DECISIONS.md`.
The commands below are the approved publication target, not evidence that the
registry release exists or has passed clean-install execution. Registry
prerequisites and publication verification remain open until evidenced.

```bash
pip install hyba-toe==1.0.0
pip install "hyba-toe[legacy-hr]==1.0.0"   # + pandas for the original HR engine
```

Requires Python ≥ 3.11, numpy and `kellogg-tensor` ≥ 1.0.

## Self-test

```python
from toe.voyage import canonical_voyage, cross_domain_voyage
cross_domain_voyage()   # eight problem classes, one machine, backend trace per domain
canonical_voyage()      # learning loop; restart/persistence UNAVAILABLE without THESEUS
```

The claim register ships with the package: `toe/CLAIM_REGISTER.json` (statuses PROVED,
COMPUTATIONALLY_VERIFIED, MEASURED, NEGATIVE, OPEN, UNSUPPORTED — never collapsed), and the
capability manifest: `toe/CAPABILITY_MANIFEST.json`.
