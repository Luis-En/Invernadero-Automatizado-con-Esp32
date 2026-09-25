"""Shared pytest fixtures.

Uses a throwaway SQLite file per test session and the app's real dependency
overrides, so tests exercise the same routers and schemas as production.
"""
import os
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_tmpdir = tempfile.mkdtemp(prefix="greenhouse-test-")
TEST_DB_PATH = os.path.join(_tmpdir, "test.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

from app.auth import get_password_hash  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app import seed  # noqa: E402

engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_PATH}")
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # Seed default crops/config like the app lifespan does in production.
    await seed.ensure_seed_data(session_factory=TestSessionLocal)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _make_user(db, username: str, role: str, password: str) -> User:
    user = User(
        username=username,
        email=f"{username}@test.local",
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db):
    return await _make_user(db, "admin_test", "admin", "adminpass123")


@pytest_asyncio.fixture
async def viewer_user(db):
    return await _make_user(db, "viewer_test", "viewer", "viewerpass123")


@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    resp = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def viewer_token(client, viewer_user):
    resp = await client.post(
        "/api/auth/login",
        json={"username": viewer_user.username, "password": "viewerpass123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def auth_admin(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def auth_viewer(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}
