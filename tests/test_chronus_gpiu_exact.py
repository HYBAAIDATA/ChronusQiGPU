"""Exact execution crosses the real ABI, verifier, wire format and custody."""

import copy
import json
from dataclasses import replace
from fractions import Fraction

import pytest

from chronus.virtual_igpu.abi import Workload, WorkloadKind
from chronus.virtual_igpu.adapters import AdapterUnavailable, CPUEmulatorAdapter
from chronus.virtual_igpu.exact_quantum import execute_quantum_program
from chronus.virtual_igpu.geometric import execute_grid, execute_modular, verify_modular
from chronus.virtual_igpu.runtime import RuntimeConfig, RuntimeDaemon
from chronus.virtual_igpu.verifier import verify_workload_result
from turing_universal_quantum_computer.backends import Program
from turing_universal_quantum_computer.quantum_library import audit_exactness


def quantum(program, **options):
    return {"program": program.to_dict(), **options}


def request(kind, value):
    return Workload(
        id="exact",
        tenant="tenant-a",
        kind=kind,
        input=value,
        execution_policy="standalone_software",
    )


def test_exact_quantum_runtime_roundtrip_and_custody(tmp_path):
    program = Program(2).then("h", 0).then("cx", 0, 1).then("t", 1)
    w = request(WorkloadKind.QUANTUM_PROGRAM, quantum(program, shots=16, seed=42))
    daemon = RuntimeDaemon(RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()])
    result = daemon.submit(json.loads(json.dumps(w.as_dict())))
    assert result.status == "ok"
    assert result.receipt["verification"]["verdict"] == "match"
    assert result.output["execution"]["backend"] == "exact_algebraic"
    assert not result.output["execution"]["measured_qpu"]
    assert audit_exactness(result.output).exact
    stored = daemon.memory.retrieve("tenant-a", "exact")
    assert stored["result"]["output"] == result.output
    reloaded = RuntimeDaemon(
        RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()]
    )
    assert reloaded.memory.retrieve("tenant-a", "exact")["result"]["output"] == result.output


def test_toffoli_lowering_keeps_exact_truth_table():
    for basis in range(8):
        program = Program(3)
        for q in range(3):
            if basis & (1 << (2 - q)):
                program = program.then("x", q)
        output = execute_quantum_program(quantum(program.then("ccx", 0, 1, 2), shots=1))
        expected = basis ^ 1 if basis & 6 == 6 else basis
        assert output["execution"]["payload"]["counts"] == {f"{expected:03b}": 1}


def test_wide_clifford_uses_tableau_and_bounded_mps_is_available():
    program = Program(1024).then("h", 0).then("cx", 0, 1023)
    output = execute_quantum_program(quantum(program))
    assert output["execution"]["backend"] == "stabilizer"
    assert not output["execution"]["materialised"]
    mps = execute_quantum_program(
        quantum(Program(4).then("h", 0).then("t", 0), backend="mps_exact")
    )
    assert mps["execution"]["backend"] == "mps_exact"
    assert audit_exactness(mps).exact


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v["program"].update(n_qubits=True),
        lambda v: v["program"].update(n_qubits=1.0),
        lambda v: v["program"].update(n_qubits=1025),
        lambda v: v["program"].update(operations=[{"gate": "cx", "qubits": [0, 0]}]),
        lambda v: v["program"].update(operations=[{"gate": "h", "qubits": [False]}]),
        lambda v: v["program"].update(operations=[{"gate": "h", "qubits": [2]}]),
        lambda v: v.update(backend="qpu"),
        lambda v: v.update(max_amplitudes=4097),
        lambda v: v.update(shots=0),
        lambda v: v.update(shots=1, seed=1.5),
        lambda v: v.update(entropy_of=[0]),
    ],
)
def test_quantum_admission_rejects_coercion_and_undeclared_options(change):
    value = quantum(Program(2).then("h", 0))
    change(value)
    with pytest.raises(ValueError):
        execute_quantum_program(value)


def test_nonclifford_refused_by_tableau_and_no_device_masquerade(tmp_path):
    with pytest.raises(ValueError, match="non-Clifford"):
        execute_quantum_program(quantum(Program(1).then("t", 0), backend="stabilizer"))
    daemon = RuntimeDaemon(RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()])
    w = Workload(
        id="physical",
        kind=WorkloadKind.QUANTUM_PROGRAM,
        input=quantum(Program(1)),
        execution_policy="required_adapter",
        required_adapter_id="opencl",
    )
    with pytest.raises(AdapterUnavailable):
        daemon.submit(w)


