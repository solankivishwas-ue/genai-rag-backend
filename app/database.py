from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Async Engine (used by FastAPI) ────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""
    pass


# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a scoped async DB session per request.
    Auto-commits on success, rolls back on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Alembic Migration Runner ──────────────────────────────────────────────────
def run_migrations() -> None:
    """
    Run any pending Alembic migrations synchronously.
    Called once at application startup via the lifespan context.
    Uses the SYNC_DATABASE_URL (psycopg2) since Alembic is synchronous.
    """
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied successfully")


# ── Shutdown ──────────────────────────────────────────────────────────────────
async def dispose_engine() -> None:
    """Dispose the async connection pool on shutdown."""
    await engine.dispose()
    logger.info("Database engine disposed")
