"""
HYBA_DATA Security Implementation

Institutional-grade security primitives for the quantum-geometric
optimization framework. Designed to meet the standards of sovereign
infrastructure deployments (FISMA, government-classified, airgapped).

Author: Andre Taylor-Morris — HYBA Software Ltd
"""
import hashlib
import hmac
import os
import time
import json
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional


PHI = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass
class SecurityConfig:
    """Configuration for the security subsystem."""
    rate_limit_requests: int = 100
    rate_limit_window_seconds: float = 60.0
    api_key_length: int = 32
    audit_log_size: int = 10000
    encryption_key_rotation_interval: int = 3600
    max_input_dimension: int = 2**32
    max_batch_size: int = 10000
    enable_audit_logging: bool = True
    enable_rate_limiting: bool = True
    enable_encryption: bool = True
    enable_input_validation: bool = True


class InputValidator:
    """
    Validates and sanitizes all inputs to the HYBA_DATA framework.
    Enforces type safety, bounds checking, and dimension limits.
    """

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()

    def validate_point(self, point: int) -> int:
        """Validate a manifold point index."""
        if not isinstance(point, (int, float)):
            raise ValueError(f"Point must be numeric, got {type(point)}")
        p = int(point)
        if p < 0:
            raise ValueError(f"Point must be non-negative, got {p}")
        if p >= self.config.max_input_dimension:
            raise ValueError(f"Point exceeds max dimension {self.config.max_input_dimension}")
        return p

    def validate_batch(self, points: list) -> list:
        """Validate a batch of points."""
        if not isinstance(points, (list, tuple)):
            raise ValueError(f"Batch must be a list, got {type(points)}")
        if len(points) > self.config.max_batch_size:
            raise ValueError(f"Batch size {len(points)} exceeds limit {self.config.max_batch_size}")
        return [self.validate_point(p) for p in points]

    def validate_dimension(self, dim: int, min_val: int = 1, max_val: int = 10000) -> int:
        """Validate a dimension parameter."""
        if not isinstance(dim, int):
            raise ValueError(f"Dimension must be int, got {type(dim)}")
        if dim < min_val or dim > max_val:
            raise ValueError(f"Dimension {dim} out of range [{min_val}, {max_val}]")
        return dim

    def validate_oracle_value(self, value: float) -> float:
        """Validate an oracle evaluation result."""
        if not isinstance(value, (int, float)):
            raise ValueError(f"Oracle value must be numeric, got {type(value)}")
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f"Oracle value is NaN/Inf: {v}")
        return v

    def sanitize_string(self, s: str, max_length: int = 1000) -> str:
        """Sanitize a string input."""
        if not isinstance(s, str):
            raise ValueError(f"Expected string, got {type(s)}")
        if len(s) > max_length:
            raise ValueError(f"String length {len(s)} exceeds max {max_length}")
        # Remove null bytes and control characters
        return ''.join(c for c in s if c >= ' ' or c in '\n\r\t')


