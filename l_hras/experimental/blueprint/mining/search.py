# l_hras/mining/search.py

import hashlib
from l_hras.experimental.blueprint.mining.candidate import Candidate, sha256d

def search_nonce(candidate: Candidate, target: bytes, start: int = 0, count: int = 2**32) -> tuple:
    """Search for a nonce that meets the target."""
    header = bytearray(candidate.header)
    for nonce in range(start, min(start + count, 2**32)):
        header[76:80] = nonce.to_bytes(4, 'little')
        h = sha256d(bytes(header))
        if h[::-1] < target:
            return (nonce, h)
    return (None, None)
