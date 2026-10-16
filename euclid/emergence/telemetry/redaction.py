"""Schema-based and pattern-based redaction engine for agent telemetry."""

from __future__ import annotations
import re
from typing import Any


class TelemetryRedactor:
    """Sanitizes telemetry structures before emission to prevent leakage of secrets, keys, or PII."""

    SENSITIVE_KEY_NAMES = {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "auth",
        "authorization",
        "api_key",
        "apikey",
        "private_key",
        "credential",
        "credentials",
        "ssn",
        "credit_card",
    }

    SECRET_REGEX_PATTERNS = [
        # Bearer tokens
        (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{12,}", re.IGNORECASE), "[REDACTED_BEARER_TOKEN]"),
        # API Keys (e.g., sk-..., key-...)
        (re.compile(r"(sk|key|pk)_[a-zA-Z0-9]{16,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
        # Private key blocks
        (re.compile(r"-----BEGIN [A-Z\s]+PRIVATE KEY-----[^-]+-----END [A-Z\s]+PRIVATE KEY-----", re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
        # Email addresses
        (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE), "[REDACTED_EMAIL]"),
        # IPv4 addresses
        (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[REDACTED_IP]"),
        # Generic key-value assignment in query/config strings (e.g. password=xyz)
        (re.compile(r"(password|secret|token|api_key)=([^\s&;]+)", re.IGNORECASE), r"\1=[REDACTED]"),
    ]

    def __init__(self) -> None:
        self.redactions_count: int = 0

    def redact_text(self, text: str) -> str:
        """Apply regex-based pattern redaction to a text string."""
        if not isinstance(text, str):
            return text
        sanitized = text
        for pattern, replacement in self.SECRET_REGEX_PATTERNS:
            new_val, count = pattern.subn(replacement, sanitized)
            if count > 0:
                self.redactions_count += count
                sanitized = new_val
        return sanitized

    def sanitize(self, data: Any) -> Any:
        """Deep recursive sanitization of objects, dictionaries, lists, and strings."""
        if isinstance(data, dict):
            sanitized_dict = {}
            for k, v in data.items():
                k_str = str(k).lower()
                if any(sensitive in k_str for sensitive in self.SENSITIVE_KEY_NAMES):
                    self.redactions_count += 1
                    sanitized_dict[k] = "[REDACTED_SENSITIVE_FIELD]"
                else:
                    sanitized_dict[k] = self.sanitize(v)
            return sanitized_dict
        elif isinstance(data, (list, tuple)):
            sanitized_seq = [self.sanitize(item) for item in data]
            return tuple(sanitized_seq) if isinstance(data, tuple) else sanitized_seq
        elif isinstance(data, str):
            return self.redact_text(data)
        else:
            return data
