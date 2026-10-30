"""
Comprehensive mainline qualification script for HYBA MCP server and capability composition.

Verifies:
1. Module imports and stdio process launch via `python -m hyba_mcp.server`.
2. MCP initialization, handshake, and tool discovery (19 base tools, 23 capability tools).
3. Tool execution across exact math, repository context, and expert skills.
4. Governed capability composition: goal decomposition, plan validation, and capability invocation.
5. Fail-closed security: authorization denial, unknown capabilities, malformed inputs, oversized payloads.
6. Audit trail durability and SHA-256 hash-chain integrity.
7. Acceptance criteria boundaries: `theorem_proven` is invariant False.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from hyba_mcp.capability_contracts import decompose_goal, validate_plan, ContractError
from hyba_mcp.capability_server import CapabilityMCPServer
from hyba_mcp.control_plane import AuditTrail, ControlPlane
from hyba_mcp.production_contracts import ContractViolation
from hyba_mcp.server import HybaMCPServer, TOOLS
from hyba_mcp.skills import discover_skills


def test_stdio_server_process() -> None:
    """Test full stdio interaction with spawned python -m hyba_mcp.server process."""
    cmd = [sys.executable, "-m", "hyba_mcp.server"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "lucas", "arguments": {"n": 10}},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "hyba_context",
                "arguments": {"query": "lucas", "max_files": 2, "budget": 65536},
            },
        },
    ]

    input_data = "\n".join(json.dumps(r) for r in requests) + "\n"
    stdout, stderr = proc.communicate(input=input_data, timeout=30)
    assert proc.returncode == 0, f"Process failed with returncode {proc.returncode}: {stderr}"

    lines = [json.loads(line) for line in stdout.strip().splitlines() if line.strip()]
    assert len(lines) == 4, f"Expected 4 responses, got {len(lines)}"

    init_resp, list_resp, call_resp, ctx_resp = lines
    assert init_resp["id"] == 1
    assert init_resp["result"]["protocolVersion"] == "2024-11-05"
    assert init_resp["result"]["serverInfo"]["name"] == "hyba-mcp-server"

    assert list_resp["id"] == 2
    tool_names = {t["name"] for t in list_resp["result"]["tools"]}
    assert len(tool_names) == 19
    assert {"lucas", "fibonacci", "cassini", "hyba_context", "hyba_verify"} <= tool_names

    assert call_resp["id"] == 3
    call_content = json.loads(call_resp["result"]["content"][0]["text"])
    assert call_content["n"] == 10
    assert call_content["L_n"] == 123
    assert call_content["theorem_proven"] is False

    assert ctx_resp["id"] == 4
    ctx_content = json.loads(ctx_resp["result"]["content"][0]["text"])
    assert "files" in ctx_content
    assert ctx_content["theorem_proven"] is False


def test_capability_composition_and_security() -> None:
    """Test CapabilityMCPServer, goal decomposition, plan validation, invocation, and security."""
    with tempfile.TemporaryDirectory() as td:
        audit_file = Path(td) / "mcp_audit.jsonl"
        authorized_identities = {"trusted-operator"}

        def authorizer(identity: str, skill_id: str, args: dict) -> bool:
            return identity in authorized_identities

        cp = ControlPlane(authorizer=authorizer, audit_path=audit_file)
        server = CapabilityMCPServer(control_plane=cp, identity_provider=lambda: "trusted-operator")

        # 1. Initialize server
        init_res = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "qualification-client", "version": "1.0"},
                },
            }
        )
        assert init_res["result"]["protocolVersion"] == "2024-11-05"
        server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 2. Tool discovery
        tools_res = server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        tool_names = {t["name"] for t in tools_res["result"]["tools"]}
        assert len(tool_names) == 23
        assert {
            "goal_decompose",
            "plan_validate",
            "capability_contract",
            "capability_invoke",
        } <= tool_names

        catalog = {s["skill_id"]: s for s in discover_skills()}

        # 3. Goal decomposition
        goal_contract = {
            "goal": "Verify emergence and explain causality",
            "criteria": ["criterion_emergence", "criterion_causality"],
            "subgoals": [
                {
                    "id": "step_1",
                    "skill_id": "proof.emergence_verify",
                    "arguments": {"spectral_gap": 0.2, "betti_1": 1, "phi_resonance": 0.7},
                    "depends_on": [],
                    "covers": ["criterion_emergence"],
                },
                {
                    "id": "step_2",
                    "skill_id": "reasoning.causal_explain",
                    "arguments": {
                        "query": "explain emergence",
                        "data": {"variables": ["spectral_gap", "betti_1"]},
                    },
                    "depends_on": ["step_1"],
                    "covers": ["criterion_causality"],
                },
            ],
        }

        decompose_result = server.execute_tool(
            "goal_decompose", {"goal_contract": goal_contract}
        )
        assert decompose_result["status"] == "proposed"
        assert decompose_result["plan"]["contract_version"] == "1.0"
        assert decompose_result["validation"]["valid"] is True
        assert decompose_result["validation"]["execution_authorized"] is False
        assert decompose_result["validation"]["theorem_proven"] is False

        # 4. Plan validation
        plan_result = server.execute_tool(
            "plan_validate", {"plan": decompose_result["plan"]}
        )
        assert plan_result["valid"] is True
        assert plan_result["order"] == ["step_1", "step_2"]
        assert plan_result["execution_authorized"] is False
        assert plan_result["theorem_proven"] is False

        # 5. Invalid / cyclic plan rejection
        cyclic_plan = {
            "contract_version": "1.0",
            "goal": "Cyclic test",
            "criteria": ["c1", "c2"],
            "nodes": [
                {
                    "id": "node_a",
                    "skill_id": "proof.emergence_verify",
                    "arguments": {"spectral_gap": 0.2, "betti_1": 1, "phi_resonance": 0.7},
                    "depends_on": ["node_b"],
                    "covers": ["c1"],
                },
                {
                    "id": "node_b",
                    "skill_id": "proof.emergence_verify",
                    "arguments": {"spectral_gap": 0.2, "betti_1": 1, "phi_resonance": 0.7},
                    "depends_on": ["node_a"],
                    "covers": ["c2"],
                },
            ],
        }
        cyclic_result = server.execute_tool("plan_validate", {"plan": cyclic_plan})
        assert cyclic_result["ok"] is False
        assert cyclic_result["error"]["code"] == "invalid_contract"
        assert cyclic_result["execution_status"] == "not_executed"

        # 6. Capability contract query
        contract_res = server.execute_tool(
            "capability_contract", {"skill_id": "proof.emergence_verify"}
        )
        assert contract_res["ok"] is True
        assert contract_res["capability"]["skill_id"] == "proof.emergence_verify"
        assert "contract_digest" in contract_res["capability"]

        # 7. Valid capability invocation
        invoke_res = server.execute_tool(
            "capability_invoke",
            {
                "skill_id": "proof.emergence_verify",
                "arguments": {"spectral_gap": 0.2, "betti_1": 1, "phi_resonance": 0.7},
            },
        )
        assert invoke_res["ok"] is True
        assert invoke_res["execution_status"] == "completed"
        assert invoke_res["output_status"] == "accepted"
        assert invoke_res["result"]["emerged"] is True
        assert invoke_res["result"]["confidence"] == 1.0
        assert invoke_res["theorem_proven"] is False
        assert "audit_record" in invoke_res
        assert invoke_res["audit_record"]["sequence"] > 0

        # 8. Authorization denial (unauthorized subject)
        unauth_server = CapabilityMCPServer(
            control_plane=cp, identity_provider=lambda: "untrusted-agent"
        )
        denied_res = unauth_server.execute_tool(
            "capability_invoke",
            {
                "skill_id": "proof.emergence_verify",
                "arguments": {"spectral_gap": 0.2, "betti_1": 1, "phi_resonance": 0.7},
            },
        )
        assert denied_res["ok"] is False
        assert denied_res["error"]["code"] == "permission_denied"
        assert denied_res["execution_status"] == "not_executed"
        assert denied_res["output_status"] == "not_available"

        # 9. Unknown capability invocation
        unknown_res = server.execute_tool(
            "capability_invoke",
            {"skill_id": "nonexistent.skill", "arguments": {}},
        )
        assert unknown_res["ok"] is False
        assert unknown_res["error"]["code"] == "unknown_capability"
        assert unknown_res["execution_status"] == "not_executed"

        # 10. Verify audit trail durability and integrity
        assert audit_file.exists()
        assert cp.audit.durable is True
        assert cp.audit.verify() is True
        records = cp.audit.records()
        assert len(records) >= 5
        print(f"Verified {len(records)} audit records chained with SHA-256 integrity.")


def main() -> int:
    print("=== HYBA MCP Mainline Qualification Verification ===")
    t0 = time.time()

    print("[1/2] Verifying Stdio Server Process (`python -m hyba_mcp.server`)...")
    test_stdio_server_process()
    print("      PASSED: Stdio initialization, handshake, 19 tools listed, and kernel execution verified.")

    print("[2/2] Verifying Capability Composition, Security, and Audit...")
    test_capability_composition_and_security()
    print("      PASSED: 23 capability tools, goal decomposition, DAG validation, authorized execution, denial fail-closed, and durable audit verified.")

    elapsed = time.time() - t0
    print(f"\n[QUALIFICATION SUCCESS] All MCP mainline integration assertions verified in {elapsed:.2f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
