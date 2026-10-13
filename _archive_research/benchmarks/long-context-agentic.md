# Long‑Context & Agentic Benchmark

This benchmark suite measures HYBA’s impact on the two workload classes that are now the primary drivers of AI infrastructure cost:

- **Long‑context LLM inference** (128K–1M+ tokens)  
- **Agentic sessions** (multi‑step reasoning, retrieval, tool use, long‑lived context)

Both are **memory‑bound and bandwidth‑bound**, not compute‑bound.  
The folded‑state architecture in HYBA is designed specifically to reduce the HBM capacity, bandwidth, and duplication taxes that dominate these workloads.

---

## A. Long‑context LLM decode benchmark

**Model:** 70B‑class transformer (example)  
**Context lengths:** 128K, 256K, 1M tokens  
**Concurrency:** 256 sessions  
**Metric focus:** HBM usage, bandwidth, tokens/sec, cost per 1M tokens, intelligence per byte

| Context | Architecture   | KV footprint / session | Total HBM (KV only) | HBM utilisation | Tokens/sec (per GPU) | Bandwidth / token | Cost per 1M tokens (infra) | Intelligence per Byte (IPB) |
|--------:|----------------|------------------------|---------------------|-----------------|----------------------|-------------------|----------------------------|-----------------------------|
| 128K    | Raw (FP16)     | 43 GB                  | 11.0 TB             | 92%             | 1,850                | 344 GB            | $2.10                      | 0.48 tasks/GB‑h             |
| 128K    | HYBA folded    | 4.2 GB                 | 1.1 TB              | 38%             | 2,900                | 42 GB             | $0.95                      | 1.85 tasks/GB‑h             |
| 256K    | Raw (FP16)     | 86 GB                  | 22.0 TB             | >100% (OOM)     | 920                  | 688 GB            | $4.30                      | 0.22 tasks/GB‑h             |
| 256K    | HYBA folded    | 8.4 GB                 | 2.1 TB              | 55%             | 2,400                | 84 GB             | $1.10                      | 1.60 tasks/GB‑h             |
| 1M      | Raw (FP16)     | 344 GB                 | 88.0 TB             | OOM             | –                    | 2.75 TB           | –                          | –                           |
| 1M      | HYBA folded    | 34 GB                  | 8.7 TB              | 68%             | 1,600                | 340 GB            | $1.80                      | 1.20 tasks/GB‑h             |

**Notes**

- Numbers are illustrative; replace with real pilot data.  
- “HBM utilisation” is for a fixed GPU cluster (e.g. 12 TB total HBM).  
- “Cost per 1M tokens” is infrastructure cost (capex + power + cooling amortised), not API price.  
- IPB is defined as “completed decode tasks per GB‑hour of HBM”.

**Interpretation**

- HYBA folded KV enables **1M‑token contexts** on hardware that OOMs in the raw path.  
- At 256K, HYBA delivers **~2.6× more tokens/sec** while using **~10× less HBM** for KV.  
- **Cost per 1M tokens** drops by **~55–60%** in this example.  
- **IPB** increases by **3–7×**, showing more intelligence per byte of memory.

---

## B. Agentic session benchmark

**Agent type:** Multi‑step reasoning + retrieval + tool use  
**Session length:** 50 steps average  
**Context per session:** 200K tokens (history + retrieved docs + tool traces)  
**Concurrency:** 1,000 concurrent agent sessions  
**Metric focus:** end‑to‑end latency, HBM/DRAM footprint, cost per 1,000 agent sessions

| Architecture   | Context footprint / session | Total memory (active sessions) | End‑to‑end latency (p50) | End‑to‑end latency (p95) | Cost per 1,000 sessions | Intelligence per Byte (IPB) |
|----------------|-----------------------------|--------------------------------|--------------------------|--------------------------|-------------------------|-----------------------------|
| Raw (FP16)     | 200 GB                      | 200 TB                         | 4.8 s                    | 9.2 s                    | $18.50                  | 0.55 sessions/GB‑h          |
| HYBA folded    | 18 GB                       | 18 TB                          | 3.1 s                    | 5.6 s                    | $6.20                   | 2.90 sessions/GB‑h          |

**Notes**

- “Context footprint” includes history, retrieved chunks, and tool traces in active memory.  
- “Total memory” is for 1,000 concurrent sessions.  
- “Cost per 1,000 sessions” is amortised infra cost (compute + memory + networking).  
- IPB is “completed agent sessions per GB‑hour”.

**Interpretation**

- HYBA reduces **active memory per agent session by ~10×** in this example.  
- **p50 latency** improves by ~35%, **p95** by ~40%, due to reduced movement and better cache behaviour.  
- **Cost per 1,000 sessions** drops by ~66%.  
- **IPB** increases by **~5×**, again showing more intelligence per byte.

---

## Relation to Golden Fold and CIaaS

These long‑context and agentic benchmarks are direct applications of HYBA’s **Computational Intelligence as a Service** thesis.

- The same **Golden Fold** principles (invertible, coherence‑amplifying transforms) measured in the Golden Fold Benchmark are now applied to **KV cache and agent memory**.  
- Task‑level metrics (latency, cost, intelligence per byte) show the **economic impact** of folded‑state operation.  
- This is the infrastructure layer that makes long‑context and agentic AI **economically sustainable at scale**.
