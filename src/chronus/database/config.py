"""Database configuration for Thesus Database System.

Database configuration structures with documented defaults.
retry logic, and environment-based configuration.
"""

import os
from typing import Optional

from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """Database configuration model for Thesus.

    Loads from environment variables with sensible defaults.
    """

    # PostgreSQL connection
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="chronus_quantum", description="Database name")
    username: str = Field(default="chronus", description="Database username")
    password: str = Field(default="", description="Database password")
    ssl_mode: str = Field(default="prefer", description="SSL mode")
    ssl_cert: Optional[str] = Field(default=None, description="SSL certificate path")

    # Connection pool settings
    pool_size: int = Field(default=20, description="Pool size")
    max_overflow: int = Field(default=10, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool timeout (seconds)")
    pool_recycle: int = Field(default=3600, description="Recycle connections (seconds)")

    # Pool settings
    pool_pre_ping: bool = Field(
        default=True, description="Test connections before use"
    )
    pool_idle_timeout: int = Field(
        default=300, description="Idle timeout (seconds)"
    )

    # Connection retry
    max_retries: int = Field(default=3, description="Max connection retries")
    retry_delay: float = Field(default=1.0, description="Retry delay (seconds)")

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        return cls(
            host=os.getenv("THESISUS_DB_HOST", "localhost"),
            port=int(os.getenv("THESISUS_DB_PORT", "5432")),
            database=os.getenv("THESISUS_DB_DATABASE", "chronus_quantum"),
            username=os.getenv("THESISUS_DB_USERNAME", "chronus"),
            password=os.getenv("THESISUS_DB_PASSWORD", ""),
            ssl_mode=os.getenv("THESISUS_DB_SSL_MODE", "prefer"),
            pool_size=int(os.getenv("THESISUS_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("THESISUS_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("THESISUS_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("THESISUS_POOL_RECYCLE", "3600")),
            max_retries=int(os.getenv("THESISUS_MAX_RETRIES", "3")),
        )


class MigrationConfig(BaseModel):
    """Migration configuration."""

    migrations_dir: str = Field(
        default="src/chronus/database/migrations", description="Migrations directory"
    )
    auto_migrate: bool = Field(
        default=True, description="Auto-run migrations on startup"
    )
    log_migrations: bool = Field(default=True, description="Log migrations")