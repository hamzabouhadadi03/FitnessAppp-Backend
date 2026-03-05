"""Configuration Celery pour FitProgress.

Broker  : Redis (même instance que le cache JWKS).
Workers : exécutent les tâches asynchrones (push notifications, etc.).
Beat    : planificateur de tâches périodiques (rappels d'entraînement).

Utilisation :
    # Lancer le worker
    celery -A app.core.celery_app worker --loglevel=info

    # Lancer le beat (planificateur)
    celery -A app.core.celery_app beat --loglevel=info --scheduler celery.beat:PersistentScheduler
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "fitprogress",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.notifications.tasks"],
)

celery_app.conf.update(
    # Sérialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Fiabilité
    task_track_started=True,
    task_acks_late=True,          # Acknowledge après exécution (pas avant)
    worker_prefetch_multiplier=1,  # Un message à la fois par worker
    # Expiration des résultats (24h)
    result_expires=86_400,
    # Planification Beat — rappels d'entraînement
    beat_schedule={
        "workout-reminders-hourly": {
            "task": "notifications.schedule_workout_reminders",
            "schedule": crontab(minute=0),  # Toutes les heures à H:00 UTC
            "options": {"queue": "notifications"},
        },
    },
    # Files de tâches
    task_default_queue="default",
    task_routes={
        "notifications.*": {"queue": "notifications"},
    },
)
