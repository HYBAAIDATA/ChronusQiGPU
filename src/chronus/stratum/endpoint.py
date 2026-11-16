"""Parse pool endpoint URIs into a (host, port, tls) triple.

Stratum pools advertise endpoints as URIs ("stratum+tcp://host:port"), but
asyncio.open_connection needs a bare hostname. Parsing here keeps the scheme
out of the socket layer and gives TLS a single place to be switched on.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

# Scheme -> use TLS. "stratum" alone is the pre-2018 spelling and was cleartext.
_SCHEMES: dict[str, bool] = {
    "stratum+tcp": False,
    "stratum": False,
    "tcp": False,
    "stratum+ssl": True,
    "stratum+tls": True,
    "ssl": True,
    "tls": True,
}

_DEFAULT_PORT = 3333


@dataclass(frozen=True)
class PoolEndpoint:
    host: str
    port: int
    tls: bool

    def __str__(self) -> str:
        scheme = "stratum+ssl" if self.tls else "stratum+tcp"
        display_host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{scheme}://{display_host}:{self.port}"


def parse_endpoint(raw: str, default_port: int = _DEFAULT_PORT) -> PoolEndpoint:
    """Parse a pool endpoint URI into a PoolEndpoint dataclass.

    Supported formats:
        stratum+tcp://host:port     -> cleartext, port 3333 default
        stratum+ssl://host:port     -> TLS, port 3333 default
        stratum+tls://host:port     -> TLS, port 3333 default
        stratum://host:port         -> cleartext, port 3333 default
        tcp://host:port             -> cleartext, port 3333 default
        host:port                   -> bare host:port, default port 3333
        host                        -> bare host, default port 3333

    Raises ValueError for unknown schemes or malformed endpoints.
    """
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        raise ValueError("pool endpoint is empty")
    if not isinstance(default_port, int) or isinstance(default_port, bool):
        raise ValueError("default pool port must be an integer")
    if not 1 <= default_port <= 65535:
        raise ValueError(f"default pool port {default_port} outside [1, 65535]")

    normalized = text if "://" in text else f"stratum+tcp://{text}"
    try:
        parsed = urlsplit(normalized)
    except ValueError as exc:
        raise ValueError(f"malformed pool endpoint {raw!r}: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in _SCHEMES:
        raise ValueError(
            f"unsupported pool scheme {scheme!r}; use stratum+tcp:// or stratum+ssl://"
        )
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("pool endpoint must not contain user information")
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("pool endpoint must contain only a host and optional port")

    authority = parsed.netloc
    if authority.count(":") > 1 and not authority.startswith("["):
        raise ValueError("IPv6 pool hosts must be enclosed in brackets")
    if authority.startswith("["):
        closing = authority.find("]")
        suffix = authority[closing + 1 :] if closing >= 0 else ""
        if closing < 0 or (suffix and not suffix.startswith(":")):
            raise ValueError(f"malformed bracketed pool host {authority!r}")
    if authority.endswith(":"):
        raise ValueError("pool endpoint has an empty port")

    host = parsed.hostname
    if not host:
        raise ValueError(f"pool endpoint {raw!r} has no host")
    if any(character.isspace() for character in host):
        raise ValueError("pool endpoint host must not contain whitespace")

    try:
        port = parsed.port if parsed.port is not None else default_port
    except ValueError as exc:
        raise ValueError(f"invalid pool port in endpoint {raw!r}: {exc}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"pool port {port} outside [1, 65535]")

    return PoolEndpoint(host=host, port=port, tls=_SCHEMES[scheme])
