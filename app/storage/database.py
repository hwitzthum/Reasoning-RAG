"""Database setup and connection management."""

from collections.abc import AsyncIterator
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.storage.models import Base


# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"timeout": 30},
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _run_lightweight_migrations(sync_conn) -> None:
    """Apply additive schema migrations required for newer runtime fields."""
    inspector = inspect(sync_conn)
    if "query_log" not in inspector.get_table_names():
        existing_query_log_columns = set()
    else:
        existing_query_log_columns = {col["name"] for col in inspector.get_columns("query_log")}

    if existing_query_log_columns:
        if "status" not in existing_query_log_columns:
            sync_conn.execute(text("ALTER TABLE query_log ADD COLUMN status VARCHAR(20)"))
            sync_conn.execute(text("UPDATE query_log SET status = 'processing' WHERE status IS NULL"))

        if "error_message" not in existing_query_log_columns:
            sync_conn.execute(text("ALTER TABLE query_log ADD COLUMN error_message TEXT"))

    if "query_cache" in inspector.get_table_names():
        existing_query_cache_columns = {col["name"] for col in inspector.get_columns("query_cache")}
        if "cited_doc_ids" not in existing_query_cache_columns:
            sync_conn.execute(text("ALTER TABLE query_cache ADD COLUMN cited_doc_ids JSON"))



async def init_db() -> None:
    """Initialize database by creating all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_run_lightweight_migrations)
        # Enable WAL mode for concurrent read/write access and set a safe sync level.
        # WAL mode is a database-level setting that persists after the first PRAGMA call.
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    Dependency for FastAPI endpoints to get database session.

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
