# Fresh native HYBA + Cogito benchmark

Reusable protocol for the HYBA 11 + Cogito 12 benchmark after the Cogito JSON
input fix. This measures the tools exposed to a fresh cloud-agent session; it is
not a local server or source-code benchmark.

## Run constraints

1. Start a **new cloud-agent session** with no prior conversation or local MCP
   substitute. Record the session/run identifier and UTC start time.
2. Use the agent host's native MCP controls to start `hyba-mcp-server` and
   `cogito`. Do not launch either with a shell command, call their stdio
   protocols directly, use `HybaMCPClient`, or infer tool availability from
   source files.
3. If a native server cannot be started, its tools are absent, or the host does
   not expose its usage credits, record that item as `UNSEEN` and why. Lack of
   access is not a test failure; do not substitute a local run.
4. Start the wall-clock timer immediately before starting the first server and
   stop it after the last benchmark call. Record the host-reported credits for
   this fresh session; do not estimate credits from tokens or elapsed time.

## Calls and observations

1. Start `hyba-mcp-server`, then record the total tools in its native tool list
   and the observed names. The requested HYBA count is 11; report the count
   actually exposed rather than forcing it to 11. This distinction matters:
   the source registry currently has 9 math/scale tools, 5 skill tools, and 2
   context tools, so source inspection is not evidence of the native count.
2. Call HYBA `lucas` with `{"n":10}`. Preserve the exact response and verify
   `n=10`, `L_n=123`, `F_n=55`, `cassini_holds=true`, `left=4`, and `right=4`.
   `theorem_proven` remains `false`; an exact identity check is not a theorem
   claim.
3. Start `cogito`, then record the total tools in its native tool list and the
   observed names. The requested Cogito count is 12.
4. Call Cogito `represent` with the JSON object
   `{"problem":{"domain":"benchmark","observation":[1,2,3]}}`. Preserve the
   returned envelope verbatim. Check `capability="represent"`, a
   `truth_class` of `ACT`, `ACQUIRE_EVIDENCE`, or `REFUSED`, 64-character
   problem and result digests under `evidence`, and `theorem_proven=false`.
   Do not flatten or paraphrase the envelope.

## Report template

```text
Status: UNSEEN
Session: <fresh cloud-agent run ID, or UNSEEN>
Started at (UTC): <timestamp, or UNSEEN>
HYBA native start: <started / UNSEEN + reason>
HYBA native tools: <observed count and names, or UNSEEN>
HYBA lucas n=10: <verbatim response, or UNSEEN>
Cogito native start: <started / UNSEEN + reason>
Cogito native tools: <observed count and names, or UNSEEN>
Cogito represent: <verbatim truth envelope, or UNSEEN>
Duration: <measured wall time, or UNSEEN>
Credits: <host-reported amount and unit, or UNSEEN>
```

Set overall status to `OBSERVED` only when both native servers, both native
tool inventories, both calls, duration, and host-reported credits are captured.
Otherwise retain `UNSEEN` and identify each missing observation; do not label
missing native evidence `FAIL`.

The JSON `represent` regression is covered by
`tests/test_cogito_handshake.py`; exact HYBA anchors are covered by
`tests/test_hyba_mcp.py`.
