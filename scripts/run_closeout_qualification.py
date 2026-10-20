"""Local EUCLID closeout runner. No upload, merge or production-tag authority.

Requires a complete clean Git checkout and an explicit real claims-gate command.
Artifacts and basetemps must be outside the checkout. Snapshot comparisons detect
changes at the sampled checkpoints; they are not continuous filesystem attestation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import shutil
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

CASES = {
 'regress': ['tests/test_euclid_v17_integrated_loop.py','tests/test_euclid_v17_phi_and_skills.py','tests/test_euclid_v17_runtime.py','tests/test_euclid_v17_worlds.py','tests/test_euclid_v17_world_model.py'],
 'ineffable': ['tests/test_euclid_elevated_vs_ineffable.py'],
 'gate': ['tests/test_euclid_v17_integration_gate.py'],
 'pytest_arena': ['tests/euclid_arena/'],
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git','-C',str(root),*args], text=True).strip()


def source_identity(root: Path) -> dict:
    tracked=subprocess.check_output(['git','-C',str(root),'ls-files','--stage','-z'])
    rows=[]
    for entry in tracked.split(b'\0'):
        if not entry: continue
        meta,name=entry.split(b'\t',1); mode,oid,stage=meta.split()
        if mode==b'160000' or stage!=b'0':
            raise ValueError('submodule/unmerged index needs separate recursive source validation')
        relative=os.fsdecode(name); path=root/relative
        if not path.parent.resolve().is_relative_to(root):
            raise ValueError('tracked path traverses an external symlink')
        data=os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
        rows.append({'path':relative,'mode':mode.decode(),'index_blob':oid.decode(),
                     'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    encoded=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
    return {'sha':git(root,'rev-parse','HEAD'),'tracked_files':rows,
            'manifest_sha256':hashlib.sha256(encoded).hexdigest()}


def preflight(root: Path, evidence: Path, temp: Path) -> dict:
    root=root.resolve(); evidence=evidence.resolve(); temp=temp.resolve()
    if evidence.is_relative_to(root) or temp.is_relative_to(root):
        raise ValueError('evidence and basetemps must be outside source ROOT')
    if evidence==temp or evidence.is_relative_to(temp) or temp.is_relative_to(evidence):
        raise ValueError('evidence and disposable basetemps must not overlap')
    if Path(git(root,'rev-parse','--show-toplevel')).resolve()!=root:
        raise ValueError('ROOT must be the complete checkout top level')
    if git(root,'status','--porcelain','--untracked-files=all'):
        raise ValueError('source checkout must be clean, including untracked files')
    required=['claims.yaml','scripts/chronus_elevation_proof.py']+[x for xs in CASES.values() for x in xs]
    missing=[p for p in required if not (root/p).exists()]
    if missing: raise ValueError('missing required source inputs: '+', '.join(missing))
    return source_identity(root)


def junit_outcome(path: Path, returncode: int, log: str, *, arena: bool=False) -> dict:
    if not path.is_file(): return {'state':'FAIL','reason':'missing JUnit artifact'}
    tree=ET.parse(path); suites=[s for s in tree.iter('testsuite')]
    counts={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')}
    bad_marks=(' xfailed',' xpassed','XPASS','XFAIL')
    okay=(returncode==0 and counts['tests']>0 and
          all(counts[k]==0 for k in ('failures','errors','skipped')) and
          not any(x in log for x in bad_marks) and (not arena or counts['tests']==100))
    return {'state':'PASS' if okay else 'FAIL','returncode':returncode,**counts}


def main(argv=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--evidence-dir',type=Path,required=True)
    ap.add_argument('--temp-root',type=Path,required=True)
    ap.add_argument('--claims-gate',help='Explicit repository claims-gate argv as one quoted string; never run through a shell')
    ap.add_argument('--timeout',type=float,default=1800)
    args=ap.parse_args(argv); root=args.root.resolve(); out=args.evidence_dir.resolve(); temp=args.temp_root.resolve()
    # Never place outputs under source or under a directory pytest will erase.
    if out.is_relative_to(root) or temp.is_relative_to(root) or out==temp or out.is_relative_to(temp) or temp.is_relative_to(out):
        print('BLOCKED: unsafe artifact/temp paths',file=sys.stderr); return 2
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        print('BLOCKED: timeout must be finite and positive',file=sys.stderr); return 2
    if out.exists() and any(out.iterdir()):
        print('BLOCKED: evidence directory must be new or empty',file=sys.stderr); return 2
    out.mkdir(parents=True,exist_ok=True)
    temp.mkdir(parents=True,exist_ok=True)
    report={'schema':'hyba.local-closeout-qualification/1','production_ready':False,
            'owner_signoffs':'PENDING','states':{},'scope':'EUCLID/Chronus local reruns only; not complete platform qualification'}
    def save(): (out/'qualification.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    try:
        before=preflight(root,out,temp); report['source_before']=before
        if not args.claims_gate: raise ValueError('actual claims-gate command is required; no guessed command or synthetic pass')
        claims=shlex.split(args.claims_gate)
        if not claims: raise ValueError('empty claims-gate command')
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        report['state']='BLOCKED'; report['reason']=str(exc); save(); print('BLOCKED:',exc); return 2
    def run(name,command):
        started=time.time(); logpath=out/(name+'.log'); mid=[]
        with open(logpath,'w') as log:
            log.write('command='+json.dumps(command)+'\nsource_sha='+before['sha']+'\n'); log.flush()
            proc=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,
                                  env={**os.environ,'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'})
            try:
                while proc.poll() is None:
                    if time.time()-started>args.timeout:
                        proc.kill(); proc.wait(); raise TimeoutError(name+' timed out')
                    identity=source_identity(root)
                    mid.append({'time':time.time(),'manifest_sha256':identity['manifest_sha256']})
                    if identity['manifest_sha256']!=before['manifest_sha256']:
                        proc.kill(); proc.wait(); raise ValueError('source manifest changed mid-run: '+name)
                    time.sleep(.5)
            finally:
                if proc.poll() is None: proc.kill(); proc.wait()
        report['states'][name]={'command':command,'returncode':proc.returncode,'sampled_manifests':mid,
                               'log_sha256':hashlib.sha256(logpath.read_bytes()).hexdigest()}
        return proc.returncode,logpath.read_text(errors='replace')
    try:
        code,_=run('claims-gate',claims)
        if code: raise ValueError('claims gate failed')
        report['states']['claims-gate']['state']='EXECUTED_ZERO_EXIT_REQUIRES_CLAIM_ARTIFACT_REVIEW'
        for name,paths in CASES.items():
            junit=out/(name+'.xml')
            command=[sys.executable,'-m','pytest',*paths,'-p','no:cacheprovider',
                     '--basetemp='+str(temp/name),'--junitxml='+str(junit),'-ra','-q']
            code,log=run(name,command)
            report['states'][name].update(junit_outcome(junit,code,log,arena=name=='pytest_arena'))
            if report['states'][name]['state']!='PASS': raise ValueError(name+' has unresolved outcomes')
        # Copy the actual fresh report, not an inferred device PASS label.
        report_started_ns=time.time_ns()
        code,_=run('chronus-elevation',[sys.executable,'scripts/chronus_elevation_proof.py'])
        if code: raise ValueError('Chronus report producer failed')
        generated=root/'reports/chronus_elevation.json'
        if generated.is_symlink() or not generated.is_file():
            raise ValueError('Chronus report is missing or symlinked')
        if generated.stat().st_mtime_ns < report_started_ns:
            raise ValueError('Chronus report was not freshly generated')
        json.loads(generated.read_text())
        copied=out/'chronus_elevation.json'; shutil.copyfile(generated,copied)
        report['states']['chronus-elevation']['artifact_sha256']=hashlib.sha256(copied.read_bytes()).hexdigest()
        report['states']['chronus-elevation']['state']='REPORT_CAPTURED_DEVICE_SCOPE_REQUIRES_REVIEW'
        after=source_identity(root); report['source_after']=after
        if after['manifest_sha256']!=before['manifest_sha256']: raise ValueError('final source manifest changed')
        report['git_status_after']=git(root,'status','--porcelain','--untracked-files=all')
        if report['git_status_after']: raise ValueError('source tree became dirty; inspect generated outputs')
        report['state']='RERUNS_COMPLETED_REVIEW_REQUIRED'
        report['remaining']=['Review claims artifacts/hash/baseline and actual Chronus report/device scope',
                             'Trio and mining acceptance','Security/operational acceptance','License/legal and named owner sign-offs']
        save(); return 0
    except (ValueError,OSError,TimeoutError,subprocess.CalledProcessError,ET.ParseError) as exc:
        report['state']='FAIL'; report['reason']=str(exc); save(); print('FAIL:',exc); return 1

if __name__=='__main__': raise SystemExit(main())
