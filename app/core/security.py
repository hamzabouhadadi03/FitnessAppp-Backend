"""Middleware de validation JWT pour Auth0.

Valide les JWT RS256 en utilisant les JWKS récupérés depuis Auth0 et mis en cache dans Redis.
Ne stocke, ne génère ni ne gère jamais de mots de passe.

Bibliothèque JWT : PyJWT (remplace python-jose, non maintenu, CVE-2024-33663/33664).
PyJWT est activement maintenu par l'équipe Okta/Auth0 et supporte nativement RS256 + JWKS.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

# PyJWT — import conventionnel : « import jwt » car le package s'appelle « PyJWT »
# mais son module Python est « jwt ».
import jwt as pyjwt
from jwt.algorithms import RSAAlgorithm          # Convertit un JWK (dict) en clé RSA Python
from jwt.exceptions import ExpiredSignatureError  # Sous-classe de InvalidTokenError
from jwt.exceptions import InvalidTokenError      # Exception de base pour tout échec JWT

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
    """Récupère les JWKS depuis Auth0 et les met en cache dans Redis pour REDIS_JWKS_TTL secondes.

    JWKS (JSON Web Key Set) : ensemble de clés publiques RSA publiées par Auth0 à l'URL
    https://<DOMAIN>/.well-known/jwks.json. Ces clés permettent de vérifier la signature
    des tokens JWT sans partager de secret entre Auth0 et notre backend.
    """
    redis = _get_redis()

    # Tentative de lecture depuis le cache Redis avant d'appeler Auth0
    cached = await redis.get(_JWKS_CACHE_KEY)
    if cached:
        return json.loads(cached)  # type: ignore[no-any-return]

    # Cache manquant ou expiré → appel HTTP vers Auth0
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.AUTH0_JWKS_URL)
        response.raise_for_status()
        jwks: dict[str, Any] = response.json()

    # Mise en cache avec TTL configurable (par défaut 3600 s = 1 h)
    await redis.setex(_JWKS_CACHE_KEY, settings.REDIS_JWKS_TTL, json.dumps(jwks))
    logger.info("jwks_fetched_and_cached", ttl=settings.REDIS_JWKS_TTL)
    return jwks


def _get_rsa_key(jwks: dict[str, Any], token: str) -> Any:
    """Extrait et convertit la clé RSA publique correspondant au « kid » du token.

    Différence clé avec python-jose :
    - python-jose acceptait un dictionnaire JWK brut  {kty, kid, n, e, ...}
    - PyJWT attend un objet clé RSA Python (cryptography.hazmat.primitives.asymmetric.rsa)
    → On utilise RSAAlgorithm.from_jwk() pour convertir le JWK JSON en objet clé RSA.

    Le « kid » (Key ID) est un identifiant présent à la fois dans l'en-tête du JWT
    et dans chaque entrée du JWKS. Il permet de sélectionner la bonne clé publique
    quand Auth0 fait une rotation de ses clés de signature.
    """
    try:
        # Décode l'en-tête du token sans vérifier la signature (lecture seule du kid)
        unverified_header = pyjwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise ValueError("Cannot parse token header") from exc

    kid = unverified_header.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            # Convertit le JWK (dictionnaire JSON) en objet clé RSA Python
            # json.dumps() re-sérialise le dict car from_jwk() attend une chaîne JSON
            return RSAAlgorithm.from_jwk(json.dumps(key))

    raise ValueError("No matching public key found in JWKS")


# ---------------------------------------------------------------------------
# Fonction de validation publique
# ---------------------------------------------------------------------------
async def validate_jwt(token: str) -> dict[str, Any]:
    """Valide un token JWT contre les JWKS d'Auth0.

    Vérifie dans l'ordre :
    1. Structure du token (3 segments base64url séparés par des points)
    2. Signature RSA-SHA256 avec la clé publique Auth0
    3. Expiration (claim « exp »)
    4. Audience (claim « aud » = notre API)
    5. Émetteur (claim « iss » = notre domaine Auth0)

    Retourne le payload décodé en cas de succès.
    Lève ValueError avec un message générique en cas d'échec
    (ne jamais exposer le détail de l'erreur JWT au client).
    """
    try:
        jwks = await _fetch_jwks()
        rsa_key = _get_rsa_key(jwks, token)

        # pyjwt.decode() vérifie signature + exp + aud + iss en une seule passe
        payload: dict[str, Any] = pyjwt.decode(
            token,
            rsa_key,
            algorithms=settings.AUTH0_ALGORITHMS,   # ["RS256"]
            audience=settings.AUTH0_AUDIENCE,        # ex. "https://api.fitprogress.com"
            issuer=settings.AUTH0_ISSUER,            # ex. "https://fitprogress.eu.auth0.com/"
        )
        return payload

    except ExpiredSignatureError as exc:
        # Token valide mais expiré → message spécifique pour que le client puisse rafraîchir
        logger.warning("jwt_expired")
        raise ValueError("Token has expired") from exc
    except InvalidTokenError as exc:
        # Signature invalide, audience incorrecte, issuer incorrect, format malformé, etc.
        logger.warning("jwt_invalid")
        raise ValueError("Invalid token") from exc
    except Exception as exc:
        # Erreur réseau (JWKS inaccessible), Redis down, etc.
        logger.error("jwt_validation_error", error_type=type(exc).__name__)
        raise ValueError("Token validation failed") from exc
