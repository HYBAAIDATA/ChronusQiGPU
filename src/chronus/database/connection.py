"""Database connection and session management for Thesus.

Database connection configuration structures; no live pooling executes in this package.
with proper lifecycle management, retry logic, and health checks.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from chronus.database.config import DatabaseConfig

logger = logging.getLogger(__name__)


class ThesusDatabase:
    """Database manager configuration holder for Chronus.

    Manages PostgreSQL connections with:
    - Async connection pooling
    - Connection retry logic
    - Health check monitoring
    - Session lifecycle management
    """

    def __init__(self, config: DatabaseConfig) -> None:
        """Initialize Thesus database manager.

        Args:
            config: Database configuration.
        """
        self.config = config
        self._engine = None
        self._session_factory = None
        self._initialized = False
        self._connection_count = 0

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._engine is not None

    def build_url(self) -> str:
        """Build SQLAlchemy async connection URL."""
        scheme = "postgresql+asyncpg"
        if self.config.ssl_mode:
            return f"{scheme}://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?sslmode={self.config.ssl_mode}"
        return f"{scheme}://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"

    async def connect(self) -> None:
        """Establish database connection with retry logic."""
        if self._initialized:
            return

        attempt = 0
        while attempt < self.config.max_retries:
            try:
                self._engine = create_async_engine(
                    self.build_url(),
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow,
                    pool_timeout=self.config.pool_timeout,
                    pool_recycle=self.config.pool_recycle,
                    pool_pre_ping=self.config.pool_pre_ping,
                    echo=False,
                )
                self._session_factory = async_sessionmaker(
                    bind=self._engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autocommit=False,
                    autoflush=False,
                )
                self._initialized = True
                logger.info(
                    f"Thesus database connected: {self.config.host}:{self.config.port}/{self.config.database}"
                )
                return

            except Exception as e:
                attempt += 1
                logger.warning(
                    f"Thesus database connection attempt {attempt} failed: {e}"
                )
                if attempt >= self.config.max_retries:
                    raise
                await asyncio.sleep(self.config.retry_delay)

    async def disconnect(self) -> None:
        """Close database connections."""
        if self._engine is None:
            return

        async with self._engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.dispose())
        self._engine = None
        self._session_factory = None
        self._initialized = False
        logger.info("Thesus database disconnected")

    async def health_check(self) -> dict:
        """Perform database health check.

        Returns:
            Health check result with connection status and latency.
        """
        if self._engine is None:
            return {"status": "disconnected", "latency_ms": 0}

        start = asyncio.get_event_loop().time()

        try:
            async with self._engine.begin() as conn:
                await conn.exec_driver_sql("SELECT 1")
            latency_ms = (asyncio.get_event_loop().time() - start) * 1000
            return {
                "status": "healthy",
                "latency_ms": round(latency_ms, 3),
                "connection_pool": self._engine.pool.size(),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "latency_ms": 0}

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session context manager.

        Yields:
            AsyncSession for database operations.
        """
        if not self._initialized:
            await self.connect()

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()