# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Fleet authentication: shared token, mutual HMAC and optional TLS.

Every request and every response is authenticated with HMAC-SHA256 under a
key derived from the shared fleet token; the token itself never crosses the
network.

Request MAC over: method, path, node id, timestamp, nonce, SHA-256 of body.
Response MAC over: the request's nonce, status code, SHA-256 of body.

The coordinator rejects requests with a bad MAC, a timestamp outside the
allowed clock skew or a nonce it has already seen. A worker or client rejects
any response that is not MACed for its own request nonce, so a machine
without the token can neither join the fleet nor impersonate the
coordinator. HMAC gives authenticity and integrity, not confidentiality:
configure TLS (``tls_server_context`` / ``tls_client_context``) when tile
data must not be readable on the network.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import ssl
import threading
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from chronus.fleet.canonical import utc_now_ns
from chronus.fleet.errors import AuthenticationError

logger = logging.getLogger(__name__)
AUTH_SCHEME = "chronus-fleet-hmac-v1"
TOKEN_ENV = "CHRONUS_FLEET_TOKEN"
MIN_TOKEN_CHARS = 32
MAX_CLOCK_SKEW_NS = 300 * 1_000_000_000
H_NODE = "X-Chronus-Fleet-Node"
H_TIME = "X-Chronus-Fleet-Timestamp"
H_NONCE = "X-Chronus-Fleet-Nonce"
H_BODY = "X-Chronus-Fleet-Body-SHA256"
H_MAC = "X-Chronus-Fleet-MAC"
H_SCHEME = "X-Chronus-Fleet-Auth"


def new_token() -> str:
    """A fresh 256-bit fleet token (URL-safe text)."""
    return secrets.token_urlsafe(32)


def secure_secret_file(path: str | Path) -> Path:
    """Restrict a secret file to its owner (mode 600) and say so if the filesystem cannot."""
    path = Path(path).expanduser()
    if os.name != "posix":
        return path
    if path.stat().st_mode & 0o077:
        os.chmod(path, 0o600)
        if path.stat().st_mode & 0o077:
            logger.warning("%s: this filesystem does not keep permission bits; protect the file by other means", path)
    return path


def load_token(token: str | None = None, token_file: str | Path | None = None) -> str:
    """Token from an argument, a file or CHRONUS_FLEET_TOKEN, in that order."""
    if token is None and token_file is not None:
        path = secure_secret_file(token_file)
        token = path.read_text(encoding="utf-8").strip()
    if token is None:
        token = os.environ.get(TOKEN_ENV)
    if not token:
        raise AuthenticationError("no fleet token: pass --token, --token-file or set CHRONUS_FLEET_TOKEN")
    token = token.strip()
    if len(token) < MIN_TOKEN_CHARS:
        raise AuthenticationError(f"fleet token must be at least {MIN_TOKEN_CHARS} characters")
    return token


def write_token_file(path: str | Path, token: str) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    return secure_secret_file(path)


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


class ReplayCache:
    """Remembers nonces for the skew window; bounded so it cannot grow without end."""

    def __init__(self, capacity: int = 200_000) -> None:
        self._seen: OrderedDict[str, int] = OrderedDict()
        self._capacity = capacity
        self._lock = threading.Lock()

    def check_and_add(self, nonce: str, now_ns: int) -> bool:
        with self._lock:
            horizon = now_ns - 2 * MAX_CLOCK_SKEW_NS
            while self._seen and next(iter(self._seen.values())) < horizon:
                self._seen.popitem(last=False)
            if nonce in self._seen:
                return False
            if len(self._seen) >= self._capacity:
                return False  # Never evict a nonce while its request can still be valid.
            self._seen[nonce] = now_ns
            return True


