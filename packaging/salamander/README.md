# hyba-salamander

SALAMANDER's canonical autonomic control-plane library, maintained by
HYBA Software Limited. Distribution: `hyba-salamander`; import: `salamander`.
Planned first public version: **1.0.0**. Python targets: 3.11–3.13. License: MIT.

**Release preparation / Alpha. Not yet qualified for production self-healing.**
An installable package is not evidence that the full production recovery loop
has passed its custody, restart, learning, rollback and real-component gates.
No registry publication is performed by this build tooling.

## Included capabilities

- Typed health, action, observation, recovery and optimisation contracts.
- AL HARAS authorisation adapter and `build_authorized_control_plane`.
- Named action registry, independent-verifier seam and circuit breakers.
- Bounded recovery plans and authorised rollback coordination.
- Hash-chained evidence ledgers and checkpoint/replay safety primitives.
- Read-only custodied mining outcome verification over a supplied SystemDataPort.
- Mining observation bridge and discovery/optimisation integration seam.

All canonical `salamander` modules and the existing bundled `al_haras` package
are staged from repository source. AL HARAS retains governance authority; its
inclusion does not transfer that authority to SALAMANDER. Tests, caches and
runtime state are not distribution contents. No other subsystem is vendored.

## Safe first use

```python
from salamander import EvidenceLedger
from salamander.control_plane import ActionRegistry, AutonomicControlPlane, FailClosed
from salamander.models import ActionKind, ActionRequest

ledger = EvidenceLedger()
ledger.append("startup-observation", {"phase": "observing"}, at_ns=1)
assert ledger.verify()

plane = AutonomicControlPlane(registry=ActionRegistry(), ledger=ledger)
request = ActionRequest(
    action_id="example", kind=ActionKind.REPLAN, handler="unconfigured",
    tenant_id="example", target="worker", reason="example",
    bounds={"max_attempts": 1}, idempotency_key="example", actor_id="operator",
)
try:
    plane.execute(request)
except FailClosed:
    pass  # missing governance/owner wiring cannot authorise an action
```

For actuation, supply the actual AL HARAS guardian and an out-of-band token
provider to `build_authorized_control_plane`. Register owning-subsystem handlers
and independent probes. Do not copy production credentials into requests,
examples or evidence. There is no `require_authorization=False` escape hatch.

## Integration boundaries

SALAMANDER coordinates; AL HARAS governs; EUCLID orchestrates; PYTHIA owns
predictive/causal intelligence and mining; CHRONUS owns execution; TURING owns
VQC execution; THESEUS owns custody; OVID owns organisation/query state.

The default EvidenceLedger is **process-local**, not canonical durable custody.
The mining JSONL ledger is a local mirror, not a substitute THESEUS store.
Reconstructing a checkpoint does not prove fresh-process production replay.

`CustodiedMiningOutcomeVerifier` consumes an existing shared SystemDataPort;
it never creates its own store or its own owner proof records. Missing owner
proofs or telemetry stay unavailable. The standalone package does not bundle
THESEUS/OVID, a mining service, CHRONUS, TURING or EUCLID.

`discovery_optimisation` imports without TOE, but candidates are refused when
`toe.intelligences` authority contracts are unavailable. The capability remains
in source; the integration is not silently substituted. Optional AL HARAS
FastAPI routes require the `api` extra and explicit application configuration.

## Build and verify

From a clean, committed full PhiMiner checkout:

```bash
python packaging/salamander/build_and_verify.py \
  --out-dir /tmp/salamander-release-candidate
```

Use a **fresh directory outside the checkout**. The command stages canonical
sources, records the source commit and input digests, builds an sdist, builds the
wheel from that sdist, checks archives and metadata with Twine, installs the
wheel in a fresh environment, imports every shipped module, and executes
installed-library boundary tests. It does not upload or create a GitHub release.

The output verdict separates `artifact_verified`, `production_qualified`,
`publishable` and `published`. Unit actuators/probes cannot qualify production
composition. See `RELEASE.md` for review findings and the remaining release gates.
