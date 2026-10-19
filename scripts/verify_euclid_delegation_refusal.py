"""Focused retrieved-source harness; excludes package initialization and conftest."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest


def main():
    root = Path(sys.argv[1]).resolve()
    # Execute the complete actual module under the historical import alias.
    spec = importlib.util.spec_from_file_location(
        "euclid_delegation", root / "euclid/delegation.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern=sys.argv[2])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps({
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
