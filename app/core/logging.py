"""Configuration de la journalisation JSON structurée avec structlog.

SÉCURITÉ : Ne jamais journaliser les mots de passe, tokens, corps complets de requêtes ni les données personnelles (PII).
Journalisé : request_id, user_id haché, endpoint, status_code, duration_ms.
"""
from __future__ import annotations

import hashlib
import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import get_settings


def _hash_user_id(user_id: str | None) -> str | None:
    """Hache le user_id avec SHA-256 avant journalisation — ne jamais journaliser les identifiants bruts."""
    if user_id is None:
        return None
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def _sanitize_event(
    logger: Any, method: str, event_dict: EventDict
) -> EventDict:
    """Supprime les champs sensibles des événements de log avant leur émission."""
    sensitive_keys = {
        "password", "token", "access_token", "refresh_token",
        "authorization", "secret", "api_key", "private_key",
        "jwt", "bearer", "credential",
    }
    for key in list(event_dict.keys()):
        if key.lower() in sensitive_keys:
            event_dict[key] = "[REDACTED]"
    # Hache le user_id s'il est présent sous forme brute
    if "user_id" in event_dict and isinstance(event_dict["user_id"], str):
        event_dict["user_id_hash"] = _hash_user_id(event_dict.pop("user_id"))
    return event_dict


def configure_logging() -> None:
    """Configure structlog pour la sortie JSON structurée."""
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _sanitize_event,
    ]

    if settings.is_production:
        # Sortie JSON pour les agrégateurs de logs en production (Datadog, CloudWatch, etc.)
        processors: list[Processor] = shared_processors + [
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Sortie console lisible pour le développement
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Configure la journalisation stdlib pour passer par structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(log_level)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Retourne un logger structlog lié."""
    return structlog.get_logger(name)
