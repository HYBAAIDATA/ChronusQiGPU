# l_hras/aethel/read.py

from l_hras.experimental.blueprint.aethel.store import AethelStore

def read_certificate(store: AethelStore, key: str):
    """Read a certificate from Aethel."""
    return store.read(key)

def verify_replay(store: AethelStore, key: str) -> bool:
    """Verify the certificate replays."""
    return store.verify_replay(key)