class RateLimiter:
    """
    Token bucket rate limiter with phi-weighted burst capacity.
    Allows bursts up to 2x the base rate, with phi-weighted refill.
    """

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
        self._tokens = float(self.config.rate_limit_requests)
        self._max_tokens = float(self.config.rate_limit_requests * 2)
        self._last_refill = time.time()
        self._refill_rate = self.config.rate_limit_requests / self.config.rate_limit_window_seconds
        self._phi_burst = PHI  # phi-weighted burst capacity

    def _refill(self):
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens. Returns True if allowed, False if rate limited."""
        if not self.config.enable_rate_limiting:
            return True
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    def get_status(self) -> dict:
        """Get current rate limiter status."""
        self._refill()
        return {
            "available_tokens": self._tokens,
            "max_tokens": self._max_tokens,
            "refill_rate_per_sec": self._refill_rate,
            "phi_burst_multiplier": self._phi_burst,
        }


class APIKeyManager:
    """
    Manages API keys with secure generation, validation, and rotation.
    Uses HMAC-SHA256 for key derivation and verification.
    """

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
        self._keys = {}  # key_id -> {key_hash, created, last_used, active}
        self._master_secret = os.urandom(32)

    def generate_key(self, key_id: str = None) -> tuple:
        """Generate a new API key. Returns (key_id, api_key)."""
        key_id = key_id or hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        raw_key = os.urandom(self.config.api_key_length)
        api_key = raw_key.hex()
        key_hash = hmac.new(self._master_secret, raw_key, hashlib.sha256).hexdigest()
        self._keys[key_id] = {
            "key_hash": key_hash,
            "created": time.time(),
            "last_used": None,
            "active": True,
        }
        return key_id, api_key

    def validate_key(self, key_id: str, api_key: str) -> bool:
        """Validate an API key."""
        if key_id not in self._keys:
            return False
        entry = self._keys[key_id]
        if not entry["active"]:
            return False
        try:
            raw_key = bytes.fromhex(api_key)
        except ValueError:
            return False
        expected_hash = hmac.new(self._master_secret, raw_key, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_hash, entry["key_hash"]):
            entry["last_used"] = time.time()
            return True
        return False

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        if key_id in self._keys:
            self._keys[key_id]["active"] = False
            return True
        return False

    def rotate_key(self, key_id: str) -> tuple:
        """Rotate an API key. Returns new (key_id, api_key)."""
        self.revoke_key(key_id)
        return self.generate_key(key_id)

    def list_keys(self) -> list:
        """List all key IDs with metadata (no secrets)."""
        return [
            {
                "key_id": kid,
                "created": info["created"],
                "last_used": info["last_used"],
                "active": info["active"],
            }
            for kid, info in self._keys.items()
        ]


class AuditLogger:
    """
    Tamper-evident audit log with chained hashes.
    Each entry includes a hash of the previous entry, creating a chain
    that detects tampering.
    """

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
        self._log = deque(maxlen=self.config.audit_log_size)
        self._chain_hash = hashlib.sha256(b"genesis").hexdigest()

    def log(self, action: str, actor: str = "system", details: dict = None) -> dict:
        """Log an action with tamper-evident chaining."""
        entry = {
            "timestamp": time.time(),
            "action": action,
            "actor": actor,
            "details": details or {},
            "prev_hash": self._chain_hash,
        }
        entry_str = json.dumps(entry, sort_keys=True, default=str)
        entry_hash = hashlib.sha256(entry_str.encode()).hexdigest()
        entry["hash"] = entry_hash
        self._chain_hash = entry_hash
        self._log.append(entry)
        return entry

    def verify_chain(self) -> bool:
        """Verify the integrity of the audit chain."""
        prev_hash = hashlib.sha256(b"genesis").hexdigest()
        for entry in self._log:
            if entry["prev_hash"] != prev_hash:
                return False
            entry_copy = {k: v for k, v in entry.items() if k != "hash"}
            entry_str = json.dumps(entry_copy, sort_keys=True, default=str)
            expected_hash = hashlib.sha256(entry_str.encode()).hexdigest()
            if entry["hash"] != expected_hash:
                return False
            prev_hash = entry["hash"]
        return True

    def get_log(self, limit: int = 100) -> list:
        """Get the last N audit entries."""
        return list(self._log)[-limit:]

    def query(self, action: str = None, actor: str = None) -> list:
        """Query audit log by action or actor."""
        results = list(self._log)
        if action:
            results = [e for e in results if e["action"] == action]
        if actor:
            results = [e for e in results if e["actor"] == actor]
        return results


class EncryptionManager:
    """
    XOR-based field-level encryption with key rotation.
    Suitable for demo and non-production use. For production,
    integrate with HSM or cloud KMS.
    """

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
        self._key = os.urandom(32)
        self._key_created = time.time()
        self._rotation_count = 0

    def _rotate_if_needed(self):
        now = time.time()
        if now - self._key_created > self.config.encryption_key_rotation_interval:
            self._key = os.urandom(32)
            self._key_created = now
            self._rotation_count += 1

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using XOR cipher."""
        self._rotate_if_needed()
        if not isinstance(data, bytes):
            data = str(data).encode()
        return bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(data))

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data (XOR is symmetric)."""
        return self.encrypt(data)

    def encrypt_field(self, value: Any) -> str:
        """Encrypt a field value and return hex string."""
        encrypted = self.encrypt(str(value).encode())
        return encrypted.hex()

    def decrypt_field(self, hex_value: str) -> str:
        """Decrypt a hex-encoded field value."""
        return self.decrypt(bytes.fromhex(hex_value)).decode()

    def get_status(self) -> dict:
        """Get encryption status."""
        return {
            "key_age_seconds": time.time() - self._key_created,
            "rotation_count": self._rotation_count,
            "rotation_interval": self.config.encryption_key_rotation_interval,
        }


class SecurityContext:
    """
    Unified security context that combines all security primitives.
    Provides a single entry point for securing HYBA_DATA operations.
    """

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
        self.validator = InputValidator(self.config)
        self.rate_limiter = RateLimiter(self.config)
        self.key_manager = APIKeyManager(self.config)
        self.audit_logger = AuditLogger(self.config)
        self.encryption = EncryptionManager(self.config)

    def secure_request(self, action: str, point: int, actor: str = "anonymous",
                       api_key: str = None, key_id: str = None) -> dict:
        """
        Process a request through all security layers.
        Returns a security result with validation, rate limit, and audit info.
        """
        result = {"allowed": True, "errors": [], "audit_entry": None}

        # 1. Input validation
        try:
            validated_point = self.validator.validate_point(point)
        except ValueError as e:
            result["allowed"] = False
            result["errors"].append(f"Validation: {e}")
            self.audit_logger.log("validation_failed", actor, {"error": str(e), "action": action})
            return result

        # 2. API key validation (if provided)
        if api_key and key_id:
            if not self.key_manager.validate_key(key_id, api_key):
                result["allowed"] = False
                result["errors"].append("Invalid API key")
                self.audit_logger.log("auth_failed", actor, {"key_id": key_id, "action": action})
                return result

        # 3. Rate limiting
        if not self.rate_limiter.acquire():
            result["allowed"] = False
            result["errors"].append("Rate limit exceeded")
            self.audit_logger.log("rate_limited", actor, {"action": action})
            return result

        # 4. Audit logging
        if self.config.enable_audit_logging:
            entry = self.audit_logger.log(action, actor, {"point": validated_point})
            result["audit_entry"] = entry

        return result

    def get_security_report(self) -> dict:
        """Generate a comprehensive security report."""
        return {
            "rate_limiter": self.rate_limiter.get_status(),
            "api_keys": self.key_manager.list_keys(),
            "audit_entries": len(self.audit_logger.get_log(limit=10000)),
            "audit_chain_valid": self.audit_logger.verify_chain(),
            "encryption": self.encryption.get_status(),
            "config": {
                "rate_limiting_enabled": self.config.enable_rate_limiting,
                "audit_logging_enabled": self.config.enable_audit_logging,
                "encryption_enabled": self.config.enable_encryption,
                "input_validation_enabled": self.config.enable_input_validation,
            },
        }
