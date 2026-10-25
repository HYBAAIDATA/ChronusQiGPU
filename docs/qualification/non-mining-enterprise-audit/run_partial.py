"""Partial-export harness: actual modules; only hyba_services initializer bypassed."""
import sys,types,pathlib,unittest
root=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(root))
package=types.ModuleType('hyba_services');package.__path__=[str(root/'hyba_services')];sys.modules['hyba_services']=package
suite=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_enterprise_audit_guardrails.py')
r=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not r.wasSuccessful())
