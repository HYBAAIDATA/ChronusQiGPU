"""Read-only Bitcoin Core RPC observations for the external-block gate."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class BitcoinChainObserver:
    def __init__(self, url: str, *, credentials: str | None = None) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Bitcoin RPC URL must be http(s)")
        if parsed.username or parsed.password:
            raise ValueError("supply RPC credentials separately from its URL")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("remote Bitcoin RPC requires HTTPS")
        self.url = url
        self.credentials = credentials

    @classmethod
    def from_environment(cls) -> BitcoinChainObserver | None:
        url = os.environ.get("PYTHIA_BITCOIN_RPC_URL")
        if not url:
            return None
        credentials = os.environ.get("PYTHIA_BITCOIN_RPC_AUTH")
        cookie = os.environ.get("PYTHIA_BITCOIN_RPC_COOKIE")
        if cookie:
            from pathlib import Path

            credentials = Path(cookie).read_text().strip()
        return cls(url, credentials=credentials)

    def _call(self, method: str, params: list) -> object:
        headers = {"Content-Type": "application/json"}
        if self.credentials:
            token = base64.b64encode(self.credentials.encode()).decode()
            headers["Authorization"] = "Basic " + token
        request = Request(
            self.url,
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
            headers=headers,
        )
        with urlopen(request, timeout=10) as response:
            data = json.load(response)
        if data.get("error"):
            raise RuntimeError("Bitcoin RPC rejected chain observation")
        return data["result"]

    def chain(self) -> str:
        """The network the configured node is on: main/test/testnet4/signet/regtest.

        ``getblockchaininfo`` is the only honest source — a node on the wrong
        network reports a chain name, not a guess derived from the URL.
        """
        info = self._call("getblockchaininfo", [])
        if not isinstance(info, dict):
            raise RuntimeError("Bitcoin RPC returned no blockchain info")
        chain = info.get("chain")
        if not isinstance(chain, str) or not chain:
            raise RuntimeError("Bitcoin RPC returned no chain name")
        return chain

    def assert_chain(self, expected: str) -> None:
        """Refuse to run against the wrong network; fails closed."""
        observed = self.chain()
        if observed != expected:
            raise RuntimeError(
                f"Bitcoin RPC chain is {observed!r}; PYTHIA_BITCOIN_NETWORK={expected!r}"
            )

    def confirmed_height(self, block_hash: str) -> int | None:
        try:
            info = self._call("getblockheader", [block_hash, True])
        except RuntimeError:
            return None
        if info["confirmations"] < 1:
            return None
        height = info["height"]
        return height if self._call("getblockhash", [height]) == block_hash else None

    def tip(self) -> dict:
        block_hash = self._call("getbestblockhash", [])
        info = self._call("getblockheader", [block_hash, True])
        header = bytes.fromhex(self._call("getblockheader", [block_hash, False]))
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        if len(header) != 80 or digest[::-1].hex() != block_hash:
            raise ValueError("chain observation has an invalid header")
        bits = int.from_bytes(header[72:76], "little")
        exponent, mantissa = bits >> 24, bits & 0x7FFFFF
        target = (
            mantissa << (8 * (exponent - 3)) if exponent > 3 else mantissa >> (8 * (3 - exponent))
        )
        if bits & 0x800000 or not 0 < target < 2**256:
            raise ValueError("chain observation has an invalid target")
        if int.from_bytes(digest, "little") > target or info["confirmations"] < 1:
            raise ValueError("chain observation has no confirmed proof")
        height = info["height"]
        if type(height) is not int or height < 0:
            raise ValueError("chain observation has an invalid height")
        if self._call("getblockhash", [height]) != block_hash:
            raise ValueError("chain reorganized during observation")
        return {"block_hash": block_hash, "height": height}
