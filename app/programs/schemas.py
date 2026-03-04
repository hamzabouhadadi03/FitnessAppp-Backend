"""Schémas Pydantic du module programmes."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.users.models import SplitType


# ---------------------------------------------------------------------------
# Schémas ProgramDayExercise
# ---------------------------------------------------------------------------
class ProgramDayExerciseResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    program_day_id: uuid.UUID
    exercise_id: uuid.UUID
    sets_target: int
    reps_min: int
    reps_max: int
    order_in_day: int


class AddExerciseToDayRequest(BaseModel):
    exercise_id: uuid.UUID
    sets_target: int = Field(3, ge=1, le=20)
    reps_min: int = Field(8, ge=1, le=100)
    reps_max: int = Field(12, ge=1, le=100)
    order_in_day: int = Field(0, ge=0)


class UpdateDayExerciseRequest(BaseModel):
    sets_target: int | None = Field(None, ge=1, le=20)
    reps_min: int | None = Field(None, ge=1, le=100)
    reps_max: int | None = Field(None, ge=1, le=100)
    order_in_day: int | None = Field(None, ge=0)


class ReorderExercisesRequest(BaseModel):
    exercise_ids: list[uuid.UUID] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Schémas ProgramDay
# ---------------------------------------------------------------------------
class ProgramDayResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    program_id: uuid.UUID
    day_name: str
    day_order: int
    exercises: list[ProgramDayExerciseResponse] = []


class CreateProgramDayRequest(BaseModel):
    day_name: str = Field(..., min_length=2, max_length=100)
    day_order: int = Field(0, ge=0)


class UpdateProgramDayRequest(BaseModel):
    day_name: str | None = Field(None, min_length=2, max_length=100)
    day_order: int | None = Field(None, ge=0)


# ---------------------------------------------------------------------------
# Schémas Program
# ---------------------------------------------------------------------------
class ProgramResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    split_type: SplitType
    is_active: bool
    weeks_duration: int | None
    created_at: datetime
    days: list[ProgramDayResponse] = []


class CreateProgramRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    split_type: SplitType
    weeks_duration: int | None = Field(None, ge=1, le=52)


class UpdateProgramRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    split_type: SplitType | None = None
    weeks_duration: int | None = Field(None, ge=1, le=52)


class PaginatedProgramsResponse(BaseModel):
    data: list[ProgramResponse]
    next_cursor: str | None
    has_more: bool
    total: int
