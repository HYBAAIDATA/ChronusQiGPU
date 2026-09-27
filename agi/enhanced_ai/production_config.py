"""Production configuration and hardening for Enhanced AGI."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ResourceLimitLevel(Enum):
    """Resource limit levels for different deployment scenarios."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ResourceQuotas:
    """Resource quotas to prevent exhaustion."""

    max_sessions: int = 1000
    max_memory_per_session_mb: int = 50
    max_kb_entries_per_domain: int = 10000
    max_conversation_history_length: int = 100
    max_concurrent_nlp_operations: int = 100
    session_ttl_seconds: int = 3600  # 1 hour
    cleanup_interval_seconds: int = 300  # 5 minutes

    def validate(self) -> bool:
        """Validate resource quota settings."""
        if self.max_sessions < 1:
            raise ValueError("max_sessions must be at least 1")
        if self.max_memory_per_session_mb < 10:
            raise ValueError("max_memory_per_session_mb must be at least 10")
        if self.session_ttl_seconds < 60:
            raise ValueError("session_ttl_seconds must be at least 60")
        return True


class CircuitBreakerState(Enum):
    """States for circuit breaker pattern."""

    CLOSED = "closed"  # Operating normally
    OPEN = "open"  # Rejecting requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""

    failure_threshold: int = 5
    success_threshold_half_open: int = 2
    timeout_seconds: float = 30.0

    def validate(self) -> bool:
        """Validate circuit breaker settings."""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if self.success_threshold_half_open < 1:
            raise ValueError("success_threshold_half_open must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        return True


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10


@dataclass
class ProductionConfig:
    """Production configuration for Enhanced AGI."""

    environment: ResourceLimitLevel = ResourceLimitLevel.PRODUCTION
    resource_quotas: ResourceQuotas = None
    circuit_breaker: CircuitBreakerConfig = None
    rate_limit: RateLimitConfig = None
    enable_metrics: bool = True
    enable_audit_logging: bool = True
    log_level: str = "INFO"

    def __post_init__(self):
        """Initialize defaults if not set."""
        if self.resource_quotas is None:
            self.resource_quotas = ResourceQuotas()
        if self.circuit_breaker is None:
            self.circuit_breaker = CircuitBreakerConfig()
        if self.rate_limit is None:
            self.rate_limit = RateLimitConfig()

    def validate(self) -> bool:
        """Validate all configuration."""
        self.resource_quotas.validate()
        self.circuit_breaker.validate()
        logger.info(f"Production config validated for {self.environment.value}")
        return True

    @classmethod
    def get_development(cls) -> "ProductionConfig":
        """Get development configuration."""
        config = cls(environment=ResourceLimitLevel.DEVELOPMENT)
        config.resource_quotas = ResourceQuotas(
            max_sessions=10, session_ttl_seconds=7200
        )
        config.enable_audit_logging = False
        config.log_level = "DEBUG"
        return config

    @classmethod
    def get_staging(cls) -> "ProductionConfig":
        """Get staging configuration."""
        config = cls(environment=ResourceLimitLevel.STAGING)
        config.resource_quotas = ResourceQuotas(
            max_sessions=100, session_ttl_seconds=3600
        )
        config.log_level = "INFO"
        return config

    @classmethod
    def get_production(cls) -> "ProductionConfig":
        """Get production configuration."""
        config = cls(environment=ResourceLimitLevel.PRODUCTION)
        config.resource_quotas = ResourceQuotas(
            max_sessions=1000, session_ttl_seconds=1800
        )
        config.enable_metrics = True
        config.enable_audit_logging = True
        config.log_level = "WARNING"
        return config


# Global configuration instance
_current_config: Optional[ProductionConfig] = None


def get_config() -> ProductionConfig:
    """Get current production configuration."""
    global _current_config
    if _current_config is None:
        _current_config = ProductionConfig.get_production()
        _current_config.validate()
    return _current_config


def set_config(config: ProductionConfig) -> None:
    """Set production configuration."""
    global _current_config
    config.validate()
    _current_config = config
    logger.info(f"Configuration updated to {config.environment.value}")


def reset_config() -> None:
    """Reset to default production configuration."""
    global _current_config
    _current_config = None
