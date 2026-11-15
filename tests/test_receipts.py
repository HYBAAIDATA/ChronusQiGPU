import pytest
from chronus.security.signers import Ed25519Signer
from chronus.security.receipts import Receipt, ReceiptLog
def make_receipt(i, prev, key):
    return Receipt("w", "t", "0" * 64, "n", i, "2026-01-01T00:00:00Z", key.key_id, prev_digest=prev)
def test_chain_and_tamper():
    key = Ed25519Signer()
    log = ReceiptLog()
    for i in range(3):
        log.append(make_receipt(i, log.head_digest, key), key)
    assert log.verify_chain(key.public_key)[0]
    assert not log.verify(log._entries[0], key.public_key, {"result_digest": "f" * 64})
    with pytest.raises(ValueError):
        log.append(make_receipt(5, log.head_digest, key), key)
