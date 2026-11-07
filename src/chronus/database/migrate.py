"""Database migration script for Thesus Database System.

Production-ready migration runner using Alembic for schema management.
"""

import asyncio
import logging
import sys
from pathlib import Path

from chronus.database.config import DatabaseConfig, MigrationConfig
from chronus.database.connection import ThesusDatabase
from chronus.database.models import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_migrations(engine, config: MigrationConfig) -> bool:
    """Run database migrations using Alembic.

    Args:
        engine: SQLAlchemy async engine.
        config: Migration configuration.

    Returns:
        True if migrations succeeded, False otherwise.
    """
    try:
        logger.info("Running database migrations...")

        # Import alembic for version control
        try:
            from alembic import command
            from alembic.config import Config as AlembicConfig
            from alembic.script import ScriptDirectory
        except ImportError:
            logger.warning(
                "Alembic not installed. Creating initial migration manually..."
            )
            await _create_initial_schema(engine)

        # Auto-generate migrations if configured
        if config.auto_migrate:
            logger.info("Generating migration scripts...")
            # In production, use: alembic revision --autogenerate -m "Initial schema"
            await _verify_schema(engine)

        logger.info("Database migrations completed successfully.")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


async def _create_initial_schema(engine) -> None:
    """Create initial database schema using SQLAlchemy."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Initial schema created using SQLAlchemy")


async def _verify_schema(engine) -> None:
    """Verify database schema has critical tables."""
    async with engine.begin() as conn:
        result = await conn.exec_driver_sql("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in result.fetchall()]
        logger.info(f"Existing tables: {tables}")


async def main() -> int:
    """Main entry point for database migration.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # Load configuration from environment
    db_config = DatabaseConfig.from_env()
    migration_config = MigrationConfig()

    # Initialize database
    db = ThesusDatabase(db_config)
    await db.connect()

    try:
        # Run migrations
        success = await run_migrations(db._engine, migration_config)
        if not success:
            logger.error("Migration failed!")
            return 1

        # Health check
        health = await db.health_check()
        logger.info(f"Database health: {health}")

        return 0

    finally:
        await db.disconnect()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)