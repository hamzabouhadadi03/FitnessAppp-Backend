"""Clients push notification — APNs (iOS) et FCM v1 (Android).

APNs : authentification par token JWT ES256 (clé .p8 Apple Developer).
FCM  : authentification OAuth2 via service account Google (API v1 REST).

Les tokens d'accès sont mis en cache dans Redis (TTL conservateur : 55 min).
SÉCURITÉ : aucun token ni clé privée n'est journalisé.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# ── APNs ───────────────────────────────────────────────────────────────────
_APNS_HOST_PROD = "https://api.push.apple.com"
_APNS_HOST_DEV = "https://api.development.push.apple.com"
_APNS_JWT_CACHE_KEY = "apns:provider_token"


async def _get_apns_jwt() -> str:
    """Génère ou récupère depuis Redis un token JWT APNs (valide 60 min, cache 55 min)."""
    import redis.asyncio as aioredis

    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        cached = await redis.get(_APNS_JWT_CACHE_KEY)
        if cached:
            return cached

        import jwt as pyjwt

        provider_token = pyjwt.encode(
            {"iss": settings.APNS_TEAM_ID, "iat": int(time.time())},
            settings.APNS_PRIVATE_KEY,
            algorithm="ES256",
            headers={"kid": settings.APNS_KEY_ID},
        )
        # Cache 55 minutes (les tokens APNs sont valides 60 min)
        await redis.setex(_APNS_JWT_CACHE_KEY, 55 * 60, provider_token)
        return provider_token
    finally:
        await redis.aclose()


async def send_apns(
    device_token: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> bool:
    """Envoie une notification push via APNs HTTP/2.

    Returns True si succès, False sinon (ne lève jamais d'exception).
    """
    if not settings.APNS_ENABLED:
        logger.debug("apns_skipped_disabled")
        return False

    host = _APNS_HOST_PROD if settings.is_production else _APNS_HOST_DEV

    try:
        jwt_token = await _get_apns_jwt()

        payload: dict[str, Any] = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "badge": 1,
            }
        }
        if data:
            payload.update(data)

        # http2=True nécessite le package h2 installé
        async with httpx.AsyncClient(http2=True, timeout=10.0) as client:
            resp = await client.post(
                f"{host}/3/device/{device_token}",
                json=payload,
                headers={
                    "authorization": f"bearer {jwt_token}",
                    "apns-topic": settings.APNS_BUNDLE_ID,
                    "apns-push-type": "alert",
                    "apns-priority": "10",
                },
            )

        if resp.status_code == 200:
            logger.info("apns_push_sent")
            return True

        logger.warning(
            "apns_push_failed",
            http_status=resp.status_code,
            reason=resp.text[:200],
        )
        return False

    except Exception as exc:
        logger.error("apns_push_error", error_type=type(exc).__name__)
        return False


# ── FCM v1 REST ────────────────────────────────────────────────────────────
_FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
_FCM_TOKEN_CACHE_KEY = "fcm:access_token"
_FCM_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


async def _get_fcm_access_token() -> str:
    """Récupère un access token OAuth2 pour FCM via le service account Google.

    google-auth est synchrone → exécuté dans un thread séparé.
    Token mis en cache dans Redis.
    """
    import redis.asyncio as aioredis

    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        cached = await redis.get(_FCM_TOKEN_CACHE_KEY)
        if cached:
            return cached

        import asyncio

        import google.auth.transport.requests
        import google.oauth2.service_account

        def _refresh_sync() -> tuple[str, float]:
            service_account_info = json.loads(settings.FCM_SERVICE_ACCOUNT_JSON)
            creds = google.oauth2.service_account.Credentials.from_service_account_info(
                service_account_info, scopes=_FCM_SCOPES
            )
            request = google.auth.transport.requests.Request()
            creds.refresh(request)
            expiry_ts = creds.expiry.timestamp() if creds.expiry else time.time() + 3600
            return creds.token, expiry_ts

        access_token, expiry_ts = await asyncio.to_thread(_refresh_sync)

        # Cache jusqu'à expiration - 5 min de marge
        ttl = max(60, int(expiry_ts - time.time()) - 300)
        await redis.setex(_FCM_TOKEN_CACHE_KEY, ttl, access_token)
        return access_token
    finally:
        await redis.aclose()


async def send_fcm(
    device_token: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> bool:
    """Envoie une notification push via FCM v1 REST API.

    Returns True si succès, False sinon (ne lève jamais d'exception).
    """
    if not settings.FCM_ENABLED:
        logger.debug("fcm_skipped_disabled")
        return False

    try:
        access_token = await _get_fcm_access_token()
        url = _FCM_ENDPOINT.format(project_id=settings.FCM_PROJECT_ID)

        message: dict[str, Any] = {
            "message": {
                "token": device_token,
                "notification": {"title": title, "body": body},
                "android": {
                    "priority": "HIGH",
                    "notification": {"sound": "default"},
                },
            }
        }
        if data:
            # FCM data doit être dict[str, str]
            message["message"]["data"] = {k: str(v) for k, v in data.items()}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json=message,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if resp.status_code == 200:
            logger.info("fcm_push_sent")
            return True

        logger.warning(
            "fcm_push_failed",
            http_status=resp.status_code,
            reason=resp.text[:200],
        )
        return False

    except Exception as exc:
        logger.error("fcm_push_error", error_type=type(exc).__name__)
        return False
