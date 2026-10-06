---
name: pythia-agent-fabric
description: Apply the Enterprise agent-fabric pattern to parallel coding work: bounded delegation, explicit ownership, no overlapping mutation scopes, evidence return, and safe fallback when a delegate cannot prove completion.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Agent Fabric

Record use first.

When parallel work is useful:

1. Split by non-overlapping files or architectural responsibilities.
2. Give every delegate:
   - goal;
   - allowed files/scope;
   - forbidden authority changes;
   - acceptance tests;
   - evidence required.
3. No two delegates own the same mutable boundary unless explicitly coordinated.
4. A delegate result is advisory until verified in the shared branch.
5. Merge only after integration tests prove combined behavior.
6. If a delegate cannot prove its result, return to a safe/manual path rather
   than inventing completion.

This skill coordinates work; it does not grant new subsystem authority.
