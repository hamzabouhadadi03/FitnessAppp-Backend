"""Schémas Pydantic du module d'exercices."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.exercises.models import ExerciseCategory


class ExerciseResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    category: ExerciseCategory
    muscle_group: str
    description: str
    is_custom: bool
    created_by_user_id: uuid.UUID | None
    created_at: datetime


class CreateExerciseRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    category: ExerciseCategory
    muscle_group: str = Field(..., min_length=2, max_length=100)
    description: str = Field("", max_length=1000)


class UpdateExerciseRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    category: ExerciseCategory | None = None
    muscle_group: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=1000)


class PaginatedExercisesResponse(BaseModel):
    data: list[ExerciseResponse]
    next_cursor: str | None
    has_more: bool
    total: int
