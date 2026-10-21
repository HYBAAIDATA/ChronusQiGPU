"""Validate and build audience-isolated TURING documentation review previews.

Never deploys or approves claims. Source Markdown is trusted repository content,
not arbitrary user input; this is not a general-purpose HTML sanitizer.
"""
from __future__ import annotations

import argparse
import ast
from datetime import date
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/turing"
AUDIENCES = {"public": {"public"}, "customer": {"public", "customer"},
             "internal": {"public", "customer", "internal"}}


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links = set(), []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise ValueError("duplicate HTML anchor: " + attrs["id"])
            self.ids.add(attrs["id"])
        if tag in {"a", "img"}:
            self.links.append(attrs.get("href" if tag == "a" else "src", ""))


def render(text):
    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
    body = md.convert(text)
    return md, body, Markup(body)


def load():
    return json.loads((DOCS / "manifest.json").read_text())


def validate(manifest, today=None):
    today = today or date.today()
    pages = manifest["pages"]
    if manifest.get("schema") != "turing.docs.v1":
        raise ValueError("unknown manifest schema")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("baseline", "")):
        raise ValueError("baseline must be an inspected commit")
    if len({p["slug"] for p in pages}) != len(pages):
        raise ValueError("duplicate navigation slug")
    if not pages or pages[0]["slug"] != "index":
        raise ValueError("navigation must begin at index")
    paths = {}
    for p in pages:
        if not re.fullmatch(r"[a-z0-9]+(?:[-/][a-z0-9]+)*", p["slug"]):
            raise ValueError("unsafe slug")
        path = DOCS / (p["slug"] + ".md")
        if not path.is_file():
            raise ValueError("missing page: " + str(path))
        paths[path.resolve()] = p
    if set(DOCS.rglob("*.md")) != {DOCS / (p["slug"] + ".md") for p in pages}:
        raise ValueError("unlisted Markdown page / orphan navigation")
    for path, p in paths.items():
        for field in ("title", "section", "owner", "version", "last_verified",
                      "review_due", "verification", "audience", "status"):
            if not p.get(field):
                raise ValueError("missing metadata: " + field)
        if p["audience"] not in AUDIENCES or p["status"] not in {"draft", "approved"}:
            raise ValueError("invalid audience / status")
        verified, due = date.fromisoformat(p["last_verified"]), date.fromisoformat(p["review_due"])
        if verified > today or due < verified:
            raise ValueError("invalid actual review dates")
        if due < today:
            raise ValueError("review overdue: " + p["slug"])
        if p["version"] != manifest["version"]:
            raise ValueError("stale page version")
        if p["status"] == "approved" and (not p.get("approval_reference") or "pending" in p["owner"]):
            raise ValueError("approval requires named accountability and review reference")
        text = path.read_text()
        if not text.startswith("# " + p["title"] + "\n"):
            raise ValueError("title/manifest drift")
        if sum(line.startswith("# ") for line in text.splitlines()) != 1:
            raise ValueError("one H1 required")
        if len(re.findall(r"^```", text, re.M)) % 2:
            raise ValueError("unclosed fence")
        for sample in re.findall(r"```python\n(.*?)\n```", text, re.S):
            ast.parse(sample)
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        if re.search(r"<[A-Za-z!/]", prose):
            raise ValueError("raw HTML is not allowed in portal Markdown")
        _, _, markup = render(text)
        # Automatic patterns are deliberately narrow; human claim/disclosure review remains required.
        if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}", text):
            raise ValueError("possible secret in documentation")
        if p["audience"] == "public":
            if re.search(r"world.s first|guaranteed outcomes|ISO.?27001 certified|SOC.?2 certified", text, re.I):
                raise ValueError("unreviewed public claim pattern")
        for link in markup.links:
            parsed = urlsplit(link)
            if parsed.scheme:
                if parsed.scheme != "https":
                    raise ValueError("unsupported link scheme")
                if p["audience"] == "public" and parsed.netloc in {"github.com", "api.github.com", "raw.githubusercontent.com"}:
                    raise ValueError("public page links unreviewed repository material")
                continue
            if parsed.netloc or parsed.path.startswith("/"):
                raise ValueError("absolute or network-path link not supported")
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not target.is_relative_to(ROOT) or not target.is_file():
                raise ValueError("missing or escaping local link: " + link)
            other = paths.get(target)
            if target.is_relative_to(DOCS) and other is None:
                raise ValueError("unlisted portal destination")
            if other and other["audience"] not in AUDIENCES[p["audience"]]:
                raise ValueError("audience leak: " + link)
            if p["audience"] != "internal" and other is None:
                raise ValueError("non-internal page exposes repository file")
            if parsed.fragment and target.suffix == ".md":
                if unquote(parsed.fragment) not in render(target.read_text())[2].ids:
                    raise ValueError("missing anchor: " + link)
    ledger = json.loads((DOCS / "internal/claims.json").read_text())
    for c in ledger["claims"]:
        if not all(c.get(k) for k in ("id", "claim", "status", "source_commit", "source", "verification", "approval")):
            raise ValueError("incomplete claim evidence record")
        if not (ROOT / c["source"]).is_file():
            raise ValueError("missing claim source")
    return pages


def output_link(current, target):
    return os.path.relpath(target, Path(current).parent).replace(os.sep, "/")


