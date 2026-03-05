"""Routes des notifications push — tokens de device et préférences."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.notifications.models import UserNotificationPrefs
from app.notifications.schemas import (
    DeviceTokenResponse,
    NotificationPrefsRequest,
    NotificationPrefsResponse,
    RegisterDeviceTokenRequest,
    SendTestPushRequest,
)
from app.notifications.service import NotificationService
from app.users.models import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ── Tokens de device ────────────────────────────────────────────────────────

@router.post(
    "/device-token",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register device token for push notifications",
)
async def register_device_token(
    payload: RegisterDeviceTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceTokenResponse:
    """Enregistre ou réactive un token APNs (iOS) ou FCM (Android).

    Idempotent : appeler plusieurs fois avec le même token est sûr.
    """
    device = await NotificationService.register_device(db, current_user.id, payload)
    return DeviceTokenResponse.model_validate(device)


@router.delete(
    "/device-token/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deregister device token (unsubscribe from push notifications)",
)
async def deregister_device_token(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Désactive un token lors de la déconnexion ou désabonnement."""
    await NotificationService.deregister_device(db, current_user.id, token)


# ── Préférences ─────────────────────────────────────────────────────────────

@router.get(
    "/preferences",
    response_model=NotificationPrefsResponse,
    summary="Get notification preferences",
)
async def get_notification_prefs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPrefsResponse:
    prefs = await NotificationService.get_or_create_prefs(db, current_user.id)
    return _prefs_to_response(prefs)


@router.put(
    "/preferences",
    response_model=NotificationPrefsResponse,
    summary="Update notification preferences",
)
async def update_notification_prefs(
    payload: NotificationPrefsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPrefsResponse:
    prefs = await NotificationService.update_prefs(db, current_user.id, payload)
    return _prefs_to_response(prefs)


# ── Test push (dev only) ────────────────────────────────────────────────────

@router.post(
    "/test-push",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a test push notification to all active device tokens",
)
async def send_test_push(
    payload: SendTestPushRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Envoie une notification de test via Celery.

    Utile pour valider l'intégration APNs/FCM depuis Swagger.
    """
    result = await NotificationService.send_test_push(
        db, current_user.id, payload.title, payload.body
    )
    return result


# ── Helper ──────────────────────────────────────────────────────────────────

def _prefs_to_response(prefs: UserNotificationPrefs) -> NotificationPrefsResponse:
    try:
        reminder_days: list[str] = json.loads(prefs.reminder_days)
    except (json.JSONDecodeError, TypeError):
        reminder_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    return NotificationPrefsResponse(
        workout_reminder_enabled=prefs.workout_reminder_enabled,
        reminder_hour=prefs.reminder_hour,
        reminder_days=reminder_days,
    )
