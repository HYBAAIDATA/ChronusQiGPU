#!/usr/bin/env python3
"""Local evidence preview; reads capacity artifacts from the committed Git tree."""
import argparse
import hashlib
import html
import json
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = re.compile(r'artifacts/capacity/([0-9a-f]{64})\.json\Z')
ROUTES = ('claims', 'artifacts', 'refusals', 'status', 'incidents', 'charter', 'contact')


def esc(value):
    return html.escape(str(value), quote=True)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)


def committed_artifacts(root):
    """Fail closed unless Git HEAD, exact content address and JSON all verify."""
    listing = git(root, 'ls-tree', '-r', '--name-only', 'HEAD', '--', 'artifacts/capacity').decode('utf-8').splitlines()
    out = {}
    for path in listing:
        match = ARTIFACT.fullmatch(path)
        if not match:
            if path.endswith('.json'):
                raise ValueError('artifact filename is not a content address')
            continue
        blob = git(root, 'show', 'HEAD:' + path)
        if hashlib.sha256(blob).hexdigest() != match.group(1):
            raise ValueError('committed artifact hash mismatch')
        data = json.loads(blob)
        for key in ('hardware_spec', 'source', 'sample_hash_sha256', 'command', 'raw_stdout', 'per_class', 'label'):
            if key not in data:
                raise ValueError('incomplete artifact')
        out[match.group(1)] = (blob, data)
    return out


def token_status(root):
    """Report scan state; absence or error is unknown, not a pass."""
    checker = root / 'scripts/ci/check_forbidden_claims.py'
    if not checker.exists():
        return 'Claim token gate unavailable.'
    try:
        result = subprocess.run(['python3', str(checker)], cwd=root, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return 'Claim token gate unavailable.'
    if result.returncode == 0:
        return 'Claim token gate passed for this checkout; this does not prove semantic claim coverage.'
    return 'Claim token gate failed or could not complete; see CI for details.'


def layout(title, body):
    nav = ' '.join(f'<a href="/{x}">{esc(x.title())}</a>' for x in ROUTES)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)} | Storage evidence preview</title></head><body>'
            f'<nav aria-label="Trust pages">{nav}</nav><main><h1>{esc(title)}</h1>{body}'
            '</main></body></html>')


def page(root, name):
    if name == 'claims':
        body = ('<p>Product capacity and performance claims are withdrawn pending evidence. '
                'No product data class is currently claimed.</p><p>' + esc(token_status(root)) + '</p>'
                '<p>The existing <a href="https://github.com/hybadatadevops1/Chronusv2/blob/main/docs/claim-audit.md">claim audit</a> '
                'records earlier dispositions. This preview does not establish a complete repository-wide claim inventory.</p>')
    elif name == 'artifacts':
        try:
            artifacts = committed_artifacts(root)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError):
            return layout('Artifacts', '<p role="alert">Committed artifact source unavailable or invalid.</p>')
        body = ('<p>Reference measurements are not product capacity claims. '
                'This library covers committed capacity artifacts; other performance evidence has not been inventoried.</p>')
        if not artifacts:
            body += '<p>No committed capacity artifacts found.</p>'
        for ident, (_, a) in sorted(artifacts.items()):
            body += (f'<section><h2><a href="/artifacts/{ident}.json">{ident}</a></h2>'
                     f'<p>{esc(a["label"])}</p><dl><dt>Source commit</dt><dd>{esc(a["source"].get("commit", "unavailable"))}</dd>'
                     f'<dt>Dataset hash</dt><dd>{esc(a["sample_hash_sha256"])}</dd>'
                     f'<dt>Measurement environment</dt><dd><pre>{esc(json.dumps(a["hardware_spec"], indent=2))}</pre></dd>'
                     f'<dt>Command</dt><dd><pre>{esc(a["command"])}</pre></dd>'
                     f'<dt>Raw measurement output</dt><dd><pre>{esc(a["raw_stdout"])}</pre></dd></dl>'
                     '<p>Download the artifact for all recorded fields. Reproduce with the repository harness; timings vary.</p></section>')
    elif name == 'refusals':
        body = ('<ul><li>No product capacity or performance claim.</li>'
                '<li>No product data class has been qualified; a reference sample does not establish class-wide benefit.</li>'
                '<li>No corruption recovery capability is claimed for the reference codec.</li>'
                '<li>No durable distributed, managed, or production deployment is claimed.</li>'
                '<li>No certification or authorization is claimed.</li></ul>'
                '<p>Classes where the product does not help have not been established; measurements are needed rather than assumptions.</p>')
    elif name == 'status':
        body = ('<p>Operational status source not yet connected; this page will show status when the source is available.</p>'
                '<p>Historical incident source is not connected. <a href="/incidents">Incident log</a></p>')
    elif name == 'incidents':
        body = ('<p>Incident history source is not connected; completeness is unknown.</p>'
                '<p>Use the repository post-mortem template when incident data is available.</p>')
    elif name == 'charter':
        body = ('<p>The reference codec represents bytes using prime symbols and verifies integrity on decode. '
                'It is a reference implementation, not the discovery-specific product codec.</p>'
                '<p>It does not establish recovery, product capacity or production readiness.</p>'
                '<p>Build rule: no claim without an artifact. To verify a measurement, download the committed JSON '
                'from <a href="/artifacts">artifacts</a>, verify its content hash, and run the harness on the stated sample and environment.</p>')
    else:
        body = '<p>Technical contact: [to be supplied by the team].</p>'
    return layout(name.title(), body)


def handler(root):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            match = re.fullmatch(r'/artifacts/([0-9a-f]{64})\.json', path)
            if match:
                try:
                    entry = committed_artifacts(root).get(match.group(1))
                except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError):
                    self.send_error(503, 'Committed artifact source unavailable')
                    return
                if entry is None:
                    self.send_error(404)
                    return
                self.respond(200, entry[0], 'application/json; charset=utf-8', download=match.group(1)+'.json')
                return
            name = path.removeprefix('/')
            if name not in ROUTES:
                self.send_error(404)
                return
            self.respond(200, page(root, name).encode('utf-8'), 'text/html; charset=utf-8')

        def respond(self, status, content, content_type, download=None):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; base-uri 'none'; form-action 'none'")
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="' + download + '"')
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8088)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(ROOT))
    print('Trust preview listening on loopback', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
