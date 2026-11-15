import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trustserver', ROOT/'trust/server.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class TrustPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        subprocess.run(['git', 'init', '-q', str(cls.root)], check=True)
        (cls.root/'artifacts/capacity').mkdir(parents=True)
        raw = next((ROOT/'artifacts/capacity').glob('*.json')).read_bytes()
        cls.ident = hashlib.sha256(raw).hexdigest()
        (cls.root/'artifacts/capacity'/f'{cls.ident}.json').write_bytes(raw)
        subprocess.run(['git', 'add', '.'], cwd=cls.root, check=True)
        subprocess.run(['git', '-c', 'user.email=test@example.invalid', '-c', 'user.name=test', 'commit', '-qm', 'fixture'], cwd=cls.root, check=True)
        cls.server = service.ThreadingHTTPServer(('127.0.0.1', 0), service.handler(cls.root))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.raw = raw

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.tmp.cleanup()

    def get(self, path):
        return urlopen(self.url + path, timeout=5).read()

    def test_seven_pages_reachable_and_truthful(self):
        for name in service.ROUTES:
            with self.subTest(name=name):
                self.assertIn(b'<h1>', self.get('/'+name))
        self.assertIn(b'not yet connected', self.get('/status'))
        self.assertIn(b'completeness is unknown', self.get('/incidents'))
        self.assertIn(b'to be supplied by the team', self.get('/contact'))
        self.assertIn(b'not establish a complete', self.get('/claims'))
        self.assertIn(b'no claim without an artifact', self.get('/charter'))
        self.assertIn(b'withdrawn', self.get('/claims'))
        self.assertIn(b'capacity artifacts', self.get('/artifacts'))
        self.assertIn(b'No product data class has been qualified', self.get('/refusals'))
        self.assertIn(b'preview', self.get('/charter'))

    def test_html_escape(self):
        self.assertEqual(service.esc('<script>'), '&lt;script&gt;')

    def test_download_hash_and_committed_only(self):
        self.assertIn(self.ident.encode(), self.get('/artifacts'))
        self.assertEqual(self.get('/artifacts/'+self.ident+'.json'), self.raw)
        (self.root/'artifacts/capacity'/f'{self.ident}.json').write_text('tampered working tree')
        self.assertEqual(self.get('/artifacts/'+self.ident+'.json'), self.raw)
        with self.assertRaises(HTTPError): self.get('/artifacts/'+'0'*64+'.json')

    def test_fail_closed_when_no_git(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(subprocess.CalledProcessError): service.committed_artifacts(Path(d))

    def test_invalid_committed_content_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); subprocess.run(['git','init','-q',d],check=True)
            (root/'artifacts/capacity').mkdir(parents=True)
            (root/'artifacts/capacity'/('0'*64+'.json')).write_text('{}')
            subprocess.run(['git','add','.'],cwd=root,check=True)
            subprocess.run(['git','-c','user.email=test@example.invalid','-c','user.name=test','commit','-qm','bad'],cwd=root,check=True)
            with self.assertRaises(ValueError): service.committed_artifacts(root)


if __name__ == '__main__': unittest.main()
