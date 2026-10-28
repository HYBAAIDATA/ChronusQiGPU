# MCP deployment checklist and troubleshooting

See [tool contracts](../README_MCP.md) and [security procedures](MCP_SECURITY.md).
Production classification is not production-readiness evidence: retain executed,
scoped qualification results before promotion.

## Checklist

- [ ] Use a supported Python (see `requires-python` in `pyproject.toml`) in an
  isolated environment; change directory to the absolute checkout path.
- [ ] Install the checkout using `python -m pip install -e .` and, for validation,
  `python -m pip install -e ".[dev]"`. Use your approved dependency lock/mirror.
  No new runtime dependency is needed for HMAC (`hashlib`, `hmac`, `secrets`
  are standard-library modules).
- [ ] Confirm `Intelligence.lucas_scaler` and its transitive dependencies
  (including NumPy, supplied by the project's dependencies) import. A minimal
  exact-only deployment may intentionally omit the scaler, but must record that
  unavailable capability rather than advertise full intelligence integration.
- [ ] In `.mcp.json`, replace `${REPO_ROOT}` with the absolute checkout path
  according to the host's variable-expansion rules and set that working directory.
  Register `hyba-mcp` as the primary surface. `exact-kernel` is optional stable
  standalone; `cogito` is production-classified and exposes twelve EUCLID/TOE
  capabilities. Verify its initialize handshake and JSON problem adaptation;
  omit any server that has not passed deployment-specific qualification. The
  catalog's status fields do not enforce this.
- [ ] Place the local interface behind the governed MCPGateway/AL HARAS host
  policy; configure tenant identity, authorization, leases and kill-switches
  there. Do not assume the standalone server supplies these controls.
- [ ] Apply process isolation, request/rate/concurrency limits and log retention.
  Keep stdout reserved for JSON-RPC and collect diagnostics from stderr.
- [ ] Configure trusted per-session key custody if packs must remain verifiable
  after close. Do not put keys in `.mcp.json`; use an approved secret manager.
- [ ] Run `python -m pytest tests/test_hyba_mcp.py tests/test_lucas_31_scaler.py -q`.
  Retain results and perform the smoke test below with the deployment interpreter.
- [ ] Check all nine tool definitions, `scale_intelligence`'s availability metadata,
  invalid-input errors, exact Cassini results, signed pack verification, wrong-key
  rejection and gateway authorization denials before promotion.

## Stdio smoke test

From the absolute checkout directory:

```bash
python -m hyba_mcp.server <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"lucas","arguments":{"n":15}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"fibonacci","arguments":{"n":10001}}}
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"scale_intelligence","arguments":{"complexity":0.55}}}
EOF
```

Expect the initialize handshake, nine tools, L15=1364 with a true Cassini
identity check, `-32602` for ID 4, and rung 18 for ID 5 when the scaler is
installed. An unavailable scaler instead returns `-32000`, never fabricated
scale results. For evidence verification after close, execute the example
in the security guide with a trusted key.

## Troubleshooting

| Symptom | Action |
|---|---|
| `No module named hyba_mcp` or `chronus` | Use the installed environment, correct absolute working directory and checkout path; do not copy only `server.py` into a deployment |
| Scaler warning / `_meta["hyba/status"] == "unavailable"` | Check `python -c "from Intelligence.lucas_scaler import LucasIntelligenceScaler"` on the same interpreter; repair missing dependencies and restart. Eight exact tools remain usable |
| Invalid parameter (`-32602`) | Follow `tools/list` schemas: `n` integer 0–10000, complexity finite 0–1, rung and direction enums; do not send numeric strings or booleans |
| Scaling appears not to persist | Expected: each call starts from `target_rung` (default 31); pass the desired starting rung explicitly |
| Pack verification fails | Use the trusted session key and expected session ID, preserve payload values and check canonical JSON. Digest-only legacy packs are not authenticated; never downgrade verification |
| Verification fails after close | Default keys are ephemeral. Verify before close or supply and securely retain a managed key; closed clients intentionally cannot verify using a discarded key |
| Duplicate session start rejected | End the active session and retain its pack before starting another |
| Forbidden call succeeds locally | The raw local interface has no authorization gate; fix host/gateway containment before deployment |
| Experimental tools appear in production | Remove optional catalog entries from the host's actual registration; metadata is not an enforcement switch |

Never address dependency, authorization, or evidence failures by bypassing
AL HARAS, disabling HMAC checks, granting narrow AI authority, or treating
modeled scaling metrics as proof or measured readiness.

## Release evidence and rollback

The `production` manifest status is a registration classification, not a
deployment approval or proof of readiness. Qualification requires the focused
manifest and handshake tests plus deployment-specific host and AL HARAS checks.

- CI workflow: [CI — lint, unit tests, compile](../.github/workflows/ci.yml)
  (the full `tests/` suite includes the Cogito handshake and manifest tests).
- Focused evidence: [`tests/test_cogito_handshake.py`](../tests/test_cogito_handshake.py)
  and [`tests/test_mcp_manifest.py`](../tests/test_mcp_manifest.py).
- CI run for this change: pending; attach the completed PR check-run URL here
  before treating this change as release-qualified.

### Approval record

| Decision | Approver | Date | Evidence |
|---|---|---|---|
| Pending — no deployment approval recorded by this change | Not recorded | Not recorded | Await completed CI check run and deployment-specific qualification |

### Rollback

Revert the change commit (`git revert <commit-sha>`) to restore the prior
repository configuration. If only the deployed MCP configuration must be
restored, reinstate the prior Cogito registration (`status: experimental`,
internal-review-only guidance, and `args: ["mcp/cogito/server.py"]`) from the
previous `.mcp.json`, then restart the MCP host and verify its registered
configuration. Do not treat rollback configuration metadata as an authorization
control.
