"""Schémas Pydantic du domaine utilisateur."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.users.models import SplitType, UserGoal, UserLevel


class UserProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    username: str
    goal: UserGoal | None
    level: UserLevel | None
    frequency: int | None
    preferred_split: SplitType | None
    is_active: bool
    is_onboarded: bool
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    goal: UserGoal | None = None
    level: UserLevel | None = None
    frequency: int | None = Field(None, ge=3, le=6)
    preferred_split: SplitType | None = None
    username: str | None = Field(None, min_length=3, max_length=50)


class OnboardingRequest(BaseModel):
    goal: UserGoal
    level: UserLevel
    frequency: int = Field(..., ge=3, le=6)
    preferred_split: SplitType


class OnboardingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    is_onboarded: bool
    goal: UserGoal
    level: UserLevel
    frequency: int
    preferred_split: SplitType
