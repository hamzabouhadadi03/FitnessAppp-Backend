"""Dépendances FastAPI partagées.

get_current_user : valide le JWT, charge l'utilisateur depuis la base de données, impose l'authentification.
verify_ownership : lève une erreur 403 si la ressource n'appartient pas à l'utilisateur courant.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import validate_jwt

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> "User":  # type: ignore[name-defined]  # noqa: F821
    """Extrait et valide le JWT Bearer, puis retourne l'utilisateur en base de données.

    Contrat de sécurité :
    - Lève une erreur 401 si le token est absent, invalide ou expiré.
    - Ne divulgue jamais les détails du token dans les messages d'erreur.
    """
    # Import différé pour éviter les dépendances circulaires
    from app.users.service import UserService

    if not credentials:
        raise UnauthorizedError()

    token = credentials.credentials
    try:
        payload = await validate_jwt(token)
    except ValueError:
        raise UnauthorizedError()

    auth0_sub: str | None = payload.get("sub")
    if not auth0_sub:
        raise UnauthorizedError()

    user = await UserService.get_by_auth0_sub(db, auth0_sub)
    if not user or not user.is_active:
        raise UnauthorizedError()

    return user


def verify_ownership(resource_user_id: uuid.UUID, current_user_id: uuid.UUID) -> None:
    """Lève une erreur 403 si la ressource n'appartient pas à l'utilisateur courant.

    Toujours appeler cette fonction avant de retourner ou modifier une ressource appartenant à un utilisateur.
    """
    if resource_user_id != current_user_id:
        raise ForbiddenError()
