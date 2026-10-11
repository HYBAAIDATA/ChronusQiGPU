"""Hermetic identity guard tests; not package/registry/production qualification."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('publication_names', ROOT/'packaging/check_publication_catalog.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class PublicationCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        cat = json.loads((ROOT/'packaging/publication_catalog.json').read_text())
        paths = {'packaging/publication_catalog.json', 'packaging/publication_inventory_baseline.json'}
        for row in cat['packages']:
            paths.update(row['manifest_paths'])
        paths.update(row['path'] for row in cat['private_applications'])
        for path in paths:
            out = self.root/path
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/path, out)

    def edit_catalog(self, mutate):
        p = self.root/'packaging/publication_catalog.json'
        cat = json.loads(p.read_text())
        mutate(cat)
        p.write_text(json.dumps(cat))

    def assert_rejected(self):
        self.assertEqual(M.check(self.root)['naming_status'], 'FAIL')

    def test_counts_are_derived_and_not_readiness(self):
        row = M.check(self.root)
        self.assertEqual(row['naming_status'], 'PASS', row['errors'])
        self.assertEqual((row['python_manifest_count'], row['existing_distribution_candidates'],
                          row['planned_additional_packages'], row['roadmap_package_count'],
                          row['excluded_private_applications']), (14, 13, 1, 14, 4))
        self.assertEqual(row['release_qualification'], 'NOT_EVALUATED')
        self.assertNotIn('production_ready', row)
        self.assertEqual(len(row['version_reconciliation_actions']), 0)

    def test_duplicate_catalog_is_not_an_extra_package(self):
        self.edit_catalog(lambda c: c['packages'].append(c['packages'][0].copy()))
        self.assert_rejected()

    def test_missing_scaffold_fails(self):
        (self.root/'packaging/theseus/pyproject.toml').unlink()
        self.assert_rejected()

    def test_unknown_manifest_fails(self):
        (self.root/'unexpected').mkdir()
        (self.root/'unexpected/pyproject.toml').write_text('[project]\nname="unknown"\n')
        self.assert_rejected()

    def test_legacy_identity_fails(self):
        p = self.root/'packaging/theseus/pyproject.toml'
        p.write_text(p.read_text().replace('hyba-theseus-storage', 'hyba-theseus'))
        self.assert_rejected()

    def test_legacy_dependency_fails(self):
        p = self.root/'packaging/ovid/pyproject.toml'
        p.write_text(p.read_text().replace('hyba-theseus-storage==', 'hyba-theseus=='))
        self.assert_rejected()

    def test_private_application_cannot_be_published(self):
        p = self.root/'frontend/package.json'
        row = json.loads(p.read_text());row['private'] = False;p.write_text(json.dumps(row))
        self.assert_rejected()

    def test_cli_removal_fails(self):
        p = self.root/'packaging/theseus/pyproject.toml'
        p.write_text(p.read_text().replace('hyba-theseus =', 'changed-cli ='))
        self.assert_rejected()

    def test_import_ownership_change_fails(self):
        p = self.root/'packaging/theseus/pyproject.toml'
        p.write_text(p.read_text().replace('"aethel.*"', '"replacement.*"'))
        self.assert_rejected()

    def test_first_public_version_cannot_be_generation_17(self):
        self.edit_catalog(lambda c: c['packages'][0].update(first_public_version='17.0.0'))
        self.assert_rejected()

    def test_source_binding_cannot_drift(self):
        self.edit_catalog(lambda c: c.update(audited_base_sha='0'*40))
        self.assert_rejected()

    def test_euclid_is_one_identity_with_two_metadata_definitions(self):
        c = json.loads((self.root/'packaging/publication_catalog.json').read_text())
        row, = [x for x in c['packages'] if x['system'] == 'EUCLID']
        self.assertEqual(len(row['manifest_paths']), 2)
        self.assertEqual(row['canonical_manifest'], 'packaging/euclid-engine/pyproject.toml')


if __name__ == '__main__':
    unittest.main()
