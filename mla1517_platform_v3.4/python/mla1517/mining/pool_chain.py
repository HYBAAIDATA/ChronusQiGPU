"""Chain evidence from the pool itself, for pool-only mining.

When PYTHIA mines exclusively through pools (ViaBTC, NiceHash, Braiins,
CKPool), no local bitcoind is required: the connected pool's current job
states the tip it wants built on (its previous-block hash) and, through the
BIP34 height in the coinbase, that tip's height. This observer exposes that
evidence through the same ``tip()`` / ``confirmed_height()`` contract as
``BitcoinChainObserver`` so the MiningSession's rules still hold, including
the low-profile rule that the miner never mines directly on its own block.

It is weaker evidence than an independent node (the pool is trusted for the
chain view) and says so: ``source = "pool_stratum"``. It fails closed: no job
or no parseable BIP34 height means no tip, and mining pauses.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable

from .stratum_adapter import stratum_prevhash


def _varint(raw: bytes, pos: int) -> tuple[int, int]:
    first = raw[pos]
    if first < 0xFD:
        return first, pos + 1
    width = {0xFD: 2, 0xFE: 4, 0xFF: 8}[first]
    return int.from_bytes(raw[pos + 1 : pos + 1 + width], "little"), pos + 1 + width


def bip34_height(coinb1_hex: str) -> int | None:
    """Block height pushed at the start of the coinbase scriptSig (BIP34).

    ``coinb1`` is the legacy serialization up to the extranonce, so it always
    contains version, the single null input, the script length and the height
    push. Returns None when the prefix does not have that shape.
    """
    try:
        raw = bytes.fromhex(coinb1_hex)
        pos = 4
        if raw[pos] == 0 and raw[pos + 1] == 1:  # tolerate a segwit marker/flag
            pos += 2
        inputs, pos = _varint(raw, pos)
        if inputs != 1 or raw[pos : pos + 32] != bytes(32):
            return None
        pos += 36
        _script_len, pos = _varint(raw, pos)
        push = raw[pos]
        if not 1 <= push <= 8 or pos + 1 + push > len(raw):
            return None
        return int.from_bytes(raw[pos + 1 : pos + 1 + push], "little")
    except (ValueError, IndexError, KeyError):
        return None


class PoolChainObserver:
    source = "pool_stratum"

    def __init__(self, client_provider: Callable[[], Any], *, memory: int = 256) -> None:
        self._client = client_provider
        self._heights: OrderedDict[str, int] = OrderedDict()
        self._memory = memory

    def tip(self) -> dict[str, Any]:
        client = self._client()
        state = getattr(client, "runtime_state", None) if client is not None else None
        generation = getattr(state, "current_job", None) if state is not None else None
        if generation is None:
            raise RuntimeError("no pool job: chain tip unknown")
        job_height = bip34_height(generation.coinb1)
        if job_height is None or job_height < 1:
            raise RuntimeError("pool job carries no BIP34 height: chain tip unknown")
        block_hash = stratum_prevhash(generation.prevhash)[::-1].hex()
        height = job_height - 1
        self._heights[block_hash] = height
        self._heights.move_to_end(block_hash)
        while len(self._heights) > self._memory:
            self._heights.popitem(last=False)
        return {"block_hash": block_hash, "height": height}

    def confirmed_height(self, block_hash: str) -> int | None:
        """Height of a block once any pool job has been built on it."""
        return self._heights.get(block_hash)
