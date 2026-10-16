"""Scoped real-module unittest runner; bypasses unrelated top-level package initializers.

Not an installed-artifact/full repository/PR74 runtime verification. Run from repo root.
"""
import pathlib
import sys
import types
import unittest


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    for name in ('euclid', 'euclid.emergence', 'euclid.emergence.models',
                 'euclid.emergence.substrate', 'euclid.emergence.trusted_core'):
        module = types.ModuleType(name)
        module.__path__ = [str(root.joinpath(*name.split('.')))]
        sys.modules[name] = module
    suite = unittest.TestSuite()
    for directory in sys.argv[1:] or ('tests/emergence', 'tests/emergence_authorization',
                                     'tests/emergence_custody'):
        pattern = 'test_real_qualification.py' if directory == 'tests/emergence' else 'test*.py'
        suite.addTests(unittest.defaultTestLoader.discover(str(root / directory), pattern=pattern))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == '__main__':
    sys.exit(main())
