"""Experiment checks for the TURING MCP wrapper."""

from __future__ import annotations

import io
import json
import math
import unittest

from hyba_mcp.adapter import (
    BASIS_CONVENTION,
    TuringAdapter,
    build_operator,
    embed_operator,
    parse_circuit,
    reversed_cnot,
    rotation,
    run_circuit,
    swap_2,
)
from hyba_mcp.client import connect
from hyba_mcp.server import TOOLS, HybaMCPServer, TuringMCPServer, run_server
from turing import (
    CNOT,
    HADAMARD,
    IDENTITY_2,
    PAULI_X,
    PAULI_Z,
    LinearOperator,
    QuantumState,
    tensor_operators,
)
import pytest

pytestmark = pytest.mark.real


def _bell():
    return {
        "n_qubits": 2,
        "gates": [
            {"name": "H", "qubits": [0]},
            {"name": "CNOT", "qubits": [0, 1]},
        ],
    }


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = TuringAdapter()

    def test_backend_list_is_maths_only(self):
        listed = self.adapter.list_backends()
        self.assertEqual([item["id"] for item in listed["backends"]], ["statevector"])
        self.assertFalse(listed["backends"][0]["hardware"])
        self.assertFalse(listed["backends"][0]["sampling"])
        self.assertEqual(listed["not_implemented"], ["density", "qpu"])
        self.assertEqual(listed["basis_convention"], BASIS_CONVENTION)

    def test_bell_probabilities_match_born_rule(self):
        spec = _bell()
        spec["observables"] = ["ZZ", "XX"]
        result = self.adapter.execute_circuit(spec)
        self.assertTrue(result["executed"])
        self.assertTrue(result["exact"])
        self.assertEqual(result["build"], "dense_operator")
        probabilities = result["state"]["probabilities"]
        self.assertAlmostEqual(probabilities[0], 0.5)
        self.assertAlmostEqual(probabilities[1], 0.0)
        self.assertAlmostEqual(probabilities[2], 0.0)
        self.assertAlmostEqual(probabilities[3], 0.5)
        self.assertTrue(result["unitarity"]["dense_check"])
        self.assertTrue(result["unitarity"]["ok"])
        by_name = {item["observable"]: item for item in result["expectations"]}
        self.assertAlmostEqual(by_name["ZZ"]["expectation"]["re"], 1.0, places=10)
        self.assertAlmostEqual(by_name["XX"]["expectation"]["re"], 1.0, places=10)
        psi = build_operator(parse_circuit(spec)).apply(QuantumState.basis(4, 0))
        for text, factors in (("ZZ", (PAULI_Z, PAULI_Z)), ("XX", (PAULI_X, PAULI_X))):
            value = tensor_operators(*factors).expectation_value(psi)
            self.assertAlmostEqual(by_name[text]["expectation"]["re"], value.real, places=10)
            self.assertAlmostEqual(by_name[text]["expectation"]["im"], value.imag, places=10)

    def test_sequential_apply_matches_dense_operator(self):
        spec = {
            "n_qubits": 3,
            "gates": [
                {"name": "H", "qubits": [0]},
                {"name": "CNOT", "qubits": [0, 2]},
                {"name": "RY", "qubits": [1], "theta": math.pi / 2},
                {"name": "S", "qubits": [2]},
            ],
        }
        circuit = parse_circuit(spec)
        operator = build_operator(circuit)
        from_matrix = operator.apply(QuantumState.basis(8, 0))
        mode, from_sequence, built = run_circuit(circuit)
        self.assertEqual(mode, "dense_operator")
        self.assertTrue(built.almost_equal(operator))
        for left, right in zip(from_matrix.amplitudes, from_sequence.amplitudes):
            self.assertAlmostEqual(left.real, right.real)
            self.assertAlmostEqual(left.imag, right.imag)
        self.assertTrue(operator.is_unitary())

    def test_adjacent_cnot_is_turing_cnot(self):
        embedded = embed_operator(2, {"name": "CNOT", "qubits": (0, 1), "operator": None})
        self.assertIs(embedded, CNOT)
        built = build_operator(
            parse_circuit({"n_qubits": 2, "gates": [{"name": "CNOT", "qubits": [0, 1]}]})
        )
        self.assertTrue(built.almost_equal(CNOT))
        self.assertTrue(built.almost_equal(tensor_operators(CNOT)))
        reversed_gate = reversed_cnot()
        self.assertAlmostEqual(abs(reversed_gate.apply(QuantumState.basis(4, 1)).amplitudes[3]), 1.0)
        self.assertAlmostEqual(abs(reversed_gate.apply(QuantumState.basis(4, 2)).amplitudes[2]), 1.0)
        swapped = swap_2().apply(QuantumState.basis(4, 1))
        self.assertAlmostEqual(abs(swapped.amplitudes[2]), 1.0)

    def test_qubit0_is_the_most_significant_tensor_factor(self):
        embedded = embed_operator(
            2,
            {"name": "X", "qubits": (0,), "operator": PAULI_X},
        )
        reference = tensor_operators(PAULI_X, IDENTITY_2)
        self.assertTrue(embedded.almost_equal(reference))
        psi = reference.apply(QuantumState.basis(4, 0))
        self.assertAlmostEqual(abs(psi.amplitudes[2]), 1.0)
        self.assertAlmostEqual(abs(psi.amplitudes[1]), 0.0)

    def test_nonadjacent_cnot_matches_turing_swap_conjugation(self):
        both = tensor_operators(HADAMARD, HADAMARD)
        reversed_gate = both.compose(CNOT.compose(both))
        swap = CNOT.compose(reversed_gate.compose(CNOT))
        self.assertTrue(reversed_cnot().almost_equal(reversed_gate))
        self.assertTrue(swap_2().almost_equal(swap))
        swap_embed = tensor_operators(IDENTITY_2, swap)
        adjacent = tensor_operators(CNOT, IDENTITY_2)
        reference = swap_embed.compose(adjacent.compose(swap_embed))
        built = embed_operator(3, {"name": "CNOT", "qubits": (0, 2), "operator": None})
        self.assertTrue(built.almost_equal(reference))
        flipped = built.apply(QuantumState.basis(8, 4))
        self.assertAlmostEqual(abs(flipped.amplitudes[5]), 1.0)
        spec = {
            "n_qubits": 3,
            "gates": [
                {"name": "H", "qubits": [0]},
                {"name": "CNOT", "qubits": [0, 2]},
            ],
            "observables": ["ZIZ"],
        }
        result = self.adapter.execute_circuit(spec)
        self.assertAlmostEqual(result["state"]["probabilities"][0], 0.5)
        self.assertAlmostEqual(result["state"]["probabilities"][5], 0.5)
        observable = tensor_operators(PAULI_Z, IDENTITY_2, PAULI_Z)
        psi = build_operator(parse_circuit(spec)).apply(QuantumState.basis(8, 0))
        value = observable.expectation_value(psi)
        self.assertAlmostEqual(result["expectations"][0]["expectation"]["re"], value.real, places=10)
        self.assertAlmostEqual(value.real, 1.0, places=10)

    def test_rotations_use_operator_expectation(self):
        rx_gate = rotation("RX", math.pi)
        ry_gate = rotation("RY", math.pi / 2)
        rz_gate = rotation("RZ", math.pi / 2)
        rx = embed_operator(1, {"name": "RX", "qubits": (0,), "operator": rx_gate})
        ry = embed_operator(2, {"name": "RY", "qubits": (1,), "operator": ry_gate})
        rz = embed_operator(1, {"name": "RZ", "qubits": (0,), "operator": rz_gate})
        self.assertTrue(ry.almost_equal(tensor_operators(IDENTITY_2, ry_gate)))
        rx_state = rx.apply(QuantumState.basis(2, 0))
        ry_state = ry.apply(QuantumState.basis(4, 0))
        rz_state = rz.apply(QuantumState.basis(2, 0))
        self.assertAlmostEqual(PAULI_Z.expectation_value(rx_state).real, -1.0, places=10)
        ry_expectation = tensor_operators(IDENTITY_2, PAULI_X).expectation_value(ry_state)
        rx_result = self.adapter.execute_circuit(
            {
                "n_qubits": 1,
                "gates": [{"name": "RX", "qubits": [0], "theta": math.pi}],
                "observables": ["Z"],
            }
        )
        ry_result = self.adapter.execute_circuit(
            {
                "n_qubits": 2,
                "gates": [{"name": "RY", "qubits": [1], "theta": math.pi / 2}],
                "observables": ["IX"],
            }
        )
        rz_result = self.adapter.execute_circuit(
            {
                "n_qubits": 1,
                "gates": [{"name": "RZ", "qubits": [0], "theta": math.pi / 2}],
                "observables": ["Z"],
            }
        )
        self.assertAlmostEqual(
            rx_result["expectations"][0]["expectation"]["re"],
            PAULI_Z.expectation_value(rx_state).real,
            places=10,
        )
        self.assertAlmostEqual(
            ry_result["expectations"][0]["expectation"]["re"],
            ry_expectation.real,
            places=10,
        )
        self.assertAlmostEqual(ry_expectation.real, 1.0, places=10)
        self.assertAlmostEqual(
            rz_result["expectations"][0]["expectation"]["re"],
            PAULI_Z.expectation_value(rz_state).real,
            places=10,
        )
        self.assertTrue(rx.is_unitary() and ry.is_unitary() and rz.is_unitary())

    def test_pauli_expectation_on_computational_and_plus_states(self):
        zero = self.adapter.compute_expectation(
            {"n_qubits": 1, "gates": []},
            "Z",
        )
        one = self.adapter.compute_expectation(
            {"n_qubits": 1, "gates": [{"name": "X", "qubits": [0]}]},
            "Z",
        )
        plus = self.adapter.compute_expectation(
            {"n_qubits": 1, "gates": [{"name": "H", "qubits": [0]}]},
            "Z",
        )
        rx = self.adapter.compute_expectation(
            {"n_qubits": 1, "gates": [{"name": "RX", "qubits": [0], "theta": math.pi}]},
            "Z",
        )
        self.assertAlmostEqual(zero["expectation"]["re"], 1.0)
        self.assertAlmostEqual(one["expectation"]["re"], -1.0)
        self.assertAlmostEqual(plus["expectation"]["re"], 0.0, places=10)
        self.assertAlmostEqual(rx["expectation"]["re"], -1.0, places=10)
        self.assertTrue(zero["hermitian"])

    def test_ry_prepares_plus(self):
        result = self.adapter.execute_circuit(
            {
                "n_qubits": 1,
                "gates": [{"name": "RY", "qubits": [0], "theta": math.pi / 2}],
            }
        )
        probabilities = result["state"]["probabilities"]
        self.assertAlmostEqual(probabilities[0], 0.5)
        self.assertAlmostEqual(probabilities[1], 0.5)

    def test_above_dense_limit_applies_each_embedded_operator(self):
        reference = tensor_operators(
            IDENTITY_2, IDENTITY_2, IDENTITY_2, HADAMARD, IDENTITY_2, IDENTITY_2, IDENTITY_2
        )
        embedded = embed_operator(7, {"name": "H", "qubits": (3,), "operator": HADAMARD})
        self.assertTrue(embedded.almost_equal(reference))
        psi = reference.apply(QuantumState.basis(128, 0))
        result = self.adapter.execute_circuit(
            {
                "n_qubits": 7,
                "gates": [{"name": "H", "qubits": [3]}],
                "observables": ["IIIZIII"],
            },
            include_amplitudes=False,
        )
        self.assertEqual(result["build"], "sequential_gate_apply")
        self.assertFalse(result["unitarity"]["dense_check"])
        self.assertNotIn("amplitudes", result["state"])
        self.assertAlmostEqual(result["state"]["probabilities"][0], abs(psi.amplitudes[0]) ** 2)
        self.assertAlmostEqual(result["state"]["probabilities"][8], abs(psi.amplitudes[8]) ** 2)
        value = tensor_operators(
            IDENTITY_2, IDENTITY_2, IDENTITY_2, PAULI_Z, IDENTITY_2, IDENTITY_2, IDENTITY_2
        ).expectation_value(psi)
        self.assertAlmostEqual(result["expectations"][0]["expectation"]["re"], value.real, places=10)

    def test_policy_denies_hardware_density_and_oversized_registers(self):
        spec = {"n_qubits": 2, "gates": []}
        for backend in ("qpu:local", "density", "vendor"):
            denied = self.adapter.execute_circuit(spec, backend=backend)
            self.assertEqual(denied["decision"], "deny")
            self.assertFalse(denied["executed"])
            self.assertNotIn("state", denied)
        oversized = self.adapter.validate_math({"n_qubits": 20, "gates": []})
        self.assertEqual(oversized["decision"], "deny")
        self.assertFalse(oversized["execute_allowed"])
        self.assertEqual(oversized["memory"]["statevector_complex_amplitudes"], 1 << 20)
        self.assertNotIn("dense_operator_entries", oversized["memory"])

    def test_malformed_spec_is_a_tool_input_error(self):
        with self.assertRaises(Exception):
            self.adapter.execute_circuit(
                {"n_qubits": 2, "gates": [{"name": "CNOT", "qubits": [0, 0]}]}
            )
        with self.assertRaises(Exception):
            self.adapter.execute_circuit(
                {"n_qubits": 1, "gates": [{"name": "H", "qubits": [0], "theta": 1}]}
            )

    def test_wrapper_source_has_no_vendor_sdk_or_qasm_parser(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "hyba_mcp"
        text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
        for banned in ("qiskit", "cudaq", "parse_qasm", "Qasm"):
            self.assertNotIn(banned, text)


class ServerTests(unittest.TestCase):
    def _ready(self) -> TuringMCPServer:
        server = TuringMCPServer()
        init = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
        )
        self.assertEqual(init["result"]["serverInfo"]["name"], "hyba-mcp-server")
        self.assertIsNone(
            server.handle_request(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}
            )
        )
        return server

    def test_tools_match_the_maths_surface(self):
        server = self._ready()
        listed = server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        names = [tool["name"] for tool in listed["result"]["tools"]]
        self.assertEqual(
            names,
            ["list_backends", "validate_math", "execute_circuit", "compute_expectation"],
        )
        self.assertEqual(set(TOOLS), set(names))

    def test_call_before_ready_is_rejected(self):
        server = TuringMCPServer()
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_backends", "arguments": {}},
            }
        )
        self.assertEqual(response["error"]["code"], -32002)

    def test_tool_call_returns_bell_text(self):
        server = self._ready()
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "execute_circuit",
                    "arguments": {"spec": _bell()},
                },
            }
        )
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertAlmostEqual(payload["state"]["probabilities"][0], 0.5)
        self.assertFalse(response["result"]["isError"])

    def test_unknown_field_is_an_input_error(self):
        server = self._ready()
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "execute_circuit",
                    "arguments": {"spec": _bell(), "shots": 100},
                },
            }
        )
        self.assertEqual(response["error"]["code"], -32602)

    def test_stdio_roundtrip(self):
        inbound = io.StringIO(
            "\n".join(
                [
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "stdio", "version": "0"},
                            },
                        }
                    ),
                    json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/call",
                            "params": {
                                "name": "compute_expectation",
                                "arguments": {
                                    "spec": {"n_qubits": 1, "gates": []},
                                    "observable": "Z",
                                },
                            },
                        }
                    ),
                    "",
                ]
            )
        )
        outbound = io.StringIO()
        run_server(inbound, outbound)
        lines = [json.loads(line) for line in outbound.getvalue().splitlines() if line]
        self.assertEqual(len(lines), 2)
        body = json.loads(lines[1]["result"]["content"][0]["text"])
        self.assertAlmostEqual(body["expectation"]["re"], 1.0)

    def test_library_cnot_is_the_same_object_family(self):
        self.assertIsInstance(CNOT, LinearOperator)

    def test_client_connects_and_calls_the_mcp(self):
        self.assertIs(HybaMCPServer, TuringMCPServer)
        client = connect()
        names = [tool["name"] for tool in client.list_tools()]
        self.assertIn("execute_circuit", names)
        payload = client.call_tool("execute_circuit", {"spec": _bell()})
        self.assertAlmostEqual(payload["state"]["probabilities"][0], 0.5)
        self.assertAlmostEqual(payload["state"]["probabilities"][3], 0.5)
        with self.assertRaises(RuntimeError):
            HybaMCPClient_unconnected = __import__(
                "hyba_mcp.client", fromlist=["HybaMCPClient"]
            ).HybaMCPClient()
            HybaMCPClient_unconnected.call_tool("list_backends", {})


if __name__ == "__main__":
    unittest.main()
