"""Schémas Pydantic du module de gamification."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class PersonalRecordResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    exercise_id: uuid.UUID
    exercise_name: str
    weight_kg: float
    reps: int
    achieved_at: datetime
    session_id: uuid.UUID | None


class GlobalStatsResponse(BaseModel):
    total_sessions: int
    total_completed_sessions: int
    total_volume_kg: float
    total_sets: int
    avg_rpe: str | None
    most_trained_exercise: str | None
    first_session_date: datetime | None
    last_session_date: datetime | None


class StreakResponse(BaseModel):
    current_streak_days: int
    longest_streak_days: int
    last_session_date: datetime | None


class ProgressScoreResponse(BaseModel):
    score: int  # 0-100
    load_score: int
    consistency_score: int
    progression_score: int
    month: str  # AAAA-MM


class ActivityHeatmapItem(BaseModel):
    date: date
    session_count: int
    total_volume_kg: float


class ActivityHistoryResponse(BaseModel):
    weeks: list[list[ActivityHeatmapItem]]
