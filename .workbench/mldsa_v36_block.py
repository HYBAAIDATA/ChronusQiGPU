class MLDSASigner:
    """
    FIPS 204 ML-DSA-65 module-lattice signatures through pyca/cryptography (OpenSSL).

    ``sign_mldsa`` accepts an ML-DSA-65 private key or a 32-byte FIPS 204
    key-generation seed; other key material is hashed with SHA-256 under a
    domain tag to form that seed. ``verify_mldsa`` accepts an ML-DSA-65 public
    key or its 1,952-byte raw encoding and returns True only when the signature
    verifies: there is no fallback acceptance. Receipt keys are generated per
    tenant inside this process (``tenant_private_key``); only public keys leave
    the signer. Cross-process custody (KMS or HSM) is a separate concern.
    """
    PREFIX = "mldsa65_"
    _tenant_keys: dict = {}

    @staticmethod
    def _mldsa():
        from cryptography.hazmat.primitives.asymmetric import mldsa
        return mldsa

    @classmethod
    def _private_key(cls, key: Any) -> Any:
        mldsa = cls._mldsa()
        if isinstance(key, mldsa.MLDSA65PrivateKey):
            return key
        if isinstance(key, (bytes, bytearray)) and len(key) == 32:
            return mldsa.MLDSA65PrivateKey.from_seed_bytes(bytes(key))
        material = bytes(key) if isinstance(key, (bytes, bytearray)) else str(key).encode("utf-8")
        seed = hashlib.sha256(b"chronus/mldsa65/seed/v1|" + material).digest()
        return mldsa.MLDSA65PrivateKey.from_seed_bytes(seed)

    @classmethod
    def tenant_private_key(cls, tenant_hash: str) -> Any:
        key = cls._tenant_keys.get(tenant_hash)
        if key is None:
            key = cls._mldsa().MLDSA65PrivateKey.generate()
            cls._tenant_keys[tenant_hash] = key
        return key

    @classmethod
    def public_key_bytes(cls, key: Any) -> bytes:
        return cls._private_key(key).public_key().public_bytes_raw()

    @classmethod
    def tenant_public_key(cls, tenant_hash: str) -> bytes:
        return cls.public_key_bytes(cls.tenant_private_key(tenant_hash))

    @staticmethod
    def _message_bytes(msg: Any) -> bytes:
        return msg.encode("utf-8") if isinstance(msg, str) else bytes(msg)

    @classmethod
    def sign_mldsa(cls, key: Any, msg: str) -> str:
        return cls.PREFIX + cls._private_key(key).sign(cls._message_bytes(msg)).hex()

    @classmethod
    def verify_mldsa(cls, pub: Any, msg: str, sig: str) -> bool:
        from cryptography.exceptions import InvalidSignature
        if not isinstance(sig, str) or not sig.startswith(cls.PREFIX):
            return False
        mldsa = cls._mldsa()
        try:
            public = pub if isinstance(pub, mldsa.MLDSA65PublicKey) else mldsa.MLDSA65PublicKey.from_public_bytes(bytes(pub))
            public.verify(bytes.fromhex(sig[len(cls.PREFIX):]), cls._message_bytes(msg))
        except (InvalidSignature, TypeError, ValueError):
            return False
        return True
