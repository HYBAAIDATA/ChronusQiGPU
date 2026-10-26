"""Isolated bridge-function unit checks with an explicit triad double.

NOT installed-system acceptance. Parses the two production functions only;
the package initializer and all engines are outside this unit's scope.
Never use this harness to close a launch/integration requirement.
"""
import ast
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else ROOT / 'aethel/enterprise_bridge.py'


@contextmanager
def boundary(*, corrupt=False, disk_bound=True, verified=True):
    source = ast.parse(SOURCE.read_text())
    selected = [node for node in source.body if isinstance(node, (ast.FunctionDef, ast.ImportFrom)) and (
        (isinstance(node, ast.FunctionDef) and node.name in {'open_enterprise_store', 'smoke_measured_put'})
        or (isinstance(node, ast.ImportFrom) and node.module == '__future__')
    )]
    calls = []
    stores = {}
    class Store:
        def __init__(self, kwargs):
            self.kwargs = kwargs
            self.theseus = types.SimpleNamespace(durable_dir=kwargs.get('durable_dir'))
            self.storage_profile = 'theseus-custody/v1'
        def put(self, payload, **kwargs):
            stores['payload'] = payload
            return types.SimpleNamespace(uuid='unit-id', digest=hashlib.sha256(payload).hexdigest(),
                anchor=1, lane=1, prime_key=1, folded_units=1)
        def get(self, uid): return b'corrupt' if corrupt else stores['payload']
        def verify(self): return verified
        def health(self): return {'custody': {'authority': 'theseus', 'disk_bound': disk_bound, 'integrity_verified': verified}}
    def open_triad(**kwargs):
        calls.append(kwargs)
        return Store(kwargs)
    triad = types.ModuleType('_boundary_unit.triad')
    triad.open_triad = open_triad
    triad.THESEUS_CUSTODY_PROFILE = 'theseus-custody/v1'
    namespace = {'__name__': '_boundary_unit.bridge', '__package__': '_boundary_unit',
        'Path': Path, 'hashlib': hashlib, 'Dict': dict, 'Any': object,
        'TruthClass': types.SimpleNamespace(MEASURED='measured', UNVERIFIED='unverified'),
        'emit_envelope': lambda payload, **kwargs: {'payload': payload, **kwargs}}
    with patch.dict(sys.modules, {'_boundary_unit.triad': triad}):
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), 'exec'), namespace)
        yield namespace, calls


class BoundaryUnits(unittest.TestCase):
    def test_default_durable_refused(self):
        with boundary() as (ns, calls):
            with self.assertRaises(ValueError): ns['open_enterprise_store']()
            self.assertEqual(calls, [])
    def test_empty_directory_refused(self):
        with boundary() as (ns, calls):
            with self.assertRaises(ValueError): ns['open_enterprise_store'](durable_dir='')
            self.assertEqual(calls, [])
    def test_conflict_refused(self):
        with boundary() as (ns, calls):
            with self.assertRaises(ValueError): ns['open_enterprise_store'](durable=False, durable_dir='/unit-only')
            self.assertEqual(calls, [])
    def test_nonboolean_durable_refused(self):
        with boundary() as (ns, calls):
            with self.assertRaises(TypeError): ns['open_enterprise_store'](durable=1, durable_dir='/unit-only')
            self.assertEqual(calls, [])
    def test_explicit_memory_forwarding(self):
        with boundary() as (ns, calls):
            ns['open_enterprise_store'](durable=False)
            self.assertIs(calls[0]['durable'], False)
            self.assertIsNone(calls[0].get('durable_dir'))
    def test_directory_and_profile_forwarded(self):
        with boundary() as (ns, calls):
            ns['open_enterprise_store'](durable_dir='/unit-only', bind_chronus=False)
            self.assertEqual(calls[0]['durable_dir'], '/unit-only')
            self.assertEqual(calls[0]['storage_profile'], 'theseus-custody/v1')
            self.assertIs(calls[0]['bind_chronus'], False)
    def test_smoke_refuses_unbound_before_engine(self):
        with boundary() as (ns, calls):
            with self.assertRaises(ValueError): ns['smoke_measured_put']()
            self.assertEqual(calls, [])
    def test_smoke_reattaches_with_same_directory(self):
        with boundary() as (ns, calls):
            env = ns['smoke_measured_put'](b'unit-only', durable_dir='/unit-only')
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0], calls[1])
            self.assertEqual(env['payload']['restart_evidence'], 'reattach_same_process')
            self.assertIs(env['payload']['ok'], True)

    def test_smoke_refuses_corrupt_read(self):
        with boundary(corrupt=True) as (ns, calls):
            with self.assertRaises(RuntimeError):
                ns['smoke_measured_put'](b'unit-only', durable_dir='/unit-only')
    def test_smoke_refuses_missing_disk_evidence(self):
        with boundary(disk_bound=False) as (ns, calls):
            with self.assertRaises(RuntimeError):
                ns['smoke_measured_put'](b'unit-only', durable_dir='/unit-only')
    def test_smoke_refuses_nonliteral_verification(self):
        with boundary(verified=1) as (ns, calls):
            with self.assertRaises(RuntimeError):
                ns['smoke_measured_put'](b'unit-only', durable_dir='/unit-only')


if __name__ == '__main__': unittest.main(verbosity=2)
