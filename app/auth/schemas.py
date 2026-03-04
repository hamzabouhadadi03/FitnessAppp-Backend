"""Schémas Pydantic du module d'authentification."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class AuthSyncRequest(BaseModel):
    """Payload envoyé depuis le frontend après la connexion Auth0 pour synchroniser l'utilisateur avec la base de données."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class AuthSyncResponse(BaseModel):
    """Réponse après la synchronisation d'un utilisateur."""

    user_id: str
    email: str
    username: str
    is_onboarded: bool
    is_new_user: bool


class MeResponse(BaseModel):
    """Informations sur l'utilisateur actuellement authentifié."""

    user_id: str
    email: str
    username: str
    is_onboarded: bool
    is_active: bool
