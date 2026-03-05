"""Schémas Pydantic pour les notifications push."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.notifications.models import Platform


class RegisterDeviceTokenRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=500, description="APNs or FCM device token")
    platform: Platform
    app_version: str | None = Field(None, max_length=20, description="e.g. '1.0.0'")


class DeviceTokenResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    token: str
    platform: Platform
    is_active: bool
    app_version: str | None
    created_at: datetime


class NotificationPrefsRequest(BaseModel):
    workout_reminder_enabled: bool
    reminder_hour: Annotated[int, Field(ge=0, le=23, description="Hour in UTC (0-23)")]
    reminder_days: list[str] = Field(
        default=["Mon", "Tue", "Wed", "Thu", "Fri"],
        description="Day abbreviations: Mon Tue Wed Thu Fri Sat Sun",
        min_length=0,
        max_length=7,
    )


class NotificationPrefsResponse(BaseModel):
    workout_reminder_enabled: bool
    reminder_hour: int
    reminder_days: list[str]


class SendTestPushRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
