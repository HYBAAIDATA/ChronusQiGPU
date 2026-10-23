"""Run focused tests on full checkout or explicitly isolated source snapshot.

--source-snapshot bypasses package __init__ files ONLY, not implementation
modules. This mode proves module-level integration, not packaged startup.
"""
import argparse
import pathlib
import sys
import types
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--source-snapshot', action='store_true')
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
if args.source_snapshot:
    for name in ('salamander', 'euclid', 'euclid.agents', 'euclid.core', 'euclid.validation', 'toe', 'kellogg'):
        module = types.ModuleType(name)
        module.__path__ = [str(root.joinpath(*name.split('.')))]
        sys.modules[name] = module
suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern='test_agent_capabilities.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
