"""Publication naming/count checker. Never a release or production gate verdict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
IGNORE = {'.git', '.venv', 'venv', 'node_modules', 'dist', 'build', '__pycache__'}


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def fingerprint(cfg):
    identity = {'scripts': cfg.get('project', {}).get('scripts', {}),
                'setuptools': cfg.get('tool', {}).get('setuptools', {})}
    return hashlib.sha256(json.dumps(identity, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def check(root=ROOT):
    root = Path(root)
    catalog = json.loads((root/'packaging/publication_catalog.json').read_text())
    baseline = json.loads((root/'packaging/publication_inventory_baseline.json').read_text())
    errors, manifest_names, covered, catalog_names = [], [], set(), set()
    existing, planned, version_actions = 0, 0, []
    legacy = {normalize(row['legacy_distribution']) for row in catalog['packages']}
    if baseline['source_sha'] != catalog['audited_base_sha']:
        errors.append('baseline source binding mismatch')
    for row in catalog['packages']:
        name = normalize(row['distribution'])
        if name in catalog_names:
            errors.append('duplicate catalog identity: '+name)
        catalog_names.add(name)
        if not re.fullmatch(r'hyba-[a-z0-9]+(?:-[a-z0-9]+)+', name):
            errors.append('invalid system/capability name: '+name)
        if row['first_public_version'] != '1.0.0':
            errors.append('first-public target must be 1.0.0: '+name)
        paths = row['manifest_paths']
        if row['state'] == 'PLANNED_NOT_SCAFFOLDED':
            planned += 1
            if paths:
                errors.append('planned package has a scaffold: '+name)
            continue
        if row['state'] != 'EXISTING_SCAFFOLD' or not paths:
            errors.append('invalid scaffold state: '+name)
            continue
        existing += 1
        if row['canonical_manifest'] not in paths:
            errors.append('canonical manifest not owned: '+name)
        for rel in paths:
            rel_norm = rel.replace('\\', '/')
            if rel_norm in covered:
                errors.append('manifest counted twice: '+rel)
            covered.add(rel_norm)
            p = root/rel
            if not p.is_file():
                errors.append('missing manifest: '+rel)
                continue
            cfg = tomllib.loads(p.read_text())
            project = cfg['project']
            manifest_names.append(normalize(project['name']))
            if normalize(project['name']) != name:
                errors.append('wrong distribution name: '+rel)
            if fingerprint(cfg) != row['preserved_interface_fingerprints'][rel]:
                errors.append('CLI/import ownership changed: '+rel)
            deps = list(project.get('dependencies', []))
            for values in project.get('optional-dependencies', {}).values():
                deps.extend(values)
            for dep in deps:
                match = re.match(r'\s*([A-Za-z0-9_.-]+)', dep)
                if match and normalize(match[1]) in legacy:
                    errors.append('legacy dependency: '+rel+': '+dep)
            if rel == row['canonical_manifest']:
                version = project.get('version', 'DYNAMIC')
                if version != row['source_metadata_version']:
                    errors.append('metadata version drift; reconcile catalog: '+rel)
                if version not in ('1.0.0', 'DYNAMIC'):
                    version_actions.append({'distribution': name, 'development_version': version,
                                            'first_public_target': '1.0.0'})
    discovered = {p.relative_to(root).as_posix() for p in root.rglob('pyproject.toml')
                  if not (set(p.relative_to(root).parts) & IGNORE)}
    if discovered != covered:
        errors.append('manifest coverage mismatch: '+repr(sorted(discovered ^ covered)))
    private = catalog['private_applications']
    for row in private:
        cfg = json.loads((root/row['path']).read_text())
        if cfg.get('private') is not True or row['counted_for_publication'] is not False:
            errors.append('private application leaks into publication: '+row['path'])
    source_rows = baseline['rows']
    raw_python = [x for x in source_rows if x['ecosystem'] == 'python']
    # Independent count: normalized current identity set vs baseline multiset.
    by_name = {}
    for row in raw_python:
        by_name.setdefault(normalize(row['name']), []).append(row['path'])
    if len(set(manifest_names)) != existing or len(by_name) != existing:
        errors.append('distinct identity count mismatch')
    if len(raw_python) != len(covered):
        errors.append('baseline manifest count mismatch')
    if len(private) != len([x for x in source_rows if x['ecosystem'] == 'javascript']):
        errors.append('private application count mismatch')
    return {'record_type': 'NAMING_AND_INVENTORY_CHECK_NOT_RELEASE_QUALIFICATION',
            'audited_base_sha': catalog['audited_base_sha'],
            'naming_status': 'FAIL' if errors else 'PASS', 'errors': errors,
            'python_manifest_count': len(covered), 'existing_distribution_candidates': existing,
            'planned_additional_packages': planned, 'roadmap_package_count': existing+planned,
            'excluded_private_applications': len(private),
            'version_reconciliation_actions': version_actions,
            'release_qualification': 'NOT_EVALUATED', 'registry_publication': 'NOT_EVALUATED'}


if __name__ == '__main__':
    result = check()
    print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result['naming_status'] == 'PASS' else 1)
