"""Build wheel FROM sdist and verify installed artefacts; never upload.

Package verification is not SALAMANDER production qualification. Every gate,
input source digest and failure is retained in the release verdict.
"""
from __future__ import annotations

import argparse
import ast
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PACKAGES = ("salamander", "al_haras")
RELEASE_GATES = (
    "source_identity", "staging", "build_tools", "sdist", "wheel_from_sdist",
    "archive_inspection", "twine", "clean_install", "installed_boundary_voyage", "source_snapshot",
)
REQUIRED_MODULES = (
    "salamander", "salamander.authority", "salamander.control_plane",
    "salamander.models", "salamander.runtime", "salamander.outcome_evidence",
    "salamander.discovery_optimisation", "al_haras", "al_haras.guardian",
    "al_haras.audit", "al_haras.entitlements", "al_haras.models", "al_haras.settings",
)
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, *, cwd, capture=False):
    return subprocess.run([str(x) for x in command], cwd=cwd, check=True,
                          text=True, capture_output=capture, timeout=600)


def python_in(directory):
    return directory / ("Scripts" if os.name == "nt" else "bin") / "python"


def source_identity(repo=REPO):
    top = run(["git", "rev-parse", "--show-toplevel"], cwd=repo, capture=True).stdout.strip()
    require(Path(top).resolve() == repo.resolve(), "not the repository checkout root")
    head = run(["git", "rev-parse", "HEAD"], cwd=repo, capture=True).stdout.strip()
    require(bool(re.fullmatch(r"[0-9a-f]{40}", head)), "source commit unavailable")
    dirty = run(["git", "status", "--porcelain", "--untracked-files=normal", "--",
                 "salamander", "al_haras", "packaging/salamander"], cwd=repo, capture=True).stdout
    require(not dirty.strip(), "product/release inputs are dirty; commit before qualification")
    return head


