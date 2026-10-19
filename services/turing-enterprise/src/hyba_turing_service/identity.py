"""OIDC access-token verification; issuer/audience/JWKS are trusted configuration."""

from dataclasses import dataclass
import urllib.parse

from .control import Denied


@dataclass(frozen=True)
class Identity:
    subject: str
    issuer: str


class OIDCVerifier:
    def __init__(self, issuer, audience, jwks_url, *, key_client=None):
        import jwt

        for url in (issuer, jwks_url):
            p = urllib.parse.urlsplit(url)
            if p.scheme != "https" or not p.hostname or p.username or p.password or p.fragment:
                raise ValueError("trusted HTTPS OIDC endpoints required")
        if not audience:
            raise ValueError("OIDC audience required")
        self.issuer = issuer
        self.audience = audience
        self.keys = key_client or jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=60)

    def claims(self, token):
        import jwt

        if not isinstance(token, str) or len(token) > 32768:
            raise Denied("invalid identity token")
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
                leeway=0,
            )
            if not isinstance(claims["sub"], str) or not claims["sub"] or len(claims["sub"]) > 256:
                raise ValueError("invalid subject")
            return claims
        except Exception:
            raise Denied("identity verification denied") from None

    def verify(self, token):
        claims = self.claims(token)
        return Identity(claims["sub"], claims["iss"])
