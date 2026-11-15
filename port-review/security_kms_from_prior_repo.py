"""Explicit key-provider selection. HSM is unavailable until integrated."""
from __future__ import annotations
import os
import secrets
from pathlib import Path
from typing import Protocol

class KeyProvider(Protocol):
    name: str
    hsm_backed: bool
    def available(self) -> bool: ...
    def get_or_create(self, label: str) -> bytes: ...

def _label(label: str) -> str:
    if not label or not all(c.isalnum() or c in "-_" for c in label):
        raise ValueError("invalid key label")
    return label

class LocalMemoryKeyProvider:
    name = "local-memory"
    hsm_backed = False
    def __init__(self):
        self._keys: dict[str, bytes] = {}
    def available(self) -> bool:
        return True
    def get_or_create(self, label: str) -> bytes:
        label = _label(label)
        if label not in self._keys:
            self._keys[label] = secrets.token_bytes(32)
        return self._keys[label]

class FileKeyProvider:
    name = "file"
    hsm_backed = False
    def __init__(self, root: str | Path):
        self._root = Path(root)
    def available(self) -> bool:
        return self._root.is_dir() and os.access(self._root, os.W_OK)
    def get_or_create(self, label: str) -> bytes:
        label = _label(label)
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._root / (label + ".key")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            if path.is_symlink():
                raise RuntimeError("symlink key refused")
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                data = os.read(fd, 33)
            finally:
                os.close(fd)
            if len(data) != 32:
                raise RuntimeError("invalid key length")
            return data
        else:
            material = secrets.token_bytes(32)
            with os.fdopen(fd, "wb") as stream:
                stream.write(material)
                stream.flush()
                os.fsync(stream.fileno())
            return material

class Pkcs11KeyProvider:
    name = "pkcs11"
    hsm_backed = True
    def available(self) -> bool:
        return False
    def get_or_create(self, label: str) -> bytes:
        raise NotImplementedError("PKCS#11 not implemented")

def select(name: str, root: str | Path = "keys") -> KeyProvider:
    if name == "local-memory":
        return LocalMemoryKeyProvider()
    if name == "file":
        return FileKeyProvider(root)
    if name == "pkcs11":
        raise RuntimeError("PKCS#11 not implemented")
    raise ValueError("unknown key provider")
