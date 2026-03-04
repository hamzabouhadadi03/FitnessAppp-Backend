"""Service utilisateur — toutes les opérations de base de données liées aux utilisateurs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.users.models import SplitType, User, UserGoal, UserLevel
from app.users.schemas import OnboardingRequest, UpdateProfileRequest

logger = get_logger(__name__)


class UserService:
    @staticmethod
    async def get_by_auth0_sub(db: AsyncSession, auth0_sub: str) -> User | None:
        result = await db.execute(
            select(User).where(User.auth0_sub == auth0_sub, User.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User")
        return user

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        result = await db.execute(
            select(User).where(User.email == email, User.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(
        db: AsyncSession,
        auth0_sub: str,
        email: str,
        username: str,
    ) -> User:
        # Vérifier si l'email ou le nom d'utilisateur existe déjà
        existing_email = await UserService.get_by_email(db, email)
        if existing_email:
            raise ConflictError("Email already registered")

        result = await db.execute(
            select(User).where(User.username == username, User.is_deleted.is_(False))
        )
        if result.scalar_one_or_none():
            raise ConflictError("Username already taken")

        user = User(
            auth0_sub=auth0_sub,
            email=email,
            username=username,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info("user_created_in_db", username=username)
        return user

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user: User,
        payload: UpdateProfileRequest,
    ) -> User:
        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def complete_onboarding(
        db: AsyncSession,
        user: User,
        payload: OnboardingRequest,
    ) -> User:
        user.goal = payload.goal
        user.level = payload.level
        user.frequency = payload.frequency
        user.preferred_split = payload.preferred_split
        user.is_onboarded = True
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info("user_onboarded")
        return user

    @staticmethod
    async def soft_delete_account(db: AsyncSession, user: User) -> None:
        user.is_deleted = True
        user.is_active = False
        user.deleted_at = datetime.now(tz=timezone.utc)
        db.add(user)
        await db.flush()
        logger.info("user_account_soft_deleted")
