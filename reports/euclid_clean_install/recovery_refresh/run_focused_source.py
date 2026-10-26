"""Selective-source unit runner, NOT installed EUCLID or full-repository acceptance.

Loads the real audit/bridge/recovery modules without the unrelated package
initializers. The custody port in this suite is explicitly a DiskPort double.
Use scripts/run_clean_install.py for actual installed canonical qualification.
"""

import argparse
import importlib.util
from pathlib import Path
import sys
import unittest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-root", type=Path, required=True)
args = parser.parse_args()
root = args.source_root.resolve()
for name, path in (
    ("al_haras.audit", "al_haras/audit.py"),
    ("euclid.capabilities.empirical_state_bridge", "euclid/capabilities/empirical_state_bridge.py"),
    ("euclid.capabilities.empirical_recovery", "euclid/capabilities/empirical_recovery.py"),
    ("test_empirical_hardening", "tests/test_empirical_state_bridge_hardening.py"),
):
    spec = importlib.util.spec_from_file_location(name, root / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromModule(module)
)
sys.exit(0 if result.wasSuccessful() else 1)
