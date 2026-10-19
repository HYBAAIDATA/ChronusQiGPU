"""Braiins Pool Stratum V2 session on the existing Mining Protocol codec.

Official endpoint (Braiins Academy SV2 manual):
  stratum2+tcp://stratum.braiins.com:3333/9awtMD5KQgvRUh2yFbjVeT7b6hjipWcAsQHd6wEhgtDT9soosna

The path is the pool authority public key used to verify SIGNATURE_NOISE_MESSAGE.
Live SV2 traffic cannot start until a Noise_NX_Secp256k1+EllSwift_ChaChaPoly_SHA256
channel is supplied. This module never writes SetupConnection on plaintext TCP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from mining.stratum_v2 import (
    SetupConnection,
    StratumV2Client,
    Sv2TransportError,
)

BRAIINS_SV2_HOST = "stratum.braiins.com"
BRAIINS_SV2_PORT = 3333
BRAIINS_AUTHORITY_KEY = "9awtMD5KQgvRUh2yFbjVeT7b6hjipWcAsQHd6wEhgtDT9soosna"
BRAIINS_SV2_URL = (
    f"stratum2+tcp://{BRAIINS_SV2_HOST}:{BRAIINS_SV2_PORT}/{BRAIINS_AUTHORITY_KEY}"
)
BRAIINS_SV1_BACKUP = "stratum+tcp://stratum.braiins.com:3333"
DEFAULT_IDENTITY = "pythagoras.PYTHIA"


def normalize_identity(user: str) -> str:
    user = (user or "").strip()
    if not user:
        raise Sv2TransportError("Braiins user_identity is required")
    if user.upper() == user and "." in user:
        account, worker = user.split(".", 1)
        return f"{account.lower()}.{worker}"
    if user.upper() == user:
        return user.lower()
    return user


@dataclass(frozen=True)
class BraiinsSv2Config:
    host: str = BRAIINS_SV2_HOST
    port: int = BRAIINS_SV2_PORT
    authority_key: str = BRAIINS_AUTHORITY_KEY
    user_identity: str = DEFAULT_IDENTITY
    vendor: str = "PHIDATA2"
    hardware_version: str = "PYTHIA"
    firmware: str = "PYTHIA-SV2"

    @classmethod
    def from_url(cls, url: str, user_identity: str = DEFAULT_IDENTITY) -> "BraiinsSv2Config":
        parsed = urlparse(url)
        if parsed.scheme not in {"stratum2+tcp", "stratum2+ssl"}:
            raise Sv2TransportError(f"not an SV2 URL: {parsed.scheme}")
        key = parsed.path.lstrip("/")
        if not key:
            raise Sv2TransportError("SV2 URL missing authority public key path")
        return cls(
            host=parsed.hostname or BRAIINS_SV2_HOST,
            port=parsed.port or BRAIINS_SV2_PORT,
            authority_key=key,
            user_identity=normalize_identity(user_identity),
        )

    def setup(self) -> SetupConnection:
        return SetupConnection(
            protocol=0,
            min_version=2,
            max_version=2,
            flags=1,
            endpoint_host=self.host,
            endpoint_port=self.port,
            vendor=self.vendor,
            hardware_version=self.hardware_version,
            firmware=self.firmware,
            device_id=self.user_identity,
        )


def client_for_channel(channel, config: Optional[BraiinsSv2Config] = None) -> StratumV2Client:
    cfg = config or BraiinsSv2Config()
    if not getattr(channel, "secure", False):
        raise Sv2TransportError("Braiins SV2 refuses plaintext; Noise NX channel required")
    return StratumV2Client(channel, cfg.setup())


async def open_standard(channel, config: Optional[BraiinsSv2Config] = None, hashrate: float = 1e9):
    cfg = config or BraiinsSv2Config()
    client = client_for_channel(channel, cfg)
    await client.open()
    channel_id = await client.open_standard_channel(
        1, hashrate, (1 << 256) - 1, cfg.user_identity
    )
    return client, channel_id