class FleetAuth:
    """HMAC signing and verification under a key derived from the fleet token."""

    def __init__(self, token: str) -> None:
        secret = token.encode("utf-8")
        self._key = hmac.new(secret, b"chronus-fleet/v1/mac-key", hashlib.sha256).digest()
        self.fleet_tag = hmac.new(secret, b"chronus-fleet/v1/fleet-tag", hashlib.sha256).hexdigest()[:16]

    def _mac(self, *parts: str) -> str:
        return hmac.new(self._key, "\n".join(parts).encode("utf-8"), hashlib.sha256).hexdigest()

    def sign_request(self, method: str, path: str, node_id: str, body: bytes) -> dict[str, str]:
        timestamp = str(utc_now_ns())
        nonce = secrets.token_hex(16)
        digest = body_digest(body)
        return {
            H_SCHEME: AUTH_SCHEME,
            H_NODE: node_id,
            H_TIME: timestamp,
            H_NONCE: nonce,
            H_BODY: digest,
            H_MAC: self._mac("REQ", method.upper(), path, node_id, timestamp, nonce, digest),
        }

    def verify_request(
        self, method: str, path: str, headers: Mapping[str, str], body: bytes, replay: ReplayCache
    ) -> tuple[str, str]:
        """(node_id, nonce) of an authentic, fresh request; AuthenticationError otherwise."""
        values = {name: headers.get(name) for name in (H_SCHEME, H_NODE, H_TIME, H_NONCE, H_BODY, H_MAC)}
        missing = [name for name, value in values.items() if not isinstance(value, str) or not value]
        if missing:
            raise AuthenticationError(f"missing authentication headers: {', '.join(missing)}")
        scheme, node_id, timestamp = values[H_SCHEME], values[H_NODE], values[H_TIME]
        nonce, digest, mac = values[H_NONCE], values[H_BODY], values[H_MAC]
        if scheme != AUTH_SCHEME:
            raise AuthenticationError("unsupported authentication scheme")
        if len(nonce) != 32 or not node_id or len(node_id) > 200:
            raise AuthenticationError("malformed authentication header")
        if not hmac.compare_digest(digest, body_digest(body)):
            raise AuthenticationError("body digest mismatch")
        expected = self._mac("REQ", method.upper(), path, node_id, timestamp, nonce, digest)
        if not hmac.compare_digest(mac, expected):
            raise AuthenticationError("request MAC does not verify")
        now = utc_now_ns()
        try:
            stamp = int(timestamp)
        except ValueError as exc:
            raise AuthenticationError("malformed timestamp") from exc
        if abs(now - stamp) > MAX_CLOCK_SKEW_NS:
            raise AuthenticationError("request timestamp outside the allowed clock skew")
        if not replay.check_and_add(nonce, now):
            raise AuthenticationError("replayed request nonce")
        return node_id, nonce

    def sign_response(self, request_nonce: str, status: int, body: bytes) -> dict[str, str]:
        digest = body_digest(body)
        return {
            H_SCHEME: AUTH_SCHEME,
            H_BODY: digest,
            H_MAC: self._mac("RESP", request_nonce, str(int(status)), digest),
        }

    def verify_response(self, request_nonce: str, status: int, headers: Mapping[str, str], body: bytes) -> None:
        mac = headers.get(H_MAC)
        digest = headers.get(H_BODY)
        if not mac or not digest:
            raise AuthenticationError("response is not authenticated: is this a Chronus fleet coordinator?")
        if not hmac.compare_digest(digest, body_digest(body)):
            raise AuthenticationError("response body digest mismatch")
        if not hmac.compare_digest(mac, self._mac("RESP", request_nonce, str(int(status)), digest)):
            raise AuthenticationError("response MAC does not verify (wrong token or impostor coordinator)")


def tls_server_context(cert_file: str | Path, key_file: str | Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(Path(cert_file).expanduser()), str(Path(key_file).expanduser()))
    return context


def tls_client_context(ca_file: str | Path | None = None) -> ssl.SSLContext:
    """Verifying client context; ca_file pins a private or self-signed certificate."""
    context = ssl.create_default_context(cafile=str(Path(ca_file).expanduser()) if ca_file else None)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def generate_self_signed(
    out_dir: str | Path, hostnames: list[str], days: int = 825
) -> tuple[Path, Path]:
    """ECDSA P-256 certificate and key for the coordinator; SANs from hostnames/IPs."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    if not hostnames:
        raise ValueError("at least one hostname or IP address is needed for the certificate")
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    names: list[x509.GeneralName] = []
    for name in hostnames:
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            names.append(x509.DNSName(name))
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0]),
                         x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HYBA Chronus fleet")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=True,
                crl_sign=True, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = out / "coordinator-cert.pem"
    key_path = out / "coordinator-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    return cert_path, key_path