def build(manifest, audience, out, preview=True):
    all_pages = validate(manifest)
    pages = [p for p in all_pages if p["audience"] in AUDIENCES[audience]]
    if not preview:
        raise ValueError("publication unsupported: approved deployment/claim review is separate")
    out = out.resolve()
    # Never remove a checkout or arbitrary non-build directory on a bad CLI invocation.
    if out.exists() and any(out.iterdir()):
        raise ValueError("output must be a fresh or empty directory")
    if out == ROOT or out.is_relative_to(DOCS):
        raise ValueError("unsafe output directory")
    out.mkdir(parents=True, exist_ok=True)
    for name in ("portal.css", "portal.js"):
        shutil.copyfile(DOCS / "assets" / name, out / name)
    by_path = {(DOCS / (p["slug"] + ".md")).resolve(): p for p in pages}
    search = []
    hashes = {}
    for i, p in enumerate(pages):
        source = DOCS / (p["slug"] + ".md")
        text = source.read_text()
        md, body, _ = render(text)
        current = p["slug"] + ".html"
        def rewrite(match):
            url = match.group(2)
            split = urlsplit(url)
            if split.scheme or not split.path:
                return match.group(0)
            target = (source.parent / unquote(split.path)).resolve()
            if target in by_path:
                dest = output_link(current, by_path[target]["slug"] + ".html")
            else:
                dest = "https://github.com/PhiEnterprise1/EuclidPhiEnterprise/blob/" + os.environ.get("GITHUB_SHA", manifest["baseline"]) + "/" + target.relative_to(ROOT).as_posix()
            if split.fragment:
                dest += "#" + split.fragment
            return match.group(1) + escape(dest, quote=True) + match.group(3)
        body = re.sub(r'(href=")([^"]+)(")', rewrite, body)
        asset = output_link(current, "portal.css")
        nav = []
        section = None
        for q in pages:
            if q["section"] != section:
                section = q["section"]
                nav.append('<p class="nav-section">' + escape(section) + '</p>')
            active = ' aria-current="page"' if q == p else ''
            nav.append('<a' + active + ' href="' + output_link(current, q["slug"] + ".html") + '">' + escape(q["title"]) + '</a>')
        pager = []
        for label, j in (("Previous", i - 1), ("Next", i + 1)):
            if 0 <= j < len(pages):
                q = pages[j]
                pager.append('<a href="' + output_link(current, q["slug"] + '.html') + '">' + label + ': ' + escape(q["title"]) + '</a>')
        report = '<a href="' + escape(manifest['defects']) + '">Report a documentation defect</a>' if audience == 'internal' else 'Report inaccuracies through your established HYBA contact; do not include secrets.'
        banner = 'Candidate review preview · ' + audience + ' audience · not publication approval'
        html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{escape(p['title'])} — TURING</title><link rel="stylesheet" href="{asset}"></head>
<body><a class="skip" href="#main">Skip to content</a>
<header><a class="brand" href="{output_link(current,'index.html')}">TURING<small>COMPUTATIONAL INTELLIGENCE</small></a><span>Documentation</span><button id="menu" type="button" aria-controls="navigation" aria-expanded="false">Navigation</button></header>
<div class="banner">{banner}</div><div class="shell">
<nav id="navigation" aria-label="Documentation">{''.join(nav)}</nav>
<main id="main" tabindex="-1"><p class="eyebrow">DOCUMENTATION / {escape(p['section'].upper())}</p>
<label for="search">Search this documentation audience</label><input id="search" type="search" placeholder="Search guides, concepts and interfaces…" autocomplete="off"><p id="search-status" role="status"></p><ul id="search-results"></ul>
<article>{body}</article><dl class="metadata"><dt>Status / version</dt><dd>{escape(p['status'])} / {escape(p['version'])}</dd><dt>Owner</dt><dd>{escape(p['owner'])}</dd><dt>Last source review</dt><dd>{p['last_verified']} — {escape(p['verification'])}</dd></dl><div class="pager">{''.join(pager)}</div><footer>{report}</footer></main>
<aside aria-label="On this page"><p class="nav-section">ON THIS PAGE</p>{md.toc}</aside></div>
<script src="{output_link(current,'portal.js')}" defer></script></body></html>'''
        dest = out / current
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html)
        search.append(dict(title=p["title"], url=current, text=re.sub(r"[#`*|]", " ", text)))
        hashes[p['slug']] = hashlib.sha256(text.encode()).hexdigest()
    (out / "search-index.json").write_text(json.dumps(search, ensure_ascii=False))
    receipt = dict(schema='turing.docs.build.v1', audience=audience,
                   version=manifest['version'], pages=len(pages),
                   source_identity=os.environ.get('GITHUB_SHA', 'LOCAL_DOCUMENTATION_PREVIEW_NOT_COMMIT_BOUND'),
                   content_hashes=hashes, preview=True, approval=False)
    (out / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'build'])
    parser.add_argument('--audience', choices=AUDIENCES, default='public')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    manifest = load()
    if args.command == 'check':
        print(f'Validated {len(validate(manifest))} pages: metadata, links/anchors, navigation, sample syntax, audience boundaries and claim records')
    else:
        if args.out is None:
            parser.error('build requires --out (fresh directory)')
        print(json.dumps(build(manifest, args.audience, args.out)))


if __name__ == '__main__':
    main()
