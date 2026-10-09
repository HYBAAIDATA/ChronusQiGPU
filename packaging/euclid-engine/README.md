# hyba-euclid-intelligence 1.0.0 — first-public research package candidate

Distribution identity is **`hyba-euclid-intelligence==1.0.0`** under the first-public
version policy. The contained research generation and `euclid.__version__`
remain **17.0.0**; `euclid-v17-research` is unchanged. Historical 17.0.0 build
records are not evidence for the new 1.0.0 archives. Publication remains pending.
`build_and_verify.py` builds a fresh sdist and a wheel from that sdist, checks
source hashes, then qualifies the installed copy outside the checkout. This is a **research release**, not
whole-platform production certification.

EUCLID's governed runtime plus the v17 **integrated adaptive intelligence**:
one `GeneralIntelligenceCore` orchestrating a Bayesian mechanism world model,
expected-information-gain interventions, value-of-information metacognition,
contextual strategy meta-learning, structural analogy, hierarchical model-based
planning with measured representation restructuring, evidence-gated primitive
discovery, adaptive multi-objective decisions, dynamic objectives with proxy
auditing, and episode consolidation with transfer bookkeeping.

```python
from euclid.cognition.worlds import generate_task, MechanismWorld, WorldExecutor
from euclid.cognition.integrated import IntegratedAgent

spec, truth = generate_task("program-transformation", seed=1, partition="evaluation")
agent = IntegratedAgent.for_system("integrated")
result = agent.solve(spec, WorldExecutor(MechanismWorld(spec, truth)))
print(result.summary())
```

`euclid-v17-research --output report/` re-runs the pre-registered research
programme (train / development / frozen evaluation, ablations, transfer,
continual learning, adversarial attacks, φ experiments, self-improvement).

## Packaging note (pre-existing coupling)

`euclid` imports `hyba_substrate` and `resonance_intelligence` at import time
(durable JSON writes, the experience learner and the feedback core).  They are
bundled under their own top-level names so the wheel installs and imports in a
clean environment.  Removing this cross-product coupling is tracked debt; the
v17 cognition modules themselves have no third-party or sibling dependency.

Canonical adaptive persistence uses the declared `hyba-theseus-storage` dependency:
start `aethel.enterprise.lifecycle.CompositionRoot`, then bind its `euclid` data
port with `runtime.bind_adaptive_data_port(...)` before composing intelligence.
An unbound runtime retains knowledge in memory and emits a not-persisted event.
The installed-package check exercises `EuclidRuntime`, governed task execution,
custody readback and a fresh-process adaptive replay. The full monorepo
`EuclidRuntime.production()` organism also needs its optional PYTHIA and organ
implementations; this research package does not certify that whole organism.

No AGI, consciousness, quantum-advantage or production-authority claim is made.
Results are internal, measured, and reported with intervals in
`docs/EUCLID_V17_RESEARCH_RELEASE.md`.