def source_files(repo=REPO):
    inventory = {}
    for package in PACKAGES:
        require((repo/package/'__init__.py').is_file(), "missing product package: "+package)
        for path in sorted((repo/package).rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(repo)
            if any(part in {'tests', '__pycache__', 'var', '.pytest_cache'} for part in relative.parts):
                continue
            if path.suffix in {'.pyc', '.pyo'}:
                continue
            require(not path.is_symlink(), "symlink in product sources")
            require(path.suffix == '.py' or path.name == 'py.typed',
                    "unreviewed product data file: "+str(relative))
            inventory[relative.as_posix()] = sha256(path)
    return inventory


def stage(directory, *, repo=REPO, here=HERE, commit):
    src = directory/'src'
    src.mkdir(parents=True)
    inputs = source_files(repo)
    for name in inputs:
        dst = src/name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dst)
    for name in ('pyproject.toml', 'README.md', 'RELEASE.md', 'MANIFEST.in'):
        shutil.copy2(here/name, src/name)
        inputs['packaging/salamander/'+name] = sha256(here/name)
    shutil.copy2(repo/'LICENSE', src/'LICENSE')
    inputs['LICENSE'] = sha256(repo/'LICENSE')
    for name in ('build_and_verify.py', 'installed_smoke.py'):
        inputs['packaging/salamander/'+name] = sha256(here/name)
    provenance = {'schema': 'hyba-salamander.build-provenance/1', 'source_commit': commit,
                  'input_sha256': inputs, 'scope': 'PACKAGE_ARTEFACT_NOT_PRODUCTION_CERTIFICATION'}
    (src/'salamander/_build_provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    return src, provenance


def module_names(names):
    modules = set()
    for name in names:
        parts = PurePosixPath(name).parts
        if not parts or parts[0] not in PACKAGES or not name.endswith('.py'):
            continue
        module = name[:-3].replace('/', '.')
        if module.endswith('.__init__'):
            module = module[:-9]
        modules.add(module)
    return sorted(modules)


def inspect_wheel(path, *, project, inputs):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate wheel members')
        checks = {}
        checks['safe_paths'] = all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts
                                   and '\\' not in n for n in names)
        checks['clean_payload'] = not any('/tests/' in n or '__pycache__' in n or
                                          n.endswith(('.pyc', '.pyo', '.env', '.key')) for n in names)
        top = {n.split('/')[0] for n in names if '/' in n and not n.split('/')[0].endswith('.dist-info')}
        checks['product_boundary'] = top == set(PACKAGES)
        hits = [n for n in names if any(p.search(archive.read(n)) for p in SECRET_PATTERNS)]
        checks['secret_patterns'] = not hits
        checks['source_equivalence'] = all(n in names and hashlib.sha256(archive.read(n)).hexdigest() == digest
                                          for n, digest in inputs.items() if n.split('/')[0] in PACKAGES)
        metadata_names = [n for n in names if n.endswith('.dist-info/METADATA')]
        checks['single_metadata'] = len(metadata_names) == 1
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]) if len(metadata_names)==1 else b'')
        checks['name_version'] = metadata.get('Name') == project['name'] and metadata.get('Version') == project['version']
        checks['python_contract'] = metadata.get('Requires-Python') == project['requires-python']
        checks['mit_license'] = metadata.get('License-Expression') == 'MIT' or metadata.get('License') == 'MIT'
        checks['license_notice'] = any(n.endswith('/LICENSE') for n in names)
        checks['typed_markers'] = all(p+'/py.typed' in names for p in PACKAGES)
        checks['not_production_stable_claim'] = 'Development Status :: 5 - Production/Stable' not in metadata.get_all('Classifier', [])
        checks['provenance'] = 'salamander/_build_provenance.json' in names
        modules = module_names(names)
        checks['required_modules'] = set(REQUIRED_MODULES) <= set(modules)
        checks['python_311_syntax'] = True
        for name in names:
            if name.endswith('.py'):
                try:
                    ast.parse(archive.read(name).decode('utf-8'), feature_version=(3,11))
                except (SyntaxError, UnicodeDecodeError):
                    checks['python_311_syntax'] = False
    return {'checks': checks, 'passed': all(checks.values()), 'modules': modules,
            'files': names, 'secret_hit_paths': hits}


def unpack_sdist(path, directory):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        require(bool(members), 'empty sdist')
        roots = {PurePosixPath(m.name).parts[0] for m in members}
        require(len(roots)==1, 'sdist must have one project root')
        require(all(not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts
                    and '\\' not in m.name and ':' not in m.name and (m.isfile() or m.isdir()) for m in members),
                'unsafe sdist paths or links')
        for member in members:
            if member.isfile():
                data = archive.extractfile(member).read()
                require(not any(p.search(data) for p in SECRET_PATTERNS), 'secret pattern in sdist')
                require('/tests/' not in member.name and '__pycache__' not in member.name,
                        'test/cache files in sdist')
        require(len({m.name for m in members}) == len(members), 'duplicate sdist members')
        archive.extractall(directory)  # every path/type checked above; Python 3.11 compatible
    return directory/next(iter(roots))


