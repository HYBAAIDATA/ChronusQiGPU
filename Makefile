.PHONY: verify-unified

verify-unified:
	python3 -m pytest \
		tests/test_toe_unified_invariants.py \
		tests/test_toe_unified_adversarial.py \
		tests/test_toe_unified_property.py \
		tests/test_toe_unified_unit.py \
		tests/test_toe_unified_integration.py \
		tests/test_toe_unified_e2e.py \
		tests/test_toe_unified_benchmark.py -q
