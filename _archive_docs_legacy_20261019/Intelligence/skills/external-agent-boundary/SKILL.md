---
name: external-agent-boundary
description: Policy-gated execution and evaluation boundary for external engineering, coding, and reasoning agent candidate patches.
version: 1.0.0
tags: [adapter, boundary, security, policy, confinement]
---

# External Engineering-Agent Boundary Skill

> **Foundational Axiom Anchor:** Governed by [`OWNER_DECLARATIONS.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/OWNER_DECLARATIONS.md) and [`AGENTS.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/AGENTS.md).
>
> **Zero-Trust Candidate Invariant:** All outputs from external engineering agents are treated as untrusted candidate output. An external agent claiming success is untrusted; success is determined solely by external deterministic verification, AST validation, reproduction probes, and regression tests.

---

## 1. Overview & Operational Contract

The `external-agent-boundary` capability mediates interaction between Euclid / Salamander and external coding or reasoning providers (e.g. Anthropic Claude, OpenAI, local models, or deterministic testing adapters).

It enforces:
1. **Scope and Confinement:** Restricts file access strictly to configured relative roots (`allowed_repo_relative_roots`). Denies directory traversals (`..`), absolute paths, and protected repository scopes (`AGENTS.md`, `OWNER_DECLARATIONS.md`, `.git/`, `tests/authority/`).
2. **Resource Boundaries:** Hard limits on total patch bytes and files modified per candidate.
3. **AST / Syntax Gates:** Blocks Python code containing syntax errors from admission.
4. **Independent Regression Gate:** Candidate must pass independent verification callbacks before publication.
5. **Cryptographic Receipt Custody:** Produces an immutable, tamper-evident audit receipt binding task digest, candidate digest, policy verdict, and timestamp.

---

## 2. Usage

Dispatch via `SalamanderEngine.execute_capability`:

```python
engine = SalamanderEngine()
result, receipt = engine.execute_capability(
    "external-agent-boundary",
    task={
        "task_id": "repair_task_001",
        "task_type": "code_patch",
        "instruction": "Fix memory leak in buffer",
        "policy": {
            "allowed_repo_relative_roots": ["chronus/"],
            "max_patch_bytes": 65536,
            "max_files_modified": 3,
        },
    },
    candidate={
        "task_id": "repair_task_001",
        "provider": {
            "provider_id": "anthropic_claude",
            "model_name": "claude-3-7-sonnet",
            "model_version": "20261001",
        },
        "proposed_files": {
            "chronus/buffer.py": "# fixed code\n",
        },
        "raw_response": "Patch generated",
        "claimed_success": True,  # Ignored for verification!
    },
)

assert result["verdict"] == "ADMITTED"
assert receipt.status == "SUCCESS"
```
