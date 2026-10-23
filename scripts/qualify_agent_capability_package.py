"""Build sdist -> wheel and test the installed diagnostic surface in a clean venv.

This is a scoped feature check, NOT the canonical product release verifier.
Input hashes identify a source candidate without inventing Git commit provenance.
No upload, publication, deployed-service or all-shipped-module claim is made.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, cwd):
    subprocess.run([str(x) for x in command], cwd=cwd, check=True, timeout=600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.exists() or out.is_relative_to(ROOT):
        raise ValueError('use a fresh output directory outside the source tree')
    out.mkdir(parents=True)
    verdict = {'schema': 'salamander.agent-capability-package-check/1',
               'scope': 'INSTALLED_DIAGNOSTIC_SURFACE_ONLY',
               'production_ready': False, 'published': False, 'passed': False}
    try:
        with tempfile.TemporaryDirectory(prefix='agent-package-check-') as work:
            work = Path(work)
            stage = work / 'candidate'; stage.mkdir()
            inputs = {}
            for package in ('salamander', 'al_haras'):
                for path in sorted((ROOT / package).rglob('*')):
                    if not path.is_file() or path.suffix != '.py' and path.name != 'py.typed':
                        continue
                    if {'tests', '__pycache__'} & set(path.relative_to(ROOT).parts):
                        continue
                    if path.is_symlink():
                        raise ValueError('source symlinks are not allowed')
                    name = path.relative_to(ROOT)
                    target = stage / name; target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target); inputs[name.as_posix()] = sha(path)
            for name, source in [('pyproject.toml', ROOT/'packaging/salamander/pyproject.toml'),
                                 ('README.md', ROOT/'packaging/salamander/README.md'),
                                 ('LICENSE', ROOT/'LICENSE')]:
                shutil.copy2(source, stage/name)
                inputs[source.relative_to(ROOT).as_posix()] = sha(source)
            verdict['input_sha256'] = inputs
            verdict['license_review_required'] = (
                'BSD 3-Clause' in (ROOT/'LICENSE').read_text()
                and 'license = "MIT"' in (stage/'pyproject.toml').read_text())
            run([sys.executable, '-m', 'build', '--sdist', '--no-isolation', '--outdir', out, stage], work)
            sdists = list(out.glob('*.tar.gz'))
            if len(sdists) != 1: raise RuntimeError('exactly one sdist required')
            with tarfile.open(sdists[0]) as archive:
                archive.extractall(work/'unpacked', filter='data')
            unpacked = next((work/'unpacked').iterdir())
            run([sys.executable, '-m', 'build', '--wheel', '--no-isolation', '--outdir', out, unpacked], work)
            wheels = list(out.glob('*.whl'))
            if len(wheels) != 1: raise RuntimeError('exactly one wheel required')
            with zipfile.ZipFile(wheels[0]) as archive:
                for name, digest in inputs.items():
                    if name.startswith(('salamander/', 'al_haras/')):
                        if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                            raise RuntimeError('installed candidate differs from staged source: '+name)
            env = work/'installed'; venv.EnvBuilder(with_pip=True).create(env)
            python = env/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            run([python, '-m', 'pip', 'install', '--disable-pip-version-check', wheels[0]], work)
            smoke = work/'installed_feature_smoke.py'
            smoke.write_text('''import json,sys
from pathlib import Path
import salamander
from salamander import AgentCapabilitySuite
from salamander.control_plane import EvidenceLedger,ActionRegistry,FailClosed
from salamander.models import ActionRequest,ActionKind
import salamander.agent_capabilities as module
assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert 'chronus' not in sys.modules
ledger=EvidenceLedger(); suite=AgentCapabilitySuite(ledger)
r=suite.inspect(tenant_id='tenant-a',target='x.py',source='pin=False',evidence={
 'pins':{'pin':False},'identities':[{'left':'1/3+2/3','right':'1'}],
 'quantum':{'kind':'unitary','matrices':[[[0,1],[1,0]]]}})
assert len(r['capabilities'])==10
for role in ('math_verifier','pin_verifier','quantum_checker'):
 assert r['capabilities'][role]['status']=='PASS'
f=suite.inspect(tenant_id='tenant-a',target='x.py',source='eval("1")',evidence={
 'identities':[{'left':'1','right':'2'}]})
assert f['capabilities']['math_verifier']['status']=='FAIL'
assert f['capabilities']['security_verifier']['status']=='FAIL'
assert f['capabilities']['governance']['status']=='FAIL'
assert ledger.verify() and EvidenceLedger.from_payload(ledger.to_payload()).verify()
assert r['actuation']=='NOT_PERFORMED' and not r['self_healing_ready']
try:
 ActionRegistry().execute(ActionRequest('x',ActionKind.REPLAN,'x','tenant-a','x','test',{},idempotency_key='x'))
except FailClosed: pass
else: raise AssertionError('authorization bypass')
print('installed diagnostic surface: PASS')
''')
            run([python, '-I', smoke], work)
            verdict['checks'] = dict(sdist_built=True, wheel_from_sdist=True,
                                    product_source_equivalence=True, clean_venv_install=True,
                                    installed_feature_smoke=True)
            verdict['artifacts'] = {path.name: {'sha256': sha(path), 'bytes': path.stat().st_size}
                                    for path in (sdists[0], wheels[0])}
            verdict['passed'] = True
    except Exception as exc:
        verdict['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        (out/'verdict.json').write_text(json.dumps(verdict, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__': main()
