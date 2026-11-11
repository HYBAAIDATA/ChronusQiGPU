# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Logging that cannot carry a pool login.

HYBA Mine never passes a username or password to a log call. As a second line
of defence every handler it installs formats through ``RedactingFormatter``,
which removes any registered secret from the final text (message, arguments
and tracebacks). The same registry lets the ledger refuse a record that would
contain a secret.
"""

from __future__ import annotations

import hashlib
import logging
import logging.handlers
import re
import sys
import threading
from pathlib import Path
from typing import Iterable, Optional

REDACTED = "[redacted]"
_MIN_SECRET_LENGTH = 6
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_WORKER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _distinctive(value: str) -> bool:
    """Long enough, and not hex-like, so it cannot collide with hashes or nonces."""
    return len(value) >= _MIN_SECRET_LENGTH and any(ch not in _HEX_DIGITS for ch in value)


class SecretRegistry:
    """Process-wide set of strings that must never be written anywhere."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._secrets: set[str] = set()

    def register(self, *values: Optional[str]) -> None:
        """Register login strings; short or hex-like placeholders are ignored."""
        with self._lock:
            for value in values:
                if isinstance(value, str) and _distinctive(value):
                    self._secrets.add(value)

    def clear(self) -> None:
        with self._lock:
            self._secrets.clear()

    def _ordered(self) -> list[str]:
        with self._lock:
            return sorted(self._secrets, key=len, reverse=True)

    def redact(self, text: str) -> str:
        for secret in self._ordered():
            if secret in text:
                text = text.replace(secret, REDACTED)
        return text

    def contains(self, text: str) -> bool:
        return any(secret in text for secret in self._ordered())


SECRETS = SecretRegistry()


def register_login(username: str, password: str) -> None:
    """Register a pool login for redaction."""
    SECRETS.register(username, password)


def login_fingerprint(username: str) -> str:
    """Stable, non-reversible tag that lets the console tell logins apart."""
    digest = hashlib.sha256(b"hyba-mine/login/v1|" + username.encode("utf-8")).hexdigest()
    return digest[:12]


def worker_label(username: str) -> Optional[str]:
    """The worker suffix of ``account.worker`` (shown on the console), or None."""
    if "." not in username:
        return None
    worker = username.rsplit(".", 1)[1]
    return worker if _WORKER_PATTERN.match(worker) else None


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return SECRETS.redact(super().format(record))

    def formatException(self, ei) -> str:  # noqa: N802 - logging API name
        return SECRETS.redact(super().formatException(ei))


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    stream=None,
) -> list[logging.Handler]:
    """Replace the root handlers with redacting handlers; return them."""
    formatter = RedactingFormatter(LOG_FORMAT)
    handlers: list[logging.Handler] = []
    stream_handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    stream_handler.setFormatter(formatter)
    handlers.append(stream_handler)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    logging.basicConfig(level=level, handlers=handlers, force=True)

    def _excepthook(exc_type, exc, tb):
        logging.getLogger("hyba_mine").critical(
            "unhandled exception", exc_info=(exc_type, exc, tb)
        )

    sys.excepthook = _excepthook
    return handlers


def redact_all(values: Iterable[str]) -> list[str]:
    return [SECRETS.redact(value) for value in values]
