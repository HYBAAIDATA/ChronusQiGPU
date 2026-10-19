"""OIDC code + PKCE login with server-side expiring sessions and CSRF binding."""

import base64
import hashlib
import json
import secrets
import sqlite3
import time
import urllib.parse
import urllib.request

from contextlib import contextmanager
from cryptography.fernet import Fernet

from .control import Denied, Unavailable
from .billing import NoRedirect
from .identity import Identity


class Sessions:
    def __init__(
        self,
        path,
        *,
        origin,
        issuer,
        client_id,
        redirect_uri,
        authorization_url,
        token_url,
        verifier,
        encryption_key,
        client_secret=None
    ):
        for url in (origin, redirect_uri, authorization_url, token_url):
            p = urllib.parse.urlsplit(url)
            if p.scheme != "https" or not p.netloc or p.username or p.password or p.fragment:
                raise ValueError("HTTPS SSO configuration required")
        if urllib.parse.urlsplit(origin).path not in ("", "/"):
            raise ValueError("origin must not include a path")
        if not redirect_uri.startswith(origin.rstrip("/") + "/"):
            raise ValueError("callback origin mismatch")
        self.path = path
        self.origin = origin.rstrip("/")
        self.issuer = issuer
        self.client_id = client_id
        self.redirect = redirect_uri
        self.authorization = authorization_url
        self.token_url = token_url
        self.verifier = verifier
        self.secret = client_secret
        self.crypto = Fernet(encryption_key)
        with self._db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS web_sessions (
              hash TEXT PRIMARY KEY,subject TEXT,issuer TEXT,csrf TEXT,expires INTEGER);
              CREATE TABLE IF NOT EXISTS login_states (
              hash TEXT PRIMARY KEY,verifier TEXT,nonce TEXT,expires INTEGER);""")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _hash(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def start(self):
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        pkce = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(pkce.encode()).digest()).decode().rstrip("=")
        )
        with self._db() as db:
            db.execute("DELETE FROM login_states WHERE expires<=?", (int(time.time()),))
            db.execute(
                "INSERT INTO login_states VALUES(?,?,?,?)",
                (
                    self._hash(state),
                    self.crypto.encrypt(pkce.encode()).decode(),
                    nonce,
                    int(time.time()) + 300,
                ),
            )
        params = dict(
            client_id=self.client_id,
            redirect_uri=self.redirect,
            response_type="code",
            scope="openid profile",
            state=state,
            nonce=nonce,
            code_challenge=challenge,
            code_challenge_method="S256",
        )
        return state, self.authorization + "?" + urllib.parse.urlencode(params)

    def finish(self, state, code, cookie_state):
        if not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
            raise Denied("login state mismatch")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT verifier,nonce,expires FROM login_states WHERE hash=?", (self._hash(state),)
            ).fetchone()
            if not row or row[2] <= time.time():
                raise Denied("login state expired")
            db.execute("DELETE FROM login_states WHERE hash=?", (self._hash(state),))
        form = dict(
            grant_type="authorization_code",
            code=code,
            redirect_uri=self.redirect,
            client_id=self.client_id,
            code_verifier=self.crypto.decrypt(row[0].encode()).decode(),
        )
        if self.secret:
            form["client_secret"] = self.secret
        request = urllib.request.Request(
            self.token_url,
            data=urllib.parse.urlencode(form).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(request, timeout=10) as response:
                raw = response.read(131073)
                if len(raw) > 131072:
                    raise ValueError("token response exceeds bound")
                tokens = json.loads(raw)
            claims = self.verifier.claims(tokens["id_token"])
            if claims.get("nonce") != row[1]:
                raise ValueError("login nonce mismatch")
            ttl = min(3600, int(claims["exp"]) - int(time.time()))
            if ttl <= 0:
                raise ValueError("expired login")
            return self.create(Identity(claims["sub"], claims["iss"]), ttl)
        except Exception:
            raise Denied("SSO exchange failed") from None

    def create(self, identity, ttl=3600):
        handle = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(32)
        with self._db() as db:
            db.execute("DELETE FROM web_sessions WHERE expires<=?", (int(time.time()),))
            db.execute(
                "INSERT INTO web_sessions VALUES(?,?,?,?,?)",
                (
                    self._hash(handle),
                    identity.subject,
                    identity.issuer,
                    csrf,
                    int(time.time()) + min(ttl, 3600),
                ),
            )
        return handle

    def get(self, handle):
        if not handle or len(handle) > 256:
            raise Denied("session required")
        with self._db() as db:
            row = db.execute(
                "SELECT subject,issuer,csrf,expires FROM web_sessions WHERE hash=?",
                (self._hash(handle),),
            ).fetchone()
        if not row or row[3] <= time.time():
            raise Denied("session unavailable")
        return Identity(row[0], row[1]), row[2]

    def delete(self, handle):
        with self._db() as db:
            db.execute("DELETE FROM web_sessions WHERE hash=?", (self._hash(handle or ""),))
