import unittest,re,json,hashlib
from pathlib import Path
from unittest.mock import patch
class IntakeTests(unittest.TestCase):
 def test_all_inventory_names_retained(self):
  root=Path(__file__).resolve().parents[1];raw=(root/'docs/source_notes/elevation-module-inventory.txt').read_text();x=json.loads((root/'docs/ATTACHED_SURFACE_INVENTORY.json').read_text());names=set()
  for line in raw.splitlines():
   m=re.match(r'^([\w.\-]+)\s+(?:d----|-a---|\d+)\s*(?:\d+)?\s*$',line)
   if m:names.add(m.group(1))
  self.assertEqual(names,{e['name']for e in x['entries']});self.assertIn('qsdl_compiler.py',names);self.assertIn('coordinator.py',names);self.assertIn('self_healing_agent.py',names)
 def test_inventory_hash_bound(self):
  root=Path(__file__).resolve().parents[1];x=json.loads((root/'docs/ATTACHED_SURFACE_INVENTORY.json').read_text());self.assertEqual(x['source_sha256'],hashlib.sha256((root/x['source_file']).read_bytes()).hexdigest());self.assertTrue(x['identifiers_are_not_standalone_release_commits'])
 def test_absent_hardware_never_qualifies(self):
  from chronos.qualification import qualify_target
  from chronos.adapters.base import BackendAbsent
  with patch('chronos.igpu.fabric.OpenCLOverlay',side_effect=BackendAbsent('no physical test device')):
   x=qualify_target(runs=1,nonce_budget=1);self.assertFalse(x['hardware_measured']);self.assertEqual(x['status'],'UNAVAILABLE_OR_FAILED')
 def test_proof_obligations_not_all_closed(self):
  root=Path(__file__).resolve().parents[1];x=json.loads((root/'docs/PYTHI_NATIVE_OBLIGATIONS.json').read_text());self.assertFalse(x['deployment_allowed']);self.assertEqual({o['id']for o in x['obligations']},{f'T{i}'for i in range(1,11)})
