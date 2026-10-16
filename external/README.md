# external/ — Vendored Third-Party Repositories

This directory holds **vendored copies of external repositories** that are
committed directly into the PhiEnterprise (HYBA / PYTHIA) history rather than
referenced as git submodules. Each vendored tree is kept **byte-exact** to its
upstream so provenance is auditable, and it is excluded from the repo-wide
hygiene gates (see "Gate treatment" below).

The governing declarations that apply to everything under `external/` are in
[`OWNER_DECLARATIONS.md`](../OWNER_DECLARATIONS.md) — in particular **D7**
(implementation authority + independent review; no fabricated capability) and
**PI-01** (executed evidence for readiness claims). Nothing here is a canonical
HYBA capability simply by being present; presence is not a readiness claim.

---

## sample-saas-multi-agents-workshop

**"SmartResolve" — SaaS Multi-Agents Workshop** (Amazon Web Services sample).

| Field | Value |
|-------|-------|
| Upstream | <https://github.com/aws-samples/sample-saas-multi-agents-workshop> |
| Vendored commit | `559fc55e6abfc79cd854ba35af30a7215d19f53e` |
| License | MIT-0 (`LICENSE`) — permissive, no attribution required |
| Integration mode | Vendored in-tree copy (nested `.git` removed); upstream remote `origin` recorded above for traceability |
| Workshop guide | <https://catalog.us-east-1.prod.workshops.aws/workshops/749d2432-98e2-4af5-b8d8-7242395c1925/en-US> |

### What it is

A reference implementation of a **multi-tenant, multi-agent SaaS platform** for
technical-support resolution ("SmartResolve"). It is an **AWS-serverless**
stack — a different product line from the PYTHIA mining/quantum substrate — and
is vendored here as an architectural reference and integration candidate, not
as part of the mining execution plane.

### Technology stack

