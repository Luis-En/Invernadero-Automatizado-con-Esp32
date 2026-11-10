import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.models import Base


engine = create_async_engine(
    settings.database_url_absolute,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url_absolute else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _run_migrations_sync() -> None:
    """Apply Alembic migrations (or stamp an existing pre-Alembic database)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    url = settings.database_url_absolute.replace("+aiosqlite", "")
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(alembic_ini.parent / "alembic"))
    config.set_main_option("sqlalchemy.url", url)

    sync_engine = create_engine(url)
    try:
        inspector = inspect(sync_engine)
        # A database created before Alembic already has the schema; stamp it
        # instead of replaying CREATE TABLE statements.
        if not inspector.has_table("alembic_version") and inspector.has_table("users"):
            command.stamp(config, "head")
        else:
            command.upgrade(config, "head")
    finally:
        sync_engine.dispose()


async def init_db():
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    if alembic_ini.exists():
        try:
            await asyncio.to_thread(_run_migrations_sync)
            _secure_sqlite_permissions()
            return
        except ImportError:
            # Alembic is a production dependency; keep a development fallback
            # for environments that only installed the minimal test set.
            pass
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _secure_sqlite_permissions()


def _secure_sqlite_permissions() -> None:
    """The DB stores password hashes and telemetry; keep it owner-only."""
    url = settings.database_url_absolute
    if not url.startswith("sqlite"):
        return
    path = url.split("///", 1)[-1]
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(path + suffix)
        if candidate.exists():
            try:
                candidate.chmod(0o600)
            except OSError:
                pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
