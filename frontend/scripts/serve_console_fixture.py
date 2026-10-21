"""LOCAL UI TEST HARNESS ONLY; not a substitute backend or production runner.

Executes current-source route/session/status functions with deterministic owner
fixtures. Guardian is intentionally unavailable; no fabricated mining receipts.
"""
import ast
import hashlib
import json
import os
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse, parse_qs
from test_console_contract import module, fixture, SOURCE, ROOT

scope=module(); fixture(scope)
os.environ['PYTHIA_OPERATOR_PRINCIPALS_JSON']=json.dumps({'fixture-owner':{'role':'ceo','token_sha256':hashlib.sha256(b'ui-test-only').hexdigest()}})
scope.update({'urlparse':urlparse,'parse_qs':parse_qs,'now_iso':lambda:'2026-10-20T23:00:00Z','_audit':lambda:SimpleNamespace(append=lambda *a,**k:None)})
tree=ast.parse(SOURCE.read_text());handler=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_Handler')
for name in ['_route_get','_control_session']:
    fn=next(n for n in handler.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(SOURCE),'exec'),scope)

class UIHandler(SimpleHTTPRequestHandler):
    _route_get=scope['_route_get'];_control_session=scope['_control_session']
    def _json(self,status,payload):
        body=json.dumps(payload).encode();self.send_response(int(status));self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def _guardian_preflight(self,path):
        self._json(HTTPStatus.SERVICE_UNAVAILABLE, {'reason':'test_harness_guardian_unavailable'});return False
    def _static_or_404(self,path): return super().do_GET()
    def do_GET(self):
        if self.path.startswith('/api/'):
            try:self._route_get()
            except Exception as exc:self._json(500,{'error':type(exc).__name__})
        else:super().do_GET()
    def log_message(self,*args):pass  # no credentials in output

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);a=parser.parse_args()
    print('TEST FIXTURE ONLY — current-source HTTP functions, deterministic owner dependencies',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),partial(UIHandler,directory=str(ROOT/'dist/public'))).serve_forever()
