"""Routes d'authentification : /auth/sync et /auth/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import AuthSyncRequest, AuthSyncResponse, MeResponse
from app.auth.service import AuthService
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import validate_jwt
from app.core.exceptions import UnauthorizedError
from app.users.models import User
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/sync", response_model=AuthSyncResponse, summary="Sync Auth0 user to database")
async def sync_user(
    payload: AuthSyncRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthSyncResponse:
    """Appelé après la connexion Auth0. Crée l'utilisateur en base de données lors du premier appel, synchronise lors des appels suivants.

    Limitation de débit : 10 requêtes/minute/IP.
    """
    if not credentials:
        raise UnauthorizedError()
    try:
        jwt_payload = await validate_jwt(credentials.credentials)
    except ValueError:
        raise UnauthorizedError()

    auth0_sub: str | None = jwt_payload.get("sub")
    if not auth0_sub:
        raise UnauthorizedError()

    return await AuthService.sync_user(db, auth0_sub, payload)


@router.get("/me", response_model=MeResponse, summary="Get current authenticated user")
async def me(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    """Retourne le profil de l'utilisateur actuellement authentifié."""
    return MeResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        is_onboarded=current_user.is_onboarded,
        is_active=current_user.is_active,
    )
