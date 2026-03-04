"""Routes séances d'entraînement — sessions et séries."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.users.models import User
from app.workouts.schemas import (
    AddSetRequest,
    CompleteSessionRequest,
    PaginatedSessionsResponse,
    StartSessionRequest,
    UpdateSetRequest,
    WorkoutSessionResponse,
    WorkoutSetResponse,
)
from app.workouts.service import WorkoutService

router = APIRouter(prefix="/workouts", tags=["Workouts"])


# ==========================================================================
# Sessions
# ==========================================================================
@router.post(
    "/sessions",
    response_model=WorkoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new workout session",
)
async def start_session(
    payload: StartSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSessionResponse:
    session = await WorkoutService.start_session(db, current_user.id, payload)
    return WorkoutSessionResponse.model_validate(session)


@router.get(
    "/sessions",
    response_model=PaginatedSessionsResponse,
    summary="List past workout sessions",
)
async def list_sessions(
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedSessionsResponse:
    sessions, next_cursor, total = await WorkoutService.list_sessions(
        db, current_user.id, cursor, limit
    )
    return PaginatedSessionsResponse(
        data=[WorkoutSessionResponse.model_validate(s) for s in sessions],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
        total=total,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=WorkoutSessionResponse,
    summary="Get a workout session with all sets",
)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSessionResponse:
    session = await WorkoutService.get_session(db, session_id, current_user.id)
    return WorkoutSessionResponse.model_validate(session)


@router.put(
    "/sessions/{session_id}/complete",
    response_model=WorkoutSessionResponse,
    summary="Mark session as complete — triggers progression engine",
)
async def complete_session(
    session_id: uuid.UUID,
    payload: CompleteSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSessionResponse:
    session = await WorkoutService.complete_session(db, session_id, current_user.id, payload)
    return WorkoutSessionResponse.model_validate(session)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Soft delete a workout session",
)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await WorkoutService.soft_delete_session(db, session_id, current_user.id)


# ==========================================================================
# Séries
# ==========================================================================
@router.post(
    "/sessions/{session_id}/sets",
    response_model=WorkoutSetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a set to a session",
)
async def add_set(
    session_id: uuid.UUID,
    payload: AddSetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSetResponse:
    workout_set = await WorkoutService.add_set(db, session_id, current_user.id, payload)
    return WorkoutSetResponse.model_validate(workout_set)


@router.put(
    "/sessions/{session_id}/sets/{set_id}",
    response_model=WorkoutSetResponse,
    summary="Update a set",
)
async def update_set(
    session_id: uuid.UUID,
    set_id: uuid.UUID,
    payload: UpdateSetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSetResponse:
    workout_set = await WorkoutService.update_set(
        db, set_id, session_id, current_user.id, payload
    )
    return WorkoutSetResponse.model_validate(workout_set)


@router.delete(
    "/sessions/{session_id}/sets/{set_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Remove a set from a session",
)
async def remove_set(
    session_id: uuid.UUID,
    set_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await WorkoutService.remove_set(db, set_id, session_id, current_user.id)
