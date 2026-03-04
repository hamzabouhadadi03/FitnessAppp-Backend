"""Service d'authentification — gère la synchronisation des utilisateurs depuis Auth0."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import AuthSyncRequest, AuthSyncResponse
from app.core.logging import get_logger
from app.users.models import User
from app.users.service import UserService

logger = get_logger(__name__)


class AuthService:
    @staticmethod
    async def sync_user(
        db: AsyncSession,
        auth0_sub: str,
        payload: AuthSyncRequest,
    ) -> AuthSyncResponse:
        """Synchronise l'utilisateur Auth0 dans la base de données. Crée l'utilisateur à la première connexion."""
        existing = await UserService.get_by_auth0_sub(db, auth0_sub)
        is_new = existing is None

        if is_new:
            user = await UserService.create_user(
                db=db,
                auth0_sub=auth0_sub,
                email=str(payload.email),
                username=payload.username,
            )
            logger.info("user_created", is_new=True)
        else:
            user = existing  # type: ignore[assignment]
            logger.info("user_synced", is_new=False)

        return AuthSyncResponse(
            user_id=str(user.id),
            email=user.email,
            username=user.username,
            is_onboarded=user.is_onboarded,
            is_new_user=is_new,
        )
