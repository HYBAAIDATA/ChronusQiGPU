"""Focused snapshot runner; bypasses ONLY unavailable top-level initializers.
Not a package, wheel, complete-repository or release qualification test.
"""
import os,pathlib,sys,types
os.environ["EUCLID_FOCUSED_SNAPSHOT"] = "1"
root=pathlib.Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
for name in ('toe','kellogg'):
 p=types.ModuleType(name);p.__path__=[str(root/name)];sys.modules[name]=p
import pytest
raise SystemExit(pytest.main(['--rootdir='+str(root),'-c','/dev/null','--confcutdir='+str(root/'tests'),*sys.argv[2:]]))
