"""Release-harness wiring checks only; not evidence of a built/installed artifact."""
import ast
from pathlib import Path


def test_installed_gate_includes_guardrails_without_removing_existing_suites():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / 'packaging/toe/build_and_verify.py').read_text())
    assignments = {node.targets[0].id: node.value for node in tree.body
                   if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    names = ast.literal_eval(assignments['UNIFIED_TESTS'])
    assert {'test_toe_unified_authority.py', 'test_toe_unified_atomic.py',
            'test_toe_unified_promotion.py', 'test_toe_unified_production_guardrails.py',
            'test_toe_unified_intelligence.py'} <= set(names)
    values = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
              and isinstance(node.value, str)}
    assert 'toe/unified/checkpoint.py' in values
    assert 'EUCLID_FOCUSED_SNAPSHOT' in values
