"""One bounded pass. Failures are recorded, never silently retried or exempted."""
from pathlib import Path
import subprocess,os,json,hashlib,sys,time,shutil
root=Path('/data/pr140-bounded');build=root/'build-tree';snap=root/'canonical-snapshot';checks=root/'installed-checks';checks.mkdir(exist_ok=True)
for p in ['test_reference_boundary.py','test_exact_evolution_replacement.py']:shutil.copyfile(build/'tests'/p,checks/p)
SOURCE='3795d1be98ba7496384acca821e839ac3e5fcd7c'
records=[]
py='/data/v310-build-venv/bin/python'
def run(name,cmd,cwd=None,env=None,timeout=240):
 log=root/(name+'.log');t=time.monotonic()
 try:
  with log.open('w')as f:r=subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  code=r.returncode;status='PASS'if code==0 else'FAIL'
 except subprocess.TimeoutExpired:code=None;status='TIMEOUT'
 records.append({'gate':name,'source_commit':SOURCE,'command':cmd,'cwd':str(cwd)if cwd else None,'exit_code':code,'status':status,'elapsed_seconds':time.monotonic()-t,'log':log.name,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'qualification_scope':'RETAINED_DEPENDENCY_SNAPSHOT_NOT_COMPLETE_EXACT_HEAD_CHECKOUT'})
 (root/'final-commands.json').write_text(json.dumps(records,indent=2))
 print(name,status,code,flush=True)
 return code==0
for kind in ['native','portable']:
 shutil.rmtree(build/'build',ignore_errors=True)
 dest=root/'wheels'/kind;dest.mkdir(parents=True,exist_ok=True)
 env=dict(os.environ);env.pop('PYTHONPATH',None)
 if kind=='portable':env['CHRONOS_DISABLE_NATIVE']='1'
 if not run('build-'+kind,[py,'-m','build','--wheel','--no-isolation','--outdir',str(dest)],cwd=build,env=env):continue
 venv=root/('venv-'+kind)
 run('venv-'+kind,[sys.executable,'-m','venv',str(venv)])
 vp=str(venv/'bin/python');wheel=next(dest.glob('*.whl'))
 if not run('install-'+kind,[vp,'-m','pip','install',str(wheel),'pytest>=8,<10'],env=env):continue
 paths='/data/hendrix-elevation/test-support:'+str(snap)+':'+str(snap/'turing_universal_quantum_computer')
 env['PYTHONPATH']=paths
 run('focused-installed-'+kind,[vp,'-m','pytest',str(checks),str(snap/'tests/test_exact_geometry.py'),str(snap/'tests/test_resident_hendrix.py'),str(snap/'tests/test_production_replacement_attacks.py'),'-q','--junitxml='+str(root/('final-'+kind+'.xml'))],cwd=checks,env=env,timeout=300)
 # Real Genesis SHA, local PRIME-DB persistence and separate-process replay.
 env['PYTHONPATH']=paths+':'+str(snap/'tests')
 script=Path('/data/product-closure/capture_voyage.py').read_text().replace("Path('/data/product-closure')", "Path('/data/pr140-bounded')")
 (root/'capture_voyage.py').write_text(script)
 run('restart-execute-'+kind,[vp,str(root/'capture_voyage.py'),kind,'execute'],env=env,timeout=120)
 run('restart-replay-'+kind,[vp,str(root/'capture_voyage.py'),kind,'replay'],env=env,timeout=120)
 run('installed-provenance-'+kind,[vp,'-c',"import json,hashlib,chronos_one_igpu,chronos_one_igpu.igpu.facade as f;from pathlib import Path;print(json.dumps({'package':chronos_one_igpu.__file__,'facade_sha256':hashlib.sha256(Path(f.__file__).read_bytes()).hexdigest()}));assert 'site-packages' in f.__file__"],cwd=checks,env={k:v for k,v in env.items()if k!='PYTHONPATH'})
# Product-owned gates: no fabrication of unavailable canonical dependencies.
env=dict(os.environ);env['PYTHONPATH']='/data/hendrix-elevation/test-support:'+str(snap)+':'+str(snap/'turing_universal_quantum_computer')+':'+str(snap/'chronus/mla1517_platform/python')
vp=str(root/'venv-native/bin/python')
run('platform',[vp,'-m','pytest',str(snap/'chronus/mla1517_platform/python/test_production_loop_e2e.py'),'-q','--junitxml='+str(root/'final-platform.xml')],cwd=snap,env=env,timeout=120)
run('import-audit',[vp,str(snap/'scripts/import_audit.py'),'--json',str(root/'final-import-audit.json')],cwd=snap,env=env,timeout=120)
run('packaging',[py,'-m','twine','check',*[str(p)for p in(root/'wheels').rglob('*.whl')]],timeout=120)
