"""Read-only Bitcoin Core RPC observations for the external-block gate.

The observer exposes validated historical headers and optional raw serialized
blocks for PYTHIA's corpus memory. Historical access is read-only and uses the
same proof checks as the live tip: the 80-byte header is rehashed locally, the
compact target is validated, and ``getblockhash(height)`` must still name the
same active-chain block. Nothing in this module changes mining consensus or
submission state.

Raw block custody is anchored to that independently validated header. This
module does not reimplement Bitcoin transaction parsing/merkle construction;
it therefore records that distinction rather than claiming an independent
transaction-body consensus verifier.
"""

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
    def from_environment(cls) -> "BitcoinChainObserver | None":
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
        """The network the configured node is on: main/test/testnet4/signet/regtest."""
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

    def height(self) -> int:
        """Return the active-chain height reported by Bitcoin Core."""
        height = self._call("getblockcount", [])
        if type(height) is not int or height < 0:
            raise ValueError("Bitcoin RPC returned an invalid block height")
        return height

    @staticmethod
    def _validate_header(header: bytes, block_hash: str) -> tuple[bytes, int]:
        if len(header) != 80:
            raise ValueError("chain observation has an invalid header length")
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        if digest[::-1].hex() != block_hash:
            raise ValueError("chain observation header hash does not match block hash")
        bits = int.from_bytes(header[72:76], "little")
        exponent, mantissa = bits >> 24, bits & 0x7FFFFF
        target = (
            mantissa << (8 * (exponent - 3)) if exponent > 3 else mantissa >> (8 * (3 - exponent))
        )
        if bits & 0x800000 or not 0 < target < 2**256:
            raise ValueError("chain observation has an invalid target")
        if int.from_bytes(digest, "little") > target:
            raise ValueError("chain observation header does not satisfy its target")
        return digest, target

    def header_at(self, height: int) -> dict:
        """Return one validated active-chain block header by height.

        This is the historical-data seam consumed by PYTHIA's header corpus.
        It never trusts explorer metadata in place of the canonical 80 bytes:
        the header is fetched in raw form and re-verified locally.
        """
        if type(height) is not int or height < 0:
            raise ValueError("height must be a non-negative integer")
        block_hash = self._call("getblockhash", [height])
        if not isinstance(block_hash, str) or len(block_hash) != 64:
            raise RuntimeError("Bitcoin RPC returned an invalid block hash")
        raw = self._call("getblockheader", [block_hash, False])
        info = self._call("getblockheader", [block_hash, True])
        if not isinstance(raw, str) or not isinstance(info, dict):
            raise RuntimeError("Bitcoin RPC returned an invalid block header response")
        header = bytes.fromhex(raw)
        _digest, target = self._validate_header(header, block_hash)
        observed_height = info.get("height")
        if observed_height != height or info.get("confirmations", 0) < 1:
            raise ValueError("historical header is not confirmed at the requested height")
        if self._call("getblockhash", [height]) != block_hash:
            raise ValueError("chain reorganized during historical header observation")
        return {
            "height": height,
            "block_hash": block_hash,
            "header": header,
            "header_hex": raw,
            "version": int.from_bytes(header[0:4], "little"),
            "previousblockhash": header[4:36][::-1].hex(),
            "merkleroot": header[36:68][::-1].hex(),
            "time": int.from_bytes(header[68:72], "little"),
            "bits": int.from_bytes(header[72:76], "little"),
            "nonce": int.from_bytes(header[76:80], "little"),
            "target": target,
            "chainwork": info.get("chainwork"),
            "confirmations": info.get("confirmations"),
        }

    def raw_block_at(self, height: int) -> dict:
        """Return the canonical raw serialized active-chain block at ``height``.

        The first 80 bytes must be byte-identical to ``header_at(height)`` and
        therefore already satisfy the locally checked block-hash/target
        contract. The active-chain hash is re-read after the block payload is
        fetched so a reorg cannot be silently written into the historical
        corpus under the old height.
        """
        observed = self.header_at(height)
        block_hash = observed["block_hash"]
        raw_hex = self._call("getblock", [block_hash, 0])
        if not isinstance(raw_hex, str):
            raise RuntimeError("Bitcoin RPC returned an invalid raw block response")
        try:
            raw_block = bytes.fromhex(raw_hex)
        except ValueError as exc:
            raise RuntimeError("Bitcoin RPC returned non-hex raw block data") from exc
        if len(raw_block) <= 80:
            raise ValueError("raw Bitcoin block is too short")
        if raw_block[:80] != observed["header"]:
            raise ValueError("raw block header does not match independently validated header")
        self._validate_header(raw_block[:80], block_hash)
        if self._call("getblockhash", [height]) != block_hash:
            raise ValueError("chain reorganized during raw block observation")
        return {
            **observed,
            "raw_block": raw_block,
            "raw_block_sha256": hashlib.sha256(raw_block).hexdigest(),
            "raw_block_bytes": len(raw_block),
            "body_verification": "Bitcoin Core canonical serialization anchored to locally verified header; transaction merkle body not independently reimplemented here",
        }

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
        height = self.height()
        observed = self.header_at(height)
        return {"block_hash": observed["block_hash"], "height": observed["height"]}
