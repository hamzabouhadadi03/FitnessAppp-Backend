"""Test configuration: async test client, in-memory SQLite DB, mock Auth0 JWT."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.base_model import BaseModel
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.main import create_app
from app.users.models import User

# ---------------------------------------------------------------------------
# Test database — SQLite in-memory (fast, isolated)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Create all tables once per test session."""
    # Import all models to register them with metadata
    import app.users.models  # noqa: F401
    import app.exercises.models  # noqa: F401
    import app.programs.models  # noqa: F401
    import app.workouts.models  # noqa: F401
    import app.progression.models  # noqa: F401
    import app.gamification.models  # noqa: F401

    async with test_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test DB session with automatic rollback."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.rollback()
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Test user fixture
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and persist a test user."""
    user = User(
        id=uuid.uuid4(),
        auth0_sub="auth0|test_user_123",
        email="test@fitprogress.io",
        username="testuser",
        is_active=True,
        is_onboarded=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Another user — for testing ownership isolation."""
    user = User(
        id=uuid.uuid4(),
        auth0_sub="auth0|other_user_456",
        email="other@fitprogress.io",
        username="otheruser",
        is_active=True,
        is_onboarded=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# FastAPI test client with mocked dependencies
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def app_with_mocked_auth(test_user: User, db_session: AsyncSession) -> FastAPI:
    """FastAPI app with Auth0 JWT validation mocked and test DB injected."""
    application = create_app()

    # Override DB dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    # Override auth dependency to return test_user directly
    async def override_get_current_user() -> User:
        return test_user

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = override_get_current_user

    return application


@pytest_asyncio.fixture
async def client(app_with_mocked_auth: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client authenticated as test_user."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_mocked_auth),
        base_url="http://test",
        headers={"Authorization": "Bearer fake_test_token"},
    ) as c:
        yield c


@pytest_asyncio.fixture
async def unauthenticated_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with no authentication."""
    application = create_app()

    # Only override the DB — do NOT override auth
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Mock JWT validator
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_redis_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent real Redis/JWKS calls during tests."""
    async def mock_validate_jwt(token: str) -> dict[str, Any]:
        if token == "fake_test_token":
            return {"sub": "auth0|test_user_123", "aud": "test-audience"}
        if token == "expired_token":
            raise ValueError("Token has expired")
        raise ValueError("Invalid token")

    monkeypatch.setattr("app.core.security.validate_jwt", mock_validate_jwt)
    monkeypatch.setattr("app.auth.router.validate_jwt", mock_validate_jwt)