def test_quantum_forgery_cannot_pass_sealed_replay():
    w = request(WorkloadKind.QUANTUM_PROGRAM, quantum(Program(1).then("h", 0)))
    result = CPUEmulatorAdapter().execute(w)
    assert verify_workload_result(w, result)["verdict"] == "match"
    forged = copy.deepcopy(result.output)
    forged["execution"]["payload"]["support"] = 1
    assert verify_workload_result(w, replace(result, output=forged))["verdict"] == "mismatch"


def test_d4_matches_euclid_rectangular_grid_vocabulary():
    from euclid.benchmarks.arc_agi_1 import grid_primitives as arc

    grid = [[0, 1, 2], [3, 4, 5]]
    w = request(WorkloadKind.GRID_GEOMETRY, {"op": "d4", "grid": grid})
    result = CPUEmulatorAdapter().execute(w)
    assert verify_workload_result(w, result)["verdict"] == "match"
    transforms = result.output["transforms"]
    for name in ("rot90", "rot180", "rot270", "flip_h", "flip_v", "transpose"):
        assert transforms[name] == getattr(arc, name)(grid)
    assert len({json.dumps(g) for g in transforms.values()}) == 8
    assert grid == [[0, 1, 2], [3, 4, 5]]
    transforms["rot90"][0][0] = 255
    assert verify_workload_result(w, result)["verdict"] == "mismatch"


def test_components_partition_and_connectivity_oracle():
    w = request(WorkloadKind.GRID_GEOMETRY, {"op": "components", "grid": [[1, 0, 1], [1, 0, 2]]})
    result = CPUEmulatorAdapter().execute(w)
    assert len(result.output["components"]) == 4
    assert verify_workload_result(w, result)["verdict"] == "match"
    result.output["components"][0]["cells"].append([0, 2])
    assert verify_workload_result(w, result)["verdict"] == "mismatch"


@pytest.mark.parametrize("grid", [[], [[]], [[1], [1, 2]], [[True]], [[1.0]], [[-1]], [[256]]])
def test_grid_rejects_malformed_or_noninteger_states(grid):
    with pytest.raises(ValueError):
        execute_grid({"grid": grid, "op": "d4"})


def test_modular_isometry_exact_composition_and_metric():
    value = {"x": [1, 3], "y": [2, 5], "matrix": [2, 1, 1, 1]}
    w = request(WorkloadKind.MODULAR_GEOMETRY, value)
    result = CPUEmulatorAdapter().execute(w)
    assert audit_exactness(result.output).exact
    assert verify_workload_result(w, result)["verdict"] == "match"
    inverse = execute_modular(
        {"x": result.output["x"], "y": result.output["y"], "matrix": [1, -1, -1, 2]}
    )
    assert Fraction(*inverse["x"]) == Fraction(1, 3)
    assert Fraction(*inverse["y"]) == Fraction(2, 5)
    result.output["metric_scale"] = [1, 1]
    assert verify_workload_result(w, result)["verdict"] == "mismatch"


@pytest.mark.parametrize(
    "change",
    [
        {"y": 0},
        {"y": -1},
        {"x": 0.5},
        {"x": [1, 0]},
        {"matrix": [1, 0, 0, 2]},
        {"matrix": [True, 0, 0, 1]},
    ],
)
def test_modular_geometry_rejects_invalid_domain(change):
    value = {"x": 0, "y": 1, "matrix": [1, 1, 0, 1], **change}
    with pytest.raises(ValueError):
        execute_modular(value)
    with pytest.raises(ValueError):
        verify_modular(value, {"x": [1, 1], "y": [1, 1], "metric_scale": [1, 1]})


def test_modular_oracle_rejects_extra_output_fields():
    value = {"x": 0, "y": 1, "matrix": [1, 1, 0, 1]}
    output = execute_modular(value)
    output["unchecked"] = 1
    assert verify_modular(value, output)


