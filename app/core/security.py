"""Middleware de validation JWT pour Auth0.

Valide les JWT RS256 en utilisant les JWKS récupérés depuis Auth0 et mis en cache dans Redis.
Ne stocke, ne génère ni ne gère jamais de mots de passe.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Client Redis (import différé pour éviter les dépendances circulaires)
# ---------------------------------------------------------------------------
_redis_client: Any = None


def _get_redis() -> Any:
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


# ---------------------------------------------------------------------------
# Récupération et mise en cache des JWKS
# ---------------------------------------------------------------------------
_JWKS_CACHE_KEY = "auth0:jwks"


async def _fetch_jwks() -> dict[str, Any]:
    """Récupère les JWKS depuis Auth0 et les met en cache dans Redis pour REDIS_JWKS_TTL secondes."""
    redis = _get_redis()

    cached = await redis.get(_JWKS_CACHE_KEY)
    if cached:
        return json.loads(cached)  # type: ignore[no-any-return]

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.AUTH0_JWKS_URL)
        response.raise_for_status()
        jwks: dict[str, Any] = response.json()

    await redis.setex(_JWKS_CACHE_KEY, settings.REDIS_JWKS_TTL, json.dumps(jwks))
    logger.info("jwks_fetched_and_cached", ttl=settings.REDIS_JWKS_TTL)
    return jwks


def _get_rsa_key(jwks: dict[str, Any], token: str) -> dict[str, Any]:
    """Extrait la clé RSA correspondant à l'en-tête kid du token."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise ValueError("Cannot parse token header") from exc

    kid = unverified_header.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }
    raise ValueError("No matching public key found in JWKS")


# ---------------------------------------------------------------------------
# Fonction de validation publique
# ---------------------------------------------------------------------------
async def validate_jwt(token: str) -> dict[str, Any]:
    """Valide un token JWT contre les JWKS d'Auth0.

    Retourne le payload décodé en cas de succès.
    Lève ValueError avec un message générique en cas d'échec.
    """
    try:
        jwks = await _fetch_jwks()
        rsa_key = _get_rsa_key(jwks, token)

        payload: dict[str, Any] = jwt.decode(
            token,
            rsa_key,
            algorithms=settings.AUTH0_ALGORITHMS,
            audience=settings.AUTH0_AUDIENCE,
            issuer=settings.AUTH0_ISSUER,
        )
        return payload

    except ExpiredSignatureError as exc:
        logger.warning("jwt_expired")
        raise ValueError("Token has expired") from exc
    except JWTError as exc:
        logger.warning("jwt_invalid")
        raise ValueError("Invalid token") from exc
    except Exception as exc:
        logger.error("jwt_validation_error", error_type=type(exc).__name__)
        raise ValueError("Token validation failed") from exc
