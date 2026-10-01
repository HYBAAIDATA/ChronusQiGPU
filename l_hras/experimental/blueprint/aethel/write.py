# l_hras/aethel/write.py

from l_hras.experimental.blueprint.aethel.store import AethelStore
from l_hras.experimental.blueprint.fold.certificate import Certificate

def write_certificate(store: AethelStore, cert: Certificate) -> str:
    """Write a certificate to Aethel."""
    return store.write(cert)
