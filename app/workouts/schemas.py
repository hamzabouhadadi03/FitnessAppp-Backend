"""Schémas Pydantic du module séances d'entraînement."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.workouts.models import RPELevel


# ---------------------------------------------------------------------------
# Schémas WorkoutSet
# ---------------------------------------------------------------------------
class WorkoutSetResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    session_id: uuid.UUID
    program_day_exercise_id: uuid.UUID
    set_number: int
    weight_kg: float
    reps_done: int
    rpe: RPELevel
    is_warmup: bool
    created_at: datetime


class AddSetRequest(BaseModel):
    program_day_exercise_id: uuid.UUID
    set_number: int = Field(..., ge=1, le=50)
    weight_kg: float = Field(..., ge=0.0, le=1000.0)
    reps_done: int = Field(..., ge=1, le=200)
    rpe: RPELevel
    is_warmup: bool = False


class UpdateSetRequest(BaseModel):
    weight_kg: float | None = Field(None, ge=0.0, le=1000.0)
    reps_done: int | None = Field(None, ge=1, le=200)
    rpe: RPELevel | None = None
    is_warmup: bool | None = None


# ---------------------------------------------------------------------------
# Schémas WorkoutSession
# ---------------------------------------------------------------------------
class WorkoutSessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    program_day_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    notes: str | None
    session_rpe_overall: RPELevel | None
    sets: list[WorkoutSetResponse] = []
    created_at: datetime


class StartSessionRequest(BaseModel):
    program_day_id: uuid.UUID
    started_at: datetime | None = None


class CompleteSessionRequest(BaseModel):
    notes: str | None = Field(None, max_length=2000)
    session_rpe_overall: RPELevel | None = None


class PaginatedSessionsResponse(BaseModel):
    data: list[WorkoutSessionResponse]
    next_cursor: str | None
    has_more: bool
    total: int
