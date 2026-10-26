"""Focused documentation boundary regressions, independent of the mathematical engine."""
import copy
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

SPEC = importlib.util.spec_from_file_location('turing_docs', Path(__file__).with_name('turing_docs.py'))
docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docs)


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = docs.load()

    def reject(self, mutate):
        value = copy.deepcopy(self.manifest)
        mutate(value)
        with self.assertRaises(ValueError):
            docs.validate(value, today=date(2026, 10, 19))

    def test_current_manifest(self):
        self.assertEqual(len(docs.validate(self.manifest, date(2026, 10, 19))), 25)

    def test_duplicate_slug(self):
        self.reject(lambda m: m['pages'].append(copy.deepcopy(m['pages'][0])))

    def test_unsafe_slug(self):
        self.reject(lambda m: m['pages'][0].update(slug='../escape'))

    def test_missing_owner(self):
        self.reject(lambda m: m['pages'][0].pop('owner'))

    def test_stale_version(self):
        self.reject(lambda m: m['pages'][0].update(version='0.0.0'))

    def test_future_verification(self):
        self.reject(lambda m: m['pages'][0].update(last_verified='2099-01-01'))

    def test_due_before_review(self):
        self.reject(lambda m: m['pages'][0].update(review_due='2026-10-01'))

    def test_expired_review(self):
        with self.assertRaisesRegex(ValueError, 'overdue'):
            docs.validate(self.manifest, date(2026, 12, 1))

    def test_fictional_approval(self):
        self.reject(lambda m: m['pages'][0].update(status='approved'))

    def test_audience_leak(self):
        self.reject(lambda m: next(p for p in m['pages'] if p['slug']=='product/capabilities').update(audience='internal'))

    def test_missing_page(self):
        self.reject(lambda m: m['pages'].pop(0))

    def test_no_publication_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'publication unsupported'):
                docs.build(self.manifest, 'public', Path(tmp), preview=False)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out/'unrelated').write_text('keep')
            with self.assertRaisesRegex(ValueError, 'fresh or empty'):
                docs.build(self.manifest, 'public', out)
            self.assertEqual((out/'unrelated').read_text(), 'keep')

    def test_all_audience_outputs_and_links(self):
        for audience, expected in [('public', 10), ('customer', 11), ('internal', 25)]:
            with self.subTest(audience=audience), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                receipt = docs.build(self.manifest, audience, out)
                self.assertEqual(receipt['pages'], expected)
                self.assertFalse(receipt['approval'])
                entries = json.loads((out/'search-index.json').read_text())
                self.assertEqual(len(entries), expected)
                if audience=='public':
                    self.assertFalse((out/'customer').exists())
                    self.assertFalse((out/'internal').exists())
                    self.assertFalse((out/'templates').exists())
                    self.assertFalse((out/'manifest.json').exists())
                    for row in entries:
                        self.assertNotIn('internal/', row['url'])
                        self.assertNotIn('customer/', row['url'])
                        self.assertNotIn('OWNER_DECLARATIONS', row['text'])
                for path in out.rglob('*.html'):
                    markup = docs.Markup(path.read_text())
                    for link in markup.links:
                        split = urlsplit(link)
                        if split.scheme:
                            continue
                        target = (path.parent/unquote(split.path)).resolve() if split.path else path
                        self.assertTrue(target.is_file(), str(target))
                        if split.fragment:
                            self.assertIn(split.fragment, docs.Markup(target.read_text()).ids)

    def reject_text(self, addition):
        original = Path.read_text
        target = (docs.DOCS / 'index.md').resolve()
        def altered(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            return value + addition if path.resolve() == target else value
        with patch.object(Path, 'read_text', altered), self.assertRaises((ValueError, SyntaxError)):
            docs.validate(self.manifest, date(2026, 10, 19))

    def test_broken_anchor(self):
        self.reject_text('\n[Broken](#no-such-heading)\n')

    def test_missing_link(self):
        self.reject_text('\n[Missing](missing-page.md)\n')

    def test_public_to_internal_link(self):
        self.reject_text('\n[Restricted](internal/operations.md)\n')

    def test_secret_pattern(self):
        self.reject_text('\n-----BEGIN PRIVATE KEY-----\n')

    def test_raw_script(self):
        self.reject_text('\n<script>alert(1)</script>\n')

    def test_invalid_python_sample(self):
        self.reject_text('\n```python\nif :\n```\n')

    def test_review_date_not_mutated(self):
        before = json.dumps(self.manifest, sort_keys=True)
        docs.validate(self.manifest, date(2026, 10, 19))
        self.assertEqual(before, json.dumps(self.manifest, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
