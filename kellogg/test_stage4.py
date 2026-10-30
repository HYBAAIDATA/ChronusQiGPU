"""Test script for Stage 4 dual backend."""
import sys
sys.path.insert(0, r"c:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main")

from kellogg.dual_backend import (
    StackIRBackend,
    BytecodeVM,
    Backend,
    lower_to_stack_ir,
    lower_to_bytecode,
)


def test_backend_types():
    """Test that backend types are correct."""
    assert isinstance(StackIRBackend(), Backend)
    assert isinstance(BytecodeVM(), Backend)
    print("test_backend_types: PASSED")


def test_basic_execution():
    """Test basic program execution on both backends."""
    # Program: PUSH 5, PUSH 3, ADD, HALT
    ir = {
        "instructions": [
            {"op": "PUSH", "value": 5},
            {"op": "PUSH", "value": 3},
            {"op": "ADD"},
            {"op": "HALT"},
        ]
    }

    prog_ir = lower_to_stack_ir(ir)
    prog_bc = lower_to_bytecode(ir)

    cpu = StackIRBackend()
    vm = BytecodeVM()

    result_cpu = cpu.execute(prog_ir)
    result_bc = vm.execute(prog_bc)

    assert result_cpu == result_bc == 8, f"Results: CPU={result_cpu}, VM={result_bc}"
    print("test_basic_execution: PASSED")


def test_digests():
    """Test that digests are computed."""
    cpu = StackIRBackend()
    vm = BytecodeVM()

    dig_cpu = cpu.digest(8)
    dig_bc = vm.digest(8)

    assert len(dig_cpu) > 0
    assert len(dig_bc) > 0
    print(f"CPU digest: {dig_cpu[:16]}...")
    print(f"VM digest: {dig_bc[:16]}...")
    print("test_digests: PASSED")


if __name__ == "__main__":
    test_backend_types()
    test_basic_execution()
    test_digests()
    print("\nStage 4 basic tests PASSED!")