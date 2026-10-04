from __future__ import annotations
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from euclid import HealthLevel,HealthStatus,StartupOrchestrator,StartupVerdict,SubsystemDescriptor,SubsystemKind,SubsystemRegistry,build_default_registry,salamander_descriptor
from resonance_intelligence.fallback_modes import FallbackMode
class RegistryTests(unittest.TestCase):
 def test_duplicate_and_exception_isolation(self):
  registry=SubsystemRegistry();registry.register(SubsystemDescriptor('ok',SubsystemKind.INTELLIGENCE,'test',lambda:HealthStatus(HealthLevel.HEALTHY,.9)))
  with self.assertRaises(ValueError):registry.register(SubsystemDescriptor('ok',SubsystemKind.INTELLIGENCE,'test',lambda:HealthStatus(HealthLevel.HEALTHY,.9)))
  registry.register(SubsystemDescriptor('bad',SubsystemKind.MODEL,'test',lambda:1/0));results=registry.run_health_checks();self.assertEqual(results['bad']['status'].status,HealthLevel.FAILED)
 def test_salamander_is_recovery_substrate_not_ai(self):
  descriptor=salamander_descriptor(lambda:HealthStatus(HealthLevel.HEALTHY,1));self.assertEqual(descriptor.kind,SubsystemKind.RECOVERY_SUBSTRATE)
 def test_concrete_default_registry(self):
  registry=build_default_registry();results=registry.run_health_checks();self.assertGreaterEqual(len(results),11);self.assertTrue(all(row['status'].status is not HealthLevel.FAILED for row in results.values()));self.assertEqual(results['salamander']['descriptor'].kind,SubsystemKind.RECOVERY_SUBSTRATE)
class StartupTests(unittest.TestCase):
 def make(self,root,registry,frontend=None,pool=None,baselines=None):
  return StartupOrchestrator(registry,root=root,vault_path=Path(root)/'vault',report_path=Path(root)/'startup.json',frontend_probes=frontend,pool_probe=pool,baseline_hashes=baselines)
 def registry(self,status=HealthLevel.HEALTHY,critical=True):
  r=SubsystemRegistry();r.register(SubsystemDescriptor('executive',SubsystemKind.GOVERNANCE,'arbitration',lambda:HealthStatus(status,.9,{},'degraded'),critical=critical));return r
 def test_green_full_handoff_with_injected_probes(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'HYBA_ENABLE_LIVE_SHARE_SUBMIT':'0'},clear=False):
   o=self.make(d,self.registry(),{'rest':lambda:True,'cli':lambda:True},lambda:{'handshake':True,'authenticated':True,'telemetry':True,'latency_ms':1});report=o.boot()
   self.assertEqual(report.verdict,StartupVerdict.GREEN);self.assertEqual(o.redundancy.current_mode,FallbackMode.FULL);self.assertTrue(report.handoff['learning']);self.assertFalse(report.handoff['live_share_submission']);self.assertTrue(json.loads((Path(d)/'startup.json').read_text())['audit_head'])
 def test_yellow_when_observational_probes_absent(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'HYBA_ENABLE_LIVE_SHARE_SUBMIT':'0'},clear=False):
   o=self.make(d,self.registry());report=o.boot();self.assertEqual(report.verdict,StartupVerdict.YELLOW);self.assertEqual(o.redundancy.current_mode,FallbackMode.DEGRADED);self.assertTrue(report.handoff['higher_cognition'])
 def test_red_on_critical_subsystem_failure(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'HYBA_ENABLE_LIVE_SHARE_SUBMIT':'0'},clear=False):
   o=self.make(d,self.registry(HealthLevel.FAILED),{'rest':lambda:True},lambda:{'handshake':True,'authenticated':True,'telemetry':True});report=o.boot();self.assertEqual(report.verdict,StartupVerdict.RED);self.assertEqual(o.redundancy.current_mode,FallbackMode.EMERGENCY);self.assertFalse(report.handoff['learning'])
 def test_live_share_enabled_is_critical_red(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'HYBA_ENABLE_LIVE_SHARE_SUBMIT':'1'},clear=False):
   o=self.make(d,self.registry(),{'rest':lambda:True},lambda:{'handshake':True,'authenticated':True,'telemetry':True});report=o.boot();self.assertEqual(report.verdict,StartupVerdict.RED);self.assertFalse(report.handoff['live_share_submission'])
 def test_hash_pinned_baseline_tamper_detection(self):
  import hashlib
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'HYBA_ENABLE_LIVE_SHARE_SUBMIT':'0'},clear=False):
   path=Path(d)/'file.py';path.write_text('x=1');good='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest();o=self.make(d,self.registry(),{'rest':lambda:True},lambda:{'handshake':True,'authenticated':True,'telemetry':True},{'file.py':good});self.assertEqual(o.boot().verdict,StartupVerdict.GREEN)
   path.write_text('x=2');o=self.make(d,self.registry(),{'rest':lambda:True},lambda:{'handshake':True,'authenticated':True,'telemetry':True},{'file.py':good});self.assertEqual(o.boot().verdict,StartupVerdict.RED)
 def test_phase_order_and_merkle_probe(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'HYBA_ENABLE_LIVE_SHARE_SUBMIT':'0'},clear=False):
   report=self.make(d,self.registry(),{'rest':lambda:True},lambda:{'handshake':True,'authenticated':True,'telemetry':True}).boot();phases=[c.phase for c in report.checks];self.assertEqual(phases,sorted(phases));check=next(c for c in report.checks if c.name=='merkle_compression_roundtrip');self.assertEqual(check.status.value,'pass');self.assertGreater(check.details['folded_objects'],0)
if __name__=='__main__':unittest.main()
