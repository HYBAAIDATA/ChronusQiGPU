"""Parse pool endpoint URIs into a (host, port, tls) triple.

Stratum pools advertise endpoints as URIs ("stratum+tcp://host:port"), but
asyncio.open_connection needs a bare hostname. Parsing here keeps the scheme
out of the socket layer and gives TLS a single place to be switched on.
"""

from __future__ import annotations

from dataclasses import dataclass

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
        return f"{scheme}://{self.host}:{self.port}"


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
    text = (raw or "").strip()
    if not text:
        raise ValueError("pool endpoint is empty")

    scheme, separator, rest = text.partition("://")
    if not separator:
        scheme, rest = "stratum+tcp", text
    scheme = scheme.lower()
    if scheme not in _SCHEMES:
        raise ValueError(
            f"unsupported pool scheme {scheme!r}; use stratum+tcp:// or stratum+ssl://"
        )

    # Discard any trailing path after host:port
    rest = rest.split("/", 1)[0]

    host, _, port_text = rest.rpartition(":")
    if not host:
        host, port_text = rest, ""  # no colon at all -> whole string is host
    if not host:
        raise ValueError(f"pool endpoint {raw!r} has no host")
    # Strip bracketed IPv6 e.g. [::1]
    if host.startswith("["):
        host = host.rstrip("]").lstrip("[")

    port = int(port_text) if port_text else default_port
    if not 1 <= port <= 65535:
        raise ValueError(f"pool port {port} outside [1, 65535]")

    return PoolEndpoint(host=host, port=port, tls=_SCHEMES[scheme])