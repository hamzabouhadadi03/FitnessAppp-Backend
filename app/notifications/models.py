"""Modèles de notification — tokens de device et préférences utilisateur."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class Platform(str, enum.Enum):
    IOS = "IOS"
    ANDROID = "ANDROID"


class DeviceToken(BaseModel):
    """Token de push notification d'un appareil (APNs ou FCM)."""

    __tablename__ = "device_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True, index=True
    )
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform_type"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )
    app_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relations
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[user_id], lazy="selectin"
    )


class UserNotificationPrefs(BaseModel):
    """Préférences de notification par utilisateur."""

    __tablename__ = "user_notification_prefs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    workout_reminder_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    # Heure de rappel UTC (0–23). Ex: 9 = 9h00 UTC
    reminder_hour: Mapped[int] = mapped_column(
        Integer, default=9, nullable=False, server_default="9"
    )
    # JSON array de jours : ["Mon","Tue","Wed","Thu","Fri"]
    reminder_days: Mapped[str] = mapped_column(
        Text,
        default='["Mon","Tue","Wed","Thu","Fri"]',
        nullable=False,
        server_default="""'["Mon","Tue","Wed","Thu","Fri"]'""",
    )

    # Relations
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[user_id], lazy="selectin"
    )
