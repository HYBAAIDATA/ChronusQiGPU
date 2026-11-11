# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Real Bitcoin block headers used as known answers.

Public chain data. The genesis header is the one ``tests/test_mining.py`` and
``tests/test_stratum_pool.py`` already use; the regtest genesis header is
``tests/vectors/regtest_block0.json``. Each vector is self-checking: SHA-256d
of the header must equal the published block hash and meet the header's nBits
target, so a mistyped field cannot pass.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnownHeader:
    name: str
    network: str
    height: int
    header_hex: str
    block_hash: str
    nonce: int

    @property
    def header(self) -> bytes:
        return bytes.fromhex(self.header_hex)

    @property
    def prefix(self) -> bytes:
        return self.header[:76]

    @property
    def nbits(self) -> int:
        return int.from_bytes(self.header[72:76], "little")


REAL_HEADERS = (
    KnownHeader(
        name="mainnet-0-genesis",
        network="mainnet",
        height=0,
        header_hex=(
            "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b2"
            "7ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c"
        ),
        block_hash="000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
        nonce=2083236893,
    ),
    KnownHeader(
        name="mainnet-1",
        network="mainnet",
        height=1,
        header_hex=(
            "010000006fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000982051fd1e4ba744"
            "bbbe680e1fee14677ba1a3c3540bf7b1cdb606e857233e0e61bc6649ffff001d01e36299"
        ),
        block_hash="00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048",
        nonce=2573394689,
    ),
    KnownHeader(
        name="mainnet-2",
        network="mainnet",
        height=2,
        header_hex=(
            "010000004860eb18bf1b1620e37e9490fc8a427514416fd75159ab86688e9a8300000000d5fdcc541e25de1c"
            "7a5addedf24858b8bb665c9f36ef744ee42c316022c90f9bb0bc6649ffff001d08d2bd61"
        ),
        block_hash="000000006a625f06636b8bb6ac7b960a8d03705d1ace08b1a19da3fdcc99ddbd",
        nonce=1639830024,
    ),
    KnownHeader(
        name="mainnet-100000",
        network="mainnet",
        height=100000,
        header_hex=(
            "0100000050120119172a610421a6c3011dd330d9df07b63616c2cc1f1cd00200000000006657a9252aacd5c0"
            "b2940996ecff952228c3067cc38d4885efb5a4ac4247e9f337221b4d4c86041b0f2b5710"
        ),
        block_hash="000000000003ba27aa200b1cecaad478d2b00432346c3f1f3986da1afd33e506",
        nonce=274148111,
    ),
    KnownHeader(
        name="mainnet-125552",
        network="mainnet",
        height=125552,
        header_hex=(
            "0100000081cd02ab7e569e8bcd9317e2fe99f2de44d49ab2b8851ba4a308000000000000e320b6c2fffc8d75"
            "0423db8b1eb942ae710e951ed797f7affc8892b0f1fc122bc7f5d74df2b9441a42a14695"
        ),
        block_hash="00000000000000001e8d6829a8a21adc5d38d0a473b144b6765798e61f98bd1d",
        nonce=2504433986,
    ),
    KnownHeader(
        name="regtest-0-genesis",
        network="regtest",
        height=0,
        header_hex=(
            "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b2"
            "7ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4adae5494dffff7f2002000000"
        ),
        block_hash="0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206",
        nonce=2,
    ),
)

GENESIS = REAL_HEADERS[0]
