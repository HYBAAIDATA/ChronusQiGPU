# HYBA MCP

`hyba_mcp` is a local, line-oriented stdio MCP server for bounded mathematical
and SHA256d verification tools. It is not a network service, an MCP
authorization gateway, or a mining submission interface.

## Trust and deployment boundary

The server does not implement caller authentication, TLS, AL HARAS leases,
tenant isolation, persistent audit logging, or remote transport. The MCP host
process is the trust boundary: run it only from a vetted installation under a
least-privilege OS identity, and do not expose its stdio through an unauthenticated
network bridge. Tools are calculations and verification only; they do not
submit shares, mutate enterprise data, or grant decision authority.

The separate `MCPGateway` is an application governance component; this stdio
server does not invoke or replace it. The separate `mcp/exact_kernel` and
`mcp/cogito` servers have independent implementations and are not covered by
the production-scope claims or protocol tests in this document.

## Tools

- `lucas`, `fibonacci`, `cassini`, `zeckendorf`
- `ladder_verify`, `ladder_capacity`, `largest_feasible_tile`
- `sha256d_verify` (verification only; no pool interaction)
- `scale_intelligence`

Inputs are validated before execution. Sequence indices are limited to 10,000,
tile and ladder bounds to signed 64-bit integers, SHA256d payloads to 1 MiB,
and task-type strings to 256 characters. The stdio request limit is 2 MiB plus
protocol overhead. Results retain `theorem_proven: false`; a computed witness
is not promoted to a theorem or consensus authority.

## Run

From an installed project environment:

```bash
hyba-mcp
# or
python -m hyba_mcp.server
```

The top-level `.mcp.json` uses `${REPO_ROOT}` as a host-specific `PYTHONPATH`
placeholder; configure it for the actual checkout before launching.

## Protocol example

Each JSON-RPC message is one newline-delimited JSON object. Notifications do
not receive a response.

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"example-client","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"lucas","arguments":{"n":15}}}
```

Tool execution errors use MCP's `isError` result flag; malformed JSON-RPC
requests use JSON-RPC error codes. Internal exception details are not returned
to the client.

## In-process client evidence

`HybaMCPClient` calls the local `HybaMCPServer` object directly; it is not a
remote MCP transport client. Its evidence pack includes the recorded handshake
and tool outputs and carries a SHA-256 integrity digest over canonical JSON.
The digest is not a digital signature, identity assertion, or durable audit
record. `theorem_proven` remains `false`.

The deterministic arithmetic core uses integer operations. `sha256d_verify`
checks the supplied payload and, when requested, the decoded target; it does
not establish pool acceptance or bypass the consensus hash pipeline.