def test_exact_tree_graph_crosses_runtime_and_rejects_tampering(tmp_path):
    value = {
        "topology": "tree",
        "physical": {"a": 0, "b": 0},
        "sites": {
            "a": {
                "physical_dimension": 1,
                "bonds": ["edge"],
                "dimensions": [2],
                "data": [[1, 0, 0, 0, 1], [2, 0, 0, 0, 1]],
            },
            "b": {
                "physical_dimension": 1,
                "bonds": ["edge"],
                "dimensions": [2],
                "data": [[3, 0, 0, 0, 1], [4, 0, 0, 0, 1]],
            },
        },
    }
    w = request(WorkloadKind.EXACT_GRAPH, value)
    daemon = RuntimeDaemon(RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()])
    result = daemon.submit(w)
    assert result.status == "ok"
    assert result.receipt["verification"]["verdict"] == "match"
    assert result.output["amplitude_q8"] == [11, 0, 0, 0, 1]
    assert audit_exactness(result.output).exact
    result.output["amplitude_q8"][0] = 12
    assert verify_workload_result(w, result)["verdict"] == "mismatch"
    value["max_scalar_products"] = 1
    from chronus.virtual_igpu.exact_graph import execute_exact_graph

    with pytest.raises(MemoryError, match="budget"):
        execute_exact_graph(value)


def test_serialization_cannot_hide_an_inexact_quantum_value(monkeypatch):
    from turing_universal_quantum_computer import backends

    original = backends.execute_certified

    def polluted(*args, **kwargs):
        run = original(*args, **kwargs)
        run.result.payload["unexpected_diagnostic"] = 0.25
        return run

    monkeypatch.setattr(backends, "execute_certified", polluted)
    with pytest.raises(ValueError, match="exact software execution"):
        execute_quantum_program(quantum(Program(1)))


def test_optional_math_packages_are_not_advertised_when_absent(monkeypatch):
    import importlib.util

    original = importlib.util.find_spec

    def absent(name, *args):
        if name in ("turing_universal_quantum_computer.backends", "kellogg.graph_network"):
            raise ModuleNotFoundError(name)
        return original(name, *args)

    monkeypatch.setattr(importlib.util, "find_spec", absent)
    operations = CPUEmulatorAdapter().capabilities().operations
    assert "quantum_program" not in operations
    assert "exact_graph" not in operations
    assert "grid_geometry" in operations


def test_euclid_world_routes_chosen_symmetry_through_verified_chronus(tmp_path):
    from euclid.benchmarks.arc_agi_1.arc_world import ArcDemonstrationWorld, build_spec
    from euclid.benchmarks.arc_agi_1.chronus_geometry import ChronusARCGeometry

    pairs = [([[1, 2], [3, 4]], [[3, 1], [4, 2]])]
    spec = build_spec("synthetic-d4", pairs)
    daemon = RuntimeDaemon(RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()])
    executor = ChronusARCGeometry(daemon, tenant="tenant-a", workload_prefix="arc")
    native = ArcDemonstrationWorld(spec, pairs).submit(["rot90"])
    actual = ArcDemonstrationWorld(spec, pairs, geometry_executor=executor).submit(["rot90"])
    assert actual == native
    assert executor.last_receipt["verification"]["verdict"] == "match"
    assert daemon.memory.retrieve("tenant-a", "arc-0")["result"]["status"] == "ok"


def test_euclid_chronus_failure_is_not_silently_replaced_by_local_execution(tmp_path):
    from euclid.benchmarks.arc_agi_1.arc_world import execute_program
    from euclid.benchmarks.arc_agi_1.chronus_geometry import ChronusARCGeometry

    daemon = RuntimeDaemon(RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()])
    executor = ChronusARCGeometry(
        daemon,
        tenant="tenant-a",
        workload_prefix="required",
        execution_policy="required_adapter",
        required_adapter_id="missing",
    )
    with pytest.raises(AdapterUnavailable):
        execute_program(["rot90"], [([[1]], [[1]])], geometry_executor=executor)


def test_exact_quantum_bridge_never_computes_display_approximations(monkeypatch):
    from turing_universal_quantum_computer.backends import Exact, Q2

    def forbidden(*args):
        raise AssertionError("display approximation was computed")

    monkeypatch.setattr(Q2, "approx", forbidden)
    monkeypatch.setattr(Exact, "approx", forbidden)
    result = execute_quantum_program(quantum(Program(1).then("h", 0)))
    assert result["execution"]["payload"]["support"] == 2
    assert all(
        "probability_approx" not in row for row in result["execution"]["payload"]["amplitudes"]
    )
