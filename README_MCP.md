# HYBA MCP

`hyba_mcp` exposes two capability tiers:

1. **Exact tools** for Lucas/Fibonacci arithmetic, Cassini and Zeckendorf
   certificates, ladder capacity, work tiling, SHA256d verification, and
   stateless scale selection.
2. **Governed skills and repository-context tools** for advisory EUCLID/TOE/
   SALAMANDER capabilities. These have explicit contracts and, for skill
   execution, permission, audit, and bounded-execution gates. Salamander
   diagnosis/proposals are non-actuating; optimization is explicitly enabled,
   lease-gated, budgeted, audited, and advisory-only.

Skill output, a successful identity check, and signed evidence do not grant
theorem, consensus, or execution authority. `theorem_proven` remains `false`.
See [skill reference](docs/SKILLS_REFERENCE.md), [architecture](docs/SKILLS_ARCHITECTURE.md),
[deployment guide](docs/SKILLS_DEPLOYMENT.md), [examples](docs/SKILLS_EXAMPLES.md),
and [security and evidence](docs/MCP_SECURITY.md).

## Trust and deployment boundary

The stdio server is a local process interface, not a remote service, TLS
endpoint, or AL HARAS gateway. Its default control plane has no deployment
authorizer, so skill invocation is denied. Production skill use requires an
embedding with a trusted `identity_provider`, deployment-owned AL HARAS
authorizer, and protected durable audit path; see
[skill deployment](docs/SKILLS_DEPLOYMENT.md). The standalone stdio server does
not configure those deployment credentials or policies.

Opt-in Salamander optimization additionally requires
`HybaMCPServer(salamander_enabled=True)` and a short-lived authority lease.

Run it only from a vetted installation under a least-privilege OS identity.
Do not expose stdio through an unauthenticated network bridge. The MCP host
process is the transport trust boundary; tenant isolation, access leases,
request rate/concurrency/session controls, and protected audit storage remain
deployment responsibilities. The skill sandbox provides bounded execution but
is not an OS filesystem/network namespace. Manifest status markers are guidance,
not containment or readiness certifications.

`HybaMCPClient` calls the local `HybaMCPServer` object directly; it is not a
remote MCP transport client. This qualification covers neither the separate
`mcp/exact_kernel` nor `mcp/cogito` servers, which have independent
implementations.

## Tools and limits

The server advertises exact tools (`lucas`, `fibonacci`, `cassini`,
`zeckendorf`, `ladder_verify`, `ladder_capacity`, `largest_feasible_tile`,
`sha256d_verify`, `scale_intelligence`), context tools (`hyba_context`,
`hyba_verify`), Salamander tools (`salamander_diagnose`, `salamander_propose`,
`salamander_optimise`), and governed skill tools (`discover_skills`, `get_skill`,
`validate_inputs`, `invoke_skill`, `evaluate_skill_outcome`).

Salamander tools require both host opt-in and `"enabled": true`. Diagnosis
accepts explicitly caller-supplied telemetry and reports only homeostasis
breaches (VRAM above 0.85, error rate above 0.1, or throughput below baseline/φ).
Proposals call `SelfRepairEngine.diagnose` only. To obtain an optimization
lease, invoke `security.verify_authority` for `salamander.optimise` with a
duration no longer than 300 seconds; the trusted host identity replaces any
tool-supplied identity. Use the returned `authority_lease.lease_id` with
`salamander_optimise` and its one-step budget. Leases are process-local,
identity-bound, expiring, and single-use. Optimization requires durable audit
storage and is rate-limited; it returns a bounded golden-step recommendation
without applying it. Caller-supplied metric and CUOP values are not certified
measurements, and no Salamander tool changes source, runtime configuration, or
mining behavior.

Inputs are validated before execution. Sequence indices are limited to
0–10,000 inclusive; integer bounds to signed 64-bit values; SHA256d payloads to
1 MiB; task-type strings to 256 characters; and newline-delimited requests to
2 MiB plus protocol overhead. SHA256d compact targets must decode to a positive
uint256 target. Tool argument errors use JSON-RPC `-32602`; unavailable scaler
calls use `-32000`. Notifications do not receive responses.

`scale_intelligence` is stateless: each call creates a new scaler; its default
starting rung is 31. `target_rung` accepts 10, 12, 15, 18, 20, or 31.
`step_direction` accepts `up`, `down`, or `hold`; a step takes precedence over
task adaptation and is clamped at the endpoints. Otherwise, finite
`complexity` in [0,1] and free-form case-insensitive `task_type` matching select
a rung. Complexity thresholds .15/.35/.55/.75/.90 select 10/12/15/18/20/31,
while the highest task-keyword match wins; with both parameters, the higher
demand wins. Response fields such as `context_limit` describe configured
envelopes; `*_after` fields are modeled values, not measurements of
intelligence, consciousness, performance, or theorem completion. See the tool
schema and `scale_intelligence` implementation for exact affinity keywords.

## Run

Install the repository and declared dependencies first (see
[deployment checklist](docs/MCP_DEPLOYMENT.md)). From an installed environment:

```bash
hyba-mcp
# or
python -m hyba_mcp.server
```

The top-level `.mcp.json` uses `${REPO_ROOT}` as a host-specific `PYTHONPATH`
placeholder; configure it for the actual checkout before launching.
The exact-math tools remain available if the optional scaler import fails;
`tools/list` reports scaler availability and an unavailable invocation returns
an explicit error. The root distribution does not define a separate
`hyba-mcp` PyPI distribution.

## Protocol example

Each JSON-RPC message is one newline-delimited JSON object:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"example-client","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"lucas","arguments":{"n":15}}}
```

The server requires initialization before tools/list or tools/call, negotiates
the protocol version, and suppresses notification responses. Invalid tool
arguments return JSON-RPC `-32602`; runtime tool failures return a safe error
without exposing internal exception details.

## Evidence packs

Evidence includes the handshake, tool arguments and outputs, session metadata,
a SHA-256 digest, and HMAC-SHA256 authentication tag. Session IDs use 128 bits
of cryptographic randomness; the default signing key is a private ephemeral
256-bit key. A caller-managed key may be supplied for verification after
session close. Keys are never exported in packs. See
[MCP security](docs/MCP_SECURITY.md) for canonicalization, key management,
replay considerations, and verification.

The HMAC authenticates a client's evidence record; it is not encryption,
non-repudiation, independently attested server execution, or AL HARAS approval.
Evidence can contain sensitive operator data, so apply deployment retention,
encryption-at-rest, and access controls.