def verdict(gates, production):
    artifact_verified = all(gates.get(gate) == 'PASSED' for gate in RELEASE_GATES)
    # The installed implementation provides the qualification state. A package
    # test result or owner dispatch option cannot make it production-ready.
    production_qualified = production.get('production_ready') is True and all(
        v == 'VERIFIED' for v in production.get('gates', {}).values()) and bool(production.get('gates'))
    return {'artifact_verified': artifact_verified, 'production_qualified': production_qualified,
            'publishable': artifact_verified and production_qualified,
            'published': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, required=True,
                        help='fresh output directory outside the repository')
    args = parser.parse_args()
    out = args.out_dir.resolve()
    require(not out.is_relative_to(REPO.resolve()), 'output must be outside repository')
    require(not out.exists(), 'output directory already exists; refuse stale artifacts')
    out.mkdir(parents=True)
    record = {'schema':'hyba-salamander.release-verdict/1', 'gates': {}, 'production': {}}
    gate = 'source_identity'
    try:
        commit = source_identity()
        record['source_commit'] = commit
        record['gates'][gate] = 'PASSED'
        config = tomllib.loads((HERE/'pyproject.toml').read_text())
        project = config['project']
        record['distribution'], record['version'] = project['name'], project['version']
        with tempfile.TemporaryDirectory(prefix='salamander-release-') as temp:
            temp = Path(temp)
            gate = 'staging'
            src, provenance = stage(temp, commit=commit)
            record['input_sha256'] = provenance['input_sha256']
            record['gates'][gate] = 'PASSED'
            tools = temp/'tools'
            venv.EnvBuilder(with_pip=True).create(tools)
            python = python_in(tools)
            gate = 'build_tools'
            run([python,'-m','pip','install','build>=1.2,<2','twine>=6,<7'],cwd=temp)
            record['gates'][gate] = 'PASSED'
            gate = 'sdist'
            run([python,'-m','build','--sdist','--outdir',out,src],cwd=temp)
            sdists = list(out.glob('*.tar.gz'))
            require(len(sdists)==1, 'exactly one sdist required')
            unpacked = unpack_sdist(sdists[0], temp/'unpacked')
            record['gates'][gate] = 'PASSED'
            gate = 'wheel_from_sdist'
            run([python,'-m','pip','wheel','--no-deps','--wheel-dir',out,unpacked],cwd=temp)
            wheels = list(out.glob('*.whl'))
            require(len(wheels)==1, 'exactly one wheel required')
            record['artifacts'] = {p.name:{'sha256':sha256(p),'bytes':p.stat().st_size} for p in (sdists[0],wheels[0])}
            record['gates'][gate] = 'PASSED'
            gate = 'archive_inspection'
            record['inspection'] = inspect_wheel(wheels[0], project=project, inputs=provenance['input_sha256'])
            require(record['inspection']['passed'], 'wheel inspection failed')
            record['gates'][gate] = 'PASSED'
            gate = 'twine'
            run([python,'-m','twine','check',sdists[0],wheels[0]],cwd=temp)
            record['gates'][gate] = 'PASSED'
            gate = 'clean_install'
            env = temp/'installed'
            venv.EnvBuilder(with_pip=True).create(env)
            installed_python = python_in(env)
            run([installed_python,'-m','pip','install',wheels[0]],cwd=temp)
            run([installed_python,'-m','pip','check'],cwd=temp)
            record['gates'][gate] = 'PASSED'
            gate = 'installed_boundary_voyage'
            completed = run([installed_python,'-I',HERE/'installed_smoke.py',
                             '--expected-version',project['version'],'--expected-commit',commit,
                             '--modules',json.dumps(record['inspection']['modules'])],cwd=temp,capture=True)
            record['installed_smoke'] = json.loads(completed.stdout)
            require(record['installed_smoke']['passed'], 'installed boundary voyage failed')
            record['production'] = record['installed_smoke']['production']
            record['gates'][gate] = 'PASSED'
            gate = 'source_snapshot'
            require(source_identity() == commit, 'checkout source head changed during verification')
            require(all((REPO/name).is_file() and sha256(REPO/name) == value
                        for name, value in provenance['input_sha256'].items()),
                    'release inputs changed during verification')
            record['gates'][gate] = 'PASSED'
    except Exception as exc:
        unavailable = gate in {'source_identity', 'build_tools'} and isinstance(
            exc, (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired))
        record['gates'][gate] = 'UNAVAILABLE' if unavailable else 'FAILED'
        record['failure'] = {'gate':gate,'exception_class':type(exc).__name__}
    record.update(verdict(record['gates'], record['production']))
    destination = out/'hyba-salamander-release-verdict.json'
    destination.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'verdict_file':str(destination),**verdict(record['gates'],record['production'])}))
    return 0 if record['artifact_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