- **Agents**: [Strands Agents SDK](https://strandsagents.com) (`strands-agents[a2a]`) — Python
- **Models**: Amazon Bedrock (`strands.models.BedrockModel`, Claude Sonnet)
- **Runtime**: Amazon Bedrock AgentCore (`bedrock-agentcore`, `BedrockAgentCoreApp`)
- **MCP**: Model Context Protocol over streamable HTTP (`kb_agent`, `log_agent` tools)
- **Code execution**: AgentCore code interpreter (`bedrock_agentcore.tools.code_interpreter_client`)
- **Infra**: AWS CDK v2 (TypeScript) + a bit of CloudFormation (`cfn/code-editor.yaml`)
- **Data plane**: Amazon Athena (per-tenant log queries), S3, Cognito, cost-per-tenant analytics

### Multi-agent architecture

```
OrchestratorAgent  (agent/orchestrator_agent.py)
├── kb_agent       → Bedrock Knowledge Bases (RAG) via MCP gateway
├── log_agent      → Amazon Athena tenant-log queries via MCP gateway
└── executePython  → AgentCore code interpreter (generate + test fixes)
```

Tenant identity is carried in a JWT (`tenantId` claim, decoded in
`ops_context.decode_jwt_claims`) and enforced by a gateway interceptor +
per-tenant IAM/Athena scoping (the workshop's "Lab 2: tenant isolation").
Token usage is recorded per tenant to CloudWatch Logs
(`metrics_manager.record_metric`) for "Lab 3: cost per tenant".

### Directory layout

```
sample-saas-multi-agents-workshop/
├── agent/                  # Strands multi-agent service (Python)
│   ├── main.py             #   BedrockAgentCoreApp entrypoint + streaming
│   ├── orchestrator_agent.py  #   top-level orchestrator
│   ├── kb_agent.py         #   knowledge-base subagent (MCP → Bedrock KB)
│   ├── log_agent.py        #   log-analysis subagent (MCP → Athena)
│   ├── ops_context.py      #   contextvars request/agent/token state
│   ├── access_token.py     #   token acquisition
│   ├── metrics_manager.py  #   per-tenant CloudWatch metrics
│   ├── streaming_queue.py  #   async streaming buffer
│   ├── wrapped_tool.py, config.py, requirements.txt, Dockerfile, .agentcore.yaml
│   └── constants.py        #   NOT vendored — generated during the workshop labs
│                           #   (KB_MCP_SERVER_URL, LOG_MCP_SERVER_URL, ...)
├── cdk/                    # AWS CDK app (TypeScript)
│   ├── bin/saas-genai-workshop.ts   # ControlPlane + AppPlane + CommonResources + Services stacks
│   ├── lib/                 # stacks + constructs (control-plane, agentcore, athena, cost-per-tenant, tenant-template/*)
│   ├── lambda/              # gateway interceptor, KB/log MCP handlers, kb/s3-vector creators
│   ├── services/            # standalone tenant-onboarding CDK app
│   └── test/                # jest CDK tests
├── cfn/code-editor.yaml    # CloudFormation: dev code-editor environment
├── data/                   # sample tenant inputs (clearpay/, mediops/, cur_report*.zip)
└── scripts/                # install.sh / deploy.sh / cleanup.sh, agent REPL, AgentCore provisioning
```

### How it maps to PhiEnterprise (honest status)

Per **D7 / PI-01**, this is a *reference*, not a wired capability. The overlaps
below are **architectural parallels**, not integrated code paths — no bridge
adapter ships yet, and no readiness is claimed:

| Workshop concept | Closest PhiEnterprise surface | Integration status |
|------------------|-------------------------------|--------------------|
| Strands `Agent` + `BedrockModel` | `integrations/llm_gateway/` (`gateway_config.py` already defaults to `bedrock` / Claude Sonnet) | Parallel; **not connected** |
| Multi-agent orchestration | `pythagoras/agents/orchestrator.py` (`MultiAgentEntangledOrchestrator`), `Intelligence/` orchestrator, `core_engine/multi_agent_execution_graph.py` | Different orchestration model; **not connected** |
| Per-tenant isolation / cost attribution | `aethel/enterprise/custody.py` (tenant custody), control-plane tenant/actor auth (`X-HYBA-Tenant`) | Conceptual parallel; **not connected** |

To actually run the workshop (deploy the CDK app, generate `agent/constants.py`,
build the container) follow the upstream workshop guide — it requires an AWS
account and does not run inside the PYTHIA mining substrate.

### Gate treatment

The vendored tree is excluded from the repo-wide Python hygiene gates, matching
the existing convention for standalone vendored trees (`legacy/`,
`PYTHIA-main/`, `Intelligence/skills/`):

- **`black`** (`pyproject.toml`) — `external` added to the `exclude` regex.
- **`flake8`** (`.flake8`) — `external` added to `exclude`.
- **`import_audit`** (`scripts/import_audit.py`) — `external/` added to `EXCLUDE`
  (the tree's flat sibling imports and the lab-generated `constants.py` do not
  resolve on the consolidated import graph).
- **`.gitignore`** — the repo-wide `data/`, `*.zip`, `*.log` rules are narrowly
  re-included for `external/sample-saas-multi-agents-workshop/` so its sample
  inputs are committed and the tree stays self-contained.
- **`pytest`** — unaffected: `testpaths` in `pyproject.toml` does not include
  `external/`.

---

## Adding another vendored repo

1. Clone it into `external/<name>` and **remove its nested `.git`** so the files
   are tracked by this repo.
2. Record provenance (upstream URL, commit SHA, license) in this README.
3. Add the narrow `.gitignore` re-includes it needs (if any).
4. Add `external` to the `black`/`flake8` excludes and `external/` to the
   import-audit `EXCLUDE` if it is a standalone tree (already done globally).
5. Do **not** claim it is wired into HYBA unless a real, tested adapter exists
   (D7 / PI-01).

