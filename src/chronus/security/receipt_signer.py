"""Shared process-local signer for API receipts. Keys do not survive restart."""

from chronus.security.signers import Ed25519Signer

# Deliberately process-local. This is not durable key custody or a KMS integration.
receipt_signer = Ed25519Signer()
