# Local Agent Execution Handoff

## Overview
This document assigns a local agent the work its existing checkout enables. The local agent must:

1. Fetch the latest `origin/main` without discarding your local work.
2. Read and execute `docs/LOCAL_AGENT_HANDOFF.md`.
3. First reconcile your reported commit `21543c95` with the correct remote and latest `main`, preserving the native-execution and login fixes.
4. Finish checked out on `main`.
5. Execute the assigned local qualification—not another summary—and return:
J01–J08 results
failures
logs
full source SHA

