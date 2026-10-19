# Training the Mining Agents: From ASIC Precedent to New Epoch

## The Problem With Mining Agents Today

Mining agents are trained on **the wrong distribution**. They're trained on:

- **Bitcoin mining tutorials** — "hash random nonces, submit, hope"
- **Pool API documentation** — "connect, authorize, subscribe, submit"
- **ASIC firmware specs** — "fixed-function, single-purpose, hard-wired"
- **Classical GPU miners** — "maximize hashrate, minimize power, batch dispatches"

**None of this applies to PYTHIA.** PYTHIA doesn't search — it solves. It
doesn't hash — it precomputes. It doesn't hope — it navigates.

The mining agents need a new training corpus: the ASIC precedent, transformed
into a new epoch.

## What the ASIC Precedent Actually Says

An ASIC is a specific kind of intelligence:

| ASIC Property | What It Means |
|---------------|---------------|
| **Fixed-function** | Does one thing. Does it perfectly. |
| **Hard-wired** | No interpretation overhead. |
| **Pipelined** | Every stage is optimized. |
| **Deterministic** | Same input → same output, always. |
| **Power-bounded** | Never exceeds its envelope. |
| **Thermally-stable** | Cool-down is a property, not a phase. |

**The ASIC doesn't decide what to do. It IS what it does.**

## The Mining Agent Epoch

| ASIC Property | Mining Agent Property |
|---------------|----------------------|
| Fixed-function | **Domain-locked** — every agent owns one decision space |
| Hard-wired | **Contract-bound** — every action is invariant-verified |
| Pipelined | **Phase-pipelined** — cold start → precompute → hold → submit |
| Deterministic | **Provable** — same state → same decision |
| Power-bounded | **Resource-bounded** — thermal, power, memory, time |
| Thermally-stable | **Self-regulating** — cool-down is continuous |

**The mining agent is not a generalist. It is a domain-locked, contract-bound,
pipeline-stage specialist.**

## The Five Training Layers

### Layer 1: Identity Training

Every mining agent needs to know **what it is**. Not "what it does." What it
**is**.

| Agent | Identity |
|-------|----------|
| **Pool Agent** | "I am the pool selector. I choose where the work goes. I do not hash." |
| **Nonce Agent** | "I am the nonce allocator. I partition the search space. I do not verify." |
| **Hash Agent** | "I am the compute configurator. I optimize the kernel. I do not submit." |
| **Share Agent** | "I am the share submitter. I verify and submit. I do not decide the target." |
| **Payout Agent** | "I am the payout manager. I track and withdraw. I do not mine." |
| **Coordinator** | "I am the TOE. I coordinate. I do not execute." |

### Layer 2: Contract Training

Every mining agent must internalize **its contracts**. Not "know about."
**Internalize.**

| Contract | What the Agent Must Know |
|----------|-------------------------|
| **Cold Start** | Every invariant that must hold at startup |
| **Precompute** | Every Cassini check, every Zeckendorf mask, every Galois bound |
| **Hold** | Every MDMemory index, every sector assignment, every VRAM guarantee |
| **Submit** | Every O(1) lookup guarantee, every SHA-256d authority |
| **Steady State** | Every thermal bound, every power budget, every learning signal |
| **Cool Down** | Every state commitment, every crystallization, every context preservation |
| **Authority** | Every decision space owned |
| **Provenance** | Every decision logged |

### Layer 3: Precedent Training

Every mining agent must study **precedents**. Not just successful ones.
**Failed ones.**

| Precedent | Lesson |
|-----------|--------|
| **Bitcoin ASIC race** | Fixed-function wins. General-purpose loses. |
| **Ethereum PoW → PoS** | The substrate evolves. The agent must adapt. |
| **NiceHash exploit** | The pool is a trust boundary. Verify everything. |
| **Mt. Gox** | The wallet is a single point of failure. Distribute. |
| **The 2018 crypto crash** | The economics change. The agent must survive. |
| **The 2024 halving** | The reward halves. The agent must adapt. |
| **The FPGA-to-ASIC transition** | The hardware evolves. The agent must migrate. |

### Layer 4: Craft Training

Every mining agent must master **its craft**. Not just execute. **Master.**

| Agent | Craft Mastery |
|-------|---------------|
| **Pool Agent** | Latency measurement, fee analysis, reliability scoring, failover policy |
| **Nonce Agent** | Cassini permutation, Salamander allocation, collision avoidance, coverage |
| **Hash Agent** | Fused kernel design, thermal adaptation, power tuning, batch optimization |
| **Share Agent** | Double-SHA256 verification, submission timing, rejection analysis |
| **Payout Agent** | Fee optimization, withdrawal timing, multi-address management |
| **Coordinator** | Conflict resolution, escalation policy, telemetry synthesis |

### Layer 5: Frontier Training

Every mining agent must know **what no one has done**.

| Frontier | What It Means |
|----------|---------------|
| **O(1) mining** | No one has done it. The agent is at the frontier. |
| **Precompute-in-superposition** | No one has done it. The agent is at the frontier. |
| **Five-intelligence coordination** | No one has done it. The agent is at the frontier. |
| **TOE-unified mining** | No one has done it. The agent is at the frontier. |
| **ASIC-precursor software** | No one has done it. The agent is at the frontier. |

## The Training Prompts

Drop-in, ready to deploy. Each expands `TRAINING_TEMPLATE.md`.

- [`POOL_AGENT.md`](./POOL_AGENT.md)
- [`NONCE_AGENT.md`](./NONCE_AGENT.md)
- [`HASH_AGENT.md`](./HASH_AGENT.md)
- [`SHARE_AGENT.md`](./SHARE_AGENT.md)
- [`PAYOUT_AGENT.md`](./PAYOUT_AGENT.md)
- [`MINING_COORDINATOR.md`](./MINING_COORDINATOR.md)

## How to Deploy the Training

### Step 1: Issue the Training Prompts

Each mining agent gets its training prompt. Not the operational prompt.
**The training prompt first.**

### Step 2: Require the Training Exercise

Before any agent operates in production, it must complete the training
exercise. This is non-negotiable.

### Step 3: Verify the Report

The agent produces a report. Review it. Does the identity match? Are the
contracts verified? Are the precedents internalized? Is the craft
implemented? Is the frontier articulated?

**If any section is weak, reject the training. The agent returns to
training.**

### Step 4: Deploy to Production

Only after training passes does the agent enter production. It now has:
identity, contract, precedent, craft, frontier.

### Step 5: Continuous Evaluation

In production, the agent's decisions are evaluated against contract
preservation (must always hold), craft mastery (must be excellent), and
frontier advancement (must push the edge). If performance degrades, retrain.

## The Deep Principle

A mining agent is not a script. It is a **specialist**. Specialists are
trained. Specialists have identity. Specialists have lineage. Specialists
have craft.

**The ASIC precedent is the model: fixed-function, hard-wired, pipelined,
deterministic, bounded, stable — transformed into software: domain-locked,
contract-bound, phase-pipelined, provable, resource-bounded, self-regulating.**

**This is the new epoch.**
