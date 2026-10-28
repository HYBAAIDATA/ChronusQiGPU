# Expert skills deployment

## Authorization and audit

Embed `HybaMCPServer` with a `ControlPlane` configured with:

1. A deployment-owned AL HARAS authorizer callback that checks the verified
   caller identity, requested skill capability, tenant/lease context, and
   current policy. The callback must return an explicit `True` or an
   `allowed` verdict; exceptions and ambiguous values deny.
2. A protected `audit_path` on durable storage. The server verifies an existing
   hash chain during startup and synchronously appends and fsyncs decisions and
   outcomes. File access, encryption-at-rest, backup, access review, and
   retention/deletion policy belong to the deployment.
3. Unique authenticated caller identities. Do not accept `identity` from an
   untrusted tool argument as authentication; bind it from the MCP host's
   trusted session context with `identity_provider`. Without that provider,
   MCP skill invocation is denied even if tool options contain an identity.

```python
from hyba_mcp.control_plane import ControlPlane
from hyba_mcp.server import HybaMCPServer

control_plane = ControlPlane(
    authorizer=your_al_haras_adapter,
    audit_path="/var/lib/hyba-mcp/skill-audit.jsonl",
)
server = HybaMCPServer(control_plane=control_plane)
```

In an authenticated host, inject a provider that reads the verified session
context; never derive its result from MCP tool arguments:

```python
server = HybaMCPServer(
    control_plane=control_plane,
    identity_provider=authenticated_host.current_identity,
)
```

The checked-in standalone stdio entrypoint intentionally has no credentials or
AL HARAS policy configured; consequently it denies skill execution. Configure
the control plane in a trusted embedding before enabling invocation.

## Resource policy

The sandbox defaults to a 30-second wall-clock timeout, 15 CPU seconds, 2 GiB
address-space cap, and 1 MiB request/response payload caps. Tune these limits
for the deployment host and skill workload. POSIX resource limits are required;
unsupported platforms fail closed. Skill calls are not arbitrary code execution
and do not constitute an OS-level filesystem/network namespace.

## Release and package status

The MCP module reports version `2.0.0` and is included in the repository's
existing setuptools package inventory. The root distribution remains
`hyba-pythia-mining` version `1.0.0`; this repository does not define a separate
`hyba-mcp` PyPI distribution. A separately publishable `hyba-mcp>=2.0.0`
artifact needs its own packaging/release metadata and dependency boundary.

Before production promotion, run the focused MCP tests and the deployment's
AL HARAS integration and durable-audit qualification. Passing unit tests do not
certify authorization policy, retained audit durability, or cross-platform
sandbox containment.
