"""Tâches Celery — push notifications et planification des rappels.

Architecture : Celery workers sont des processus séparés qui créent leur propre
event loop asyncio via asyncio.run(). Chaque tâche crée sa propre connexion DB
pour éviter les conflits de pool asyncpg entre event loops.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


def _run(coro: Any) -> Any:
    """Exécute une coroutine dans un nouvel event loop (Celery est synchrone)."""
    return asyncio.run(coro)


def _make_session():
    """Crée un moteur SQLAlchemy et une session factory indépendants.

    Nécessaire car Celery workers sont des processus séparés.
    Utilise un pool minimal (2 connexions) adapté aux tâches de courte durée.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.config import get_settings

    s = get_settings()
    engine = create_async_engine(
        s.DATABASE_URL,
        pool_size=2,
        max_overflow=2,
        pool_pre_ping=True,
        echo=False,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


# ===========================================================================
# Tâche : envoi de push à un utilisateur
# ===========================================================================

@celery_app.task(
    name="notifications.send_push_to_user",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_push_to_user(
    self,
    user_id: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Envoie une notification push à tous les tokens actifs d'un utilisateur.

    Args:
        user_id : UUID de l'utilisateur (str).
        title   : Titre de la notification.
        body    : Corps de la notification.
        data    : Payload additionnel (optionnel).

    Returns dict avec les compteurs ios/android/failed.
    """
    try:
        return _run(_send_push_impl(user_id, title, body, data))
    except Exception as exc:
        logger.error(
            "push_task_error",
            task_id=self.request.id,
            attempt=self.request.retries + 1,
            error_type=type(exc).__name__,
        )
        raise self.retry(exc=exc)


async def _send_push_impl(
    user_id: str,
    title: str,
    body: str,
    data: dict[str, Any] | None,
) -> dict[str, int]:
    from sqlalchemy import select

    from app.notifications.models import DeviceToken, Platform
    from app.notifications.push import send_apns, send_fcm

    engine, factory = _make_session()
    sent = {"ios": 0, "android": 0, "failed": 0}

    try:
        async with factory() as db:
            result = await db.execute(
                select(DeviceToken).where(
                    DeviceToken.user_id == uuid.UUID(user_id),
                    DeviceToken.is_active.is_(True),
                    DeviceToken.is_deleted.is_(False),
                )
            )
            tokens = list(result.scalars().all())

        for token_obj in tokens:
            if token_obj.platform == Platform.IOS:
                ok = await send_apns(token_obj.token, title, body, data)
                if ok:
                    sent["ios"] += 1
                else:
                    sent["failed"] += 1
            else:
                ok = await send_fcm(token_obj.token, title, body, data)
                if ok:
                    sent["android"] += 1
                else:
                    sent["failed"] += 1

    finally:
        await engine.dispose()

    logger.info("push_batch_done", ios=sent["ios"], android=sent["android"], failed=sent["failed"])
    return sent


# ===========================================================================
# Tâche périodique : planification des rappels d'entraînement
# ===========================================================================

@celery_app.task(name="notifications.schedule_workout_reminders")
def schedule_workout_reminders() -> dict[str, int]:
    """Tâche Beat : envoyée toutes les heures à H:00 UTC.

    Interroge les utilisateurs dont reminder_hour == heure actuelle ET
    dont le jour courant figure dans reminder_days, puis dispatche
    send_push_to_user pour chaque utilisateur concerné.
    """
    return _run(_schedule_reminders_impl())


async def _schedule_reminders_impl() -> dict[str, int]:
    import datetime

    from sqlalchemy import select

    from app.notifications.models import UserNotificationPrefs

    engine, factory = _make_session()
    now = datetime.datetime.utcnow()
    current_hour = now.hour
    day_abbr = now.strftime("%a")  # "Mon", "Tue", etc.

    scheduled = 0
    skipped = 0

    try:
        async with factory() as db:
            result = await db.execute(
                select(UserNotificationPrefs).where(
                    UserNotificationPrefs.workout_reminder_enabled.is_(True),
                    UserNotificationPrefs.reminder_hour == current_hour,
                    UserNotificationPrefs.is_deleted.is_(False),
                )
            )
            prefs_list = list(result.scalars().all())

        for prefs in prefs_list:
            try:
                reminder_days: list[str] = json.loads(prefs.reminder_days)
            except (json.JSONDecodeError, TypeError):
                reminder_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]

            if day_abbr not in reminder_days:
                skipped += 1
                continue

            send_push_to_user.apply_async(
                kwargs={
                    "user_id": str(prefs.user_id),
                    "title": "💪 C'est l'heure de s'entraîner !",
                    "body": "Ta séance t'attend. Continue sur ta lancée !",
                    "data": {"type": "workout_reminder"},
                },
                queue="notifications",
            )
            scheduled += 1

    finally:
        await engine.dispose()

    logger.info(
        "reminders_scheduled",
        scheduled=scheduled,
        skipped=skipped,
        hour_utc=current_hour,
        day=day_abbr,
    )
    return {"scheduled": scheduled, "skipped": skipped}
