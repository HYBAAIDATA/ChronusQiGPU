# Agent Doctrine — HYBA → PYTHIA Evolution, Mining Stewardship & Security Trajectory

> This document extends the engineering intent of `AGENTS.md` without replacing its foundational mathematical thesis. Autonomous agents and human collaborators should read it alongside `AGENTS.md` when working on mining, production integration, security, execution provenance, Salamander, Stratum, agentic search, or release readiness.

## 1. PYTHIA is a natural evolution of HYBA

PYTHIA is not a separate philosophy bolted onto HYBA. It is a natural operational evolution of the same research direction:

> **Change the representation. Change the topology. Preserve the truth boundary.**

HYBA began by challenging inherited assumptions about how data, memory, state, search and computation must be represented. Folding, exact reconstruction, structured state, manifold ordering and evidence-first execution emerged from that work. PYTHIA applies the same discipline to mining.

The mining system may change:

- representation;
- ordering;
- work allocation;
- topology;
- scheduling;
- precomputation;
- recovery;
- observability;
- execution routing.

It may not change Bitcoin's proof boundary.

```text
STRATUM defines real work.
INTELLIGENCE prepares and orders that work.
EXECUTION performs exactly the authorised work.
SHA256d determines candidate validity.
THE POOL determines share acceptance.
THE CHAIN determines external block truth.
SALAMANDER governs health and recovery.
```

No agent may collapse these authorities.

## 2. Mining history and evolution

### Phase 0 — Bitcoin truth first

The initial contract is unchanged Bitcoin proof-of-work:

```text
valid negotiated job
→ valid block header
→ SHA256(SHA256(header))
→ target comparison
→ Stratum submission
→ literal pool result
```

Everything PYTHIA builds sits around this boundary, never through it.

### Phase 1 — Structured M32 allocation

The first mining evolution introduced deterministic structured 32-lane allocation, geometry-aware ordering, TOE context and complete SHA256d verification. Intelligence could change search order and work allocation while the proof path remained canonical.

### Phase 2 — Golden-stride traversal

The golden-stride path changed nonce probe ordering while preserving domain coverage. Deterministic ordering, hardware execution evidence and host-reference checks became first-class requirements.

### Phase 3 — 11-dimensional geometry

Research expanded into 11-dimensional Poincaré/Cassini and Klein/Poincaré structures. These are internal mathematical/search representations. They are not alternate consensus rules and are not security credentials.

Where an implementation is numerical, agents must call it numerical. Float64/tolerance-based Klein ordering must not be labelled exact arithmetic.

### Phase 4 — Agentic mining

The workflow evolved from reactive chooser logic toward precomputed, bounded, evidence-correlated mining:

```text
live Stratum job
→ canonical generation
→ AgenticMiningController
→ SearchPlan
→ nonce lease
→ executor
→ ExecutionRecord
→ pool outcome
→ operational learning
→ next plan
```

Operational learning may include:

- job churn;
- stale-work rate;
- queue starvation;
- measured latency;
- actual completion;
- recovery outcomes;
- literal pool accept/reject/stale/unknown results.

Operational learning must never turn a previous winning nonce into evidence that nearby nonces are cryptographically more likely to satisfy SHA256d.

### Phase 5 — Salamander governance

The self-healing/self-optimising path is converging on one closed-loop governor:

```text
OBSERVE
→ CLASSIFY
→ PLAN
→ ACT
→ ACK
→ RE-OBSERVE
→ VERIFY RECOVERY
→ RESUME
```

An action request is not success. An actuator ACK is not a healthy system. Recovery requires post-action evidence.

### Phase 6 — execution truth

The current execution trajectory is to make the physical/software execution boundary impossible to misreport by accident:

```text
SearchPlan
→ requested route
→ actual route decision
→ freshness / lease guard
→ exact disjoint physical chunks
→ measured execution
→ independent SHA256d recheck
→ ExecutionRecord
```

Required distinctions:

```text
requested_route != executed_route
configured_device != hardware_executed
kernel_built != kernel_launched
kernel_launched != window_completed
hit_sample != completion_evidence
submitted != accepted
```

A reported Cline workstream delivery (`7cc591e`) adds an `ExecutionRouter`, route provenance, chunk coverage, lease compatibility and hardware-backed execution tests on Intel UHD 620. Until that work is canonically merged and independently reviewed, agents must describe it as reported integration evidence rather than merged repository truth.

Reported verification from that workstream:

- 34 execution-router tests, including 4 hardware-backed tests;
- 136 platform mining/lease tests;
- 1208 reported `tests/` passes with 0 failures;
- 4/4 kernel mirrors reported byte-identical;
- Intel UHD 620 OpenCL execution reported.

Still unverified from that report:

- fleet-scale hardware execution;
- live pool ACK in the integrated production miner;
- chain-reorg behavior;
- complete Stratum lifecycle through the final execution router;
- complete cross-system production voyage.

## 3. Production trajectory

Agents must optimize for the continuous system, not isolated component impressiveness.

Target voyage:

