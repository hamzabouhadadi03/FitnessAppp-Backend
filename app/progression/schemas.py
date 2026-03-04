"""Schémas Pydantic du module de progression."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.progression.models import ProgressionStatus


class ProgressionLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    program_day_exercise_id: uuid.UUID
    session_id: uuid.UUID
    status: ProgressionStatus
    suggested_weight_kg: float | None
    reset_percentage: float | None
    consecutive_plateau_count: int
    notes: str | None
    created_at: datetime


class AnalysisResponse(BaseModel):
    """Historique complet de progression et suggestion actuelle pour un exercice."""

    program_day_exercise_id: uuid.UUID
    current_weight_kg: float | None
    logs: list[ProgressionLogResponse]
    latest_status: ProgressionStatus | None
    suggested_weight_kg: float | None
    consecutive_plateau_count: int


class ValidateResetRequest(BaseModel):
    """L'utilisateur valide une suggestion de réinitialisation suite à un plateau."""

    program_day_exercise_id: uuid.UUID
    confirmed: bool = Field(..., description="Must be true to apply reset")


class ValidateResetResponse(BaseModel):
    program_day_exercise_id: uuid.UUID
    new_weight_kg: float
    reset_percentage: float
    message: str


class PlateauResponse(BaseModel):
    program_day_exercise_id: uuid.UUID
    exercise_name: str
    current_weight_kg: float
    suggested_reset_weight_kg: float
    consecutive_plateau_count: int
    last_detected_at: datetime


class ProgressionOverviewItem(BaseModel):
    program_day_exercise_id: uuid.UUID
    exercise_name: str
    current_weight_kg: float | None
    status: ProgressionStatus | None
    total_sessions: int
    weight_change_kg: float
