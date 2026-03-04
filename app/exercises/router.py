"""Routes de la bibliothèque d'exercices."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.exercises.models import ExerciseCategory
from app.exercises.schemas import (
    CreateExerciseRequest,
    ExerciseResponse,
    PaginatedExercisesResponse,
    UpdateExerciseRequest,
)
from app.exercises.service import ExerciseService
from app.users.models import User

router = APIRouter(prefix="/exercises", tags=["Exercises"])


@router.get("/", response_model=PaginatedExercisesResponse, summary="List exercises")
async def list_exercises(
    category: ExerciseCategory | None = Query(None),
    muscle_group: str | None = Query(None, max_length=100),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedExercisesResponse:
    exercises, next_cursor, total = await ExerciseService.list_exercises(
        db, current_user.id, category, muscle_group, cursor, limit
    )
    return PaginatedExercisesResponse(
        data=[ExerciseResponse.model_validate(e) for e in exercises],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
        total=total,
    )


@router.get("/{exercise_id}", response_model=ExerciseResponse, summary="Get exercise by ID")
async def get_exercise(
    exercise_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExerciseResponse:
    exercise = await ExerciseService.get_by_id(db, exercise_id, current_user.id)
    return ExerciseResponse.model_validate(exercise)


@router.post(
    "/",
    response_model=ExerciseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom exercise",
)
async def create_exercise(
    payload: CreateExerciseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExerciseResponse:
    exercise = await ExerciseService.create_custom(db, current_user.id, payload)
    return ExerciseResponse.model_validate(exercise)


@router.put("/{exercise_id}", response_model=ExerciseResponse, summary="Update custom exercise")
async def update_exercise(
    exercise_id: uuid.UUID,
    payload: UpdateExerciseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExerciseResponse:
    exercise = await ExerciseService.update_custom(db, exercise_id, current_user.id, payload)
    return ExerciseResponse.model_validate(exercise)


@router.delete(
    "/{exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Soft delete custom exercise",
)
async def delete_exercise(
    exercise_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ExerciseService.soft_delete(db, exercise_id, current_user.id)