```text
BOOT
→ STRATUM CONNECT
→ SUBSCRIBE
→ AUTHORIZE
→ LIVE JOB
→ CANONICAL GENERATION
→ AGENTIC PRECOMPUTE
→ UNIQUE NONCE LEASE
→ EXECUTION ROUTER
→ CPU / OPENCL EXECUTION
→ SHA256d RECHECK
→ VERIFIED CANDIDATE
→ SUBMISSION
→ LITERAL POOL OUTCOME
→ OPERATIONAL LEARNING
→ CONTINUED MINING
→ FAULT
→ SALAMANDER RECOVERY
→ VERIFIED RECOVERY
→ CONTINUED MINING
```

The miner must not silently go dark after:

- an accepted share;
- a rejected share;
- a stale share;
- a new job;
- a disconnect;
- a failover;
- device recovery;
- process restart;

unless a genuine fail-closed condition requires `PAUSED` or `FAULTED`.

## 4. Bitcoin stewardship doctrine

HYBA/PYTHIA is not being built to dominate Bitcoin, threaten SHA256, weaken consensus or undermine network security.

The intent is stewardship through better internal architecture and evidence discipline.

Agents must preserve these invariants:

1. SHA256d remains canonical proof authority.
2. Target comparison remains canonical proof authority.
3. A share is accepted only by literal pool response.
4. A block is confirmed only by external chain evidence.
5. Intelligence may reorder and schedule work; it may not redefine proof.
6. Experimental mathematics stays outside proof authority unless formally promoted through an explicit reviewed contract.

The project's posture can be summarized as **quiet guardianship**:

```text
preserve consensus truth
→ improve internal representation
→ reduce wasted work
→ increase provenance
→ strengthen recovery
→ expose fewer privileged surfaces
→ never weaken Bitcoin's proof boundary
```

## 5. Security doctrine: remove unnecessary doors

The security objective is not to make an unsupported claim that PYTHIA is "unhackable". Serious systems do not claim impossibility without a defined threat model and sustained adversarial evidence.

The objective is stronger and more useful:

> **Change the attack surface. Change the topology. Remove unnecessary doors rather than merely adding larger locks to every inherited interface.**

Agents should prefer architectures that reduce externally reachable control surfaces and isolate authority.

Desired trajectory:

```text
minimal exposed surface
→ authenticated entry
→ explicit authorization
→ least privilege
→ capability-scoped interfaces
→ isolated Stratum / planning / execution / proof / recovery authorities
→ immutable correlation IDs
→ fail closed on missing evidence
→ measured anomaly detection
→ bounded recovery
```

The system should be built so compromise becomes materially harder because fewer privileged transitions exist and each transition is identity-bound, auditable and isolated.

### 5.1 Single-user / restricted-access posture

Where the deployment is intentionally single-operator, agents should treat that as a restrictive deployment requirement, not as an excuse to omit access control.

A single intended user still requires:

- explicit authentication;
- authorization;
- secret hygiene;
- safe session handling;
- least privilege;
- closed-by-default administrative endpoints;
- no unauthenticated control plane;
- no credentials exposed to frontend clients or logs.

### 5.2 Mathematical dimensions are not access controls

11D geometry, swarm intelligence, exact algebra, manifold transforms and other internal mathematical structures are computational models. They do not themselves make a service secure.

Security claims must be grounded in:

- authentication;
- authorization;
- isolation;
- cryptographic integrity;
- provenance;
- safe defaults;
- secret management;
- adversarial testing;
- recovery evidence.

## 6. Swarm and multi-agent doctrine

PYTHIA increasingly uses agentic and swarm workflows. Multi-agent work must improve verification, not create duplicate authorities.

Preferred structure:

```text
lead agent
→ narrow subagents
→ explicit file/authority ownership
→ interface contracts
→ independent integration review
```

Subagents may investigate, test and implement bounded tasks. They must not independently invent parallel Stratum clients, proof validators, job-generation models, nonce allocators, Salamander governors or execution routers.

When a subsystem contract is insufficient, return an interface requirement to the owning lead.

## 7. Millennium and difficult-mathematics surfaces

The repository contains computational probes and partial results around deep mathematical problems. Agents must preserve the distinction between computation and theorem.

Allowed statements include:

```text
finite case verified
identity checked
numerical gap measured
known theorem scope reproduced
open question remains open
```

Not allowed without proof:

```text
Millennium problem solved
new theorem established
open result impossible
```

"Not proven here" is not equivalent to "unprovable."

Mathematical research may guide representations, schedules, invariants and hypotheses. It does not automatically create cryptographic advantage or production authority.

## 8. Evidence-first documentation law

Every engineering claim should carry an evidence class where material:

```text
SOURCE VERIFIED
SOFTWARE EXECUTION VERIFIED
HARDWARE EXECUTION VERIFIED
POOL VERIFIED
UNVERIFIED
```

Examples:

```text
GPU discovered != hardware executed
kernel compiled != kernel launched
kernel launched != window complete
candidate found != valid share
submission sent != accepted
accepted share != block confirmed
mathematical identity != Bitcoin proof-of-work
```

Do not collapse `UNVERIFIED` into `PASS`.

## 9. Required agent posture

HYBA/PYTHIA does not wait for conventional architectures to grant permission to explore a mathematically sound alternative. Agents should be willing to test unconventional representations and topology.

That mandate does **not** permit overclaiming.

The correct posture is:

```text
question inherited representation
→ construct the mathematical alternative
→ implement it
→ falsify it
→ measure it
→ integrate it under explicit authority boundaries
→ strengthen the system
```

Innovation without evidence is drift.
Evidence without imagination is stagnation.
PYTHIA requires both.