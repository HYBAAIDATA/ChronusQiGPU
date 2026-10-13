"""Reference cryptographic predicates; no fabricated preimages."""
import hashlib
class AdvancedMathematicalOracles:
    @staticmethod
    def sha256(data): return hashlib.sha256(data).digest()
    @staticmethod
    def sha256d(data): return hashlib.sha256(hashlib.sha256(data).digest()).digest()
    @staticmethod
    def nonce_digest(header_prefix, nonce):
        if not isinstance(header_prefix, bytes) or len(header_prefix) != 76: raise ValueError("76-byte Bitcoin header prefix required")
        if type(nonce) is not int or not 0 <= nonce < 2**32: raise ValueError("uint32 nonce required")
        return AdvancedMathematicalOracles.sha256d(header_prefix + nonce.to_bytes(4, "little"))
    @staticmethod
    def accepts(digest, target):
        if type(target) is not int or not 0 <= target < 2**256: raise ValueError("uint256 target required")
        if not isinstance(digest, bytes) or len(digest) != 32: raise ValueError("32-byte digest required")
        return int.from_bytes(digest, "little") <= target
