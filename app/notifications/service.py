"""Service métier — tokens de device et préférences de notification."""
from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.notifications.models import DeviceToken, Platform, UserNotificationPrefs
from app.notifications.schemas import NotificationPrefsRequest, RegisterDeviceTokenRequest


class NotificationService:

    @staticmethod
    async def register_device(
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: RegisterDeviceTokenRequest,
    ) -> DeviceToken:
        """Enregistre (ou réactive) un token de device.

        Idempotent : si le token existe déjà, on le réaffecte à l'utilisateur
        courant et on le marque actif (cas de ré-installation de l'app).
        """
        result = await db.execute(
            select(DeviceToken).where(DeviceToken.token == payload.token)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.user_id = user_id
            existing.is_active = True
            existing.app_version = payload.app_version
            existing.is_deleted = False
            existing.deleted_at = None
            await db.commit()
            await db.refresh(existing)
            return existing

        device = DeviceToken(
            user_id=user_id,
            token=payload.token,
            platform=payload.platform,
            is_active=True,
            app_version=payload.app_version,
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)
        return device

    @staticmethod
    async def deregister_device(
        db: AsyncSession,
        user_id: uuid.UUID,
        token: str,
    ) -> None:
        """Désactive un token (déconnexion / désabonnement aux notifications)."""
        result = await db.execute(
            select(DeviceToken).where(
                DeviceToken.token == token,
                DeviceToken.user_id == user_id,
                DeviceToken.is_deleted.is_(False),
            )
        )
        device = result.scalar_one_or_none()
        if not device:
            raise NotFoundError("Device token")
        device.is_active = False
        await db.commit()

    @staticmethod
    async def get_active_tokens(
        db: AsyncSession, user_id: uuid.UUID
    ) -> list[DeviceToken]:
        """Retourne tous les tokens actifs d'un utilisateur."""
        result = await db.execute(
            select(DeviceToken).where(
                DeviceToken.user_id == user_id,
                DeviceToken.is_active.is_(True),
                DeviceToken.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())

    # ── Préférences ────────────────────────────────────────────────────────

    @staticmethod
    async def get_or_create_prefs(
        db: AsyncSession, user_id: uuid.UUID
    ) -> UserNotificationPrefs:
        result = await db.execute(
            select(UserNotificationPrefs).where(
                UserNotificationPrefs.user_id == user_id
            )
        )
        prefs = result.scalar_one_or_none()
        if not prefs:
            prefs = UserNotificationPrefs(user_id=user_id)
            db.add(prefs)
            await db.commit()
            await db.refresh(prefs)
        return prefs

    @staticmethod
    async def update_prefs(
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: NotificationPrefsRequest,
    ) -> UserNotificationPrefs:
        prefs = await NotificationService.get_or_create_prefs(db, user_id)
        prefs.workout_reminder_enabled = payload.workout_reminder_enabled
        prefs.reminder_hour = payload.reminder_hour
        prefs.reminder_days = json.dumps(payload.reminder_days)
        await db.commit()
        await db.refresh(prefs)
        return prefs

    # ── Envoi de test ──────────────────────────────────────────────────────

    @staticmethod
    async def send_test_push(
        db: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        body: str,
    ) -> dict[str, int]:
        """Envoie une notification de test à tous les tokens actifs de l'utilisateur."""
        from app.notifications.tasks import send_push_to_user

        tokens = await NotificationService.get_active_tokens(db, user_id)
        if not tokens:
            return {"queued": 0, "message": "No active device tokens"}

        send_push_to_user.delay(
            user_id=str(user_id),
            title=title,
            body=body,
            data={"type": "test"},
        )
        return {"queued": len(tokens)}
