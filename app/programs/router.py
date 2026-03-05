"""Routes programmes — CRUD complet pour les programmes, les jours et les exercices dans les jours."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.programs.schemas import (
    AddExerciseToDayRequest,
    CreateProgramDayRequest,
    CreateProgramRequest,
    PaginatedProgramsResponse,
    ProgramDayExerciseResponse,
    ProgramDayResponse,
    ProgramResponse,
    ReorderExercisesRequest,
    UpdateDayExerciseRequest,
    UpdateProgramDayRequest,
    UpdateProgramRequest,
)
from app.programs.service import ProgramService
from app.users.models import User

router = APIRouter(prefix="/programs", tags=["Programs"])


# ==========================================================================
# Programmes
# ==========================================================================
@router.get("/", response_model=PaginatedProgramsResponse)
async def list_programs(
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedProgramsResponse:
    programs, next_cursor, total = await ProgramService.list_programs(
        db, current_user.id, cursor, limit
    )
    return PaginatedProgramsResponse(
        data=[ProgramResponse.model_validate(p) for p in programs],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
        total=total,
    )


@router.post("/", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(
    payload: CreateProgramRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramResponse:
    program = await ProgramService.create_program(db, current_user.id, payload)
    return ProgramResponse.model_validate(program)


@router.get("/{program_id}", response_model=ProgramResponse)
async def get_program(
    program_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramResponse:
    program = await ProgramService.get_program(db, program_id, current_user.id)
    return ProgramResponse.model_validate(program)


@router.put("/{program_id}", response_model=ProgramResponse)
async def update_program(
    program_id: uuid.UUID,
    payload: UpdateProgramRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramResponse:
    program = await ProgramService.update_program(db, program_id, current_user.id, payload)
    return ProgramResponse.model_validate(program)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_program(
    program_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ProgramService.soft_delete_program(db, program_id, current_user.id)


@router.post("/{program_id}/activate", response_model=ProgramResponse)
async def activate_program(
    program_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramResponse:
    program = await ProgramService.activate_program(db, program_id, current_user.id)
    return ProgramResponse.model_validate(program)


# ==========================================================================
# Jours de programme
# ==========================================================================
@router.get("/{program_id}/days", response_model=list[ProgramDayResponse])
async def list_days(
    program_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProgramDayResponse]:
    program = await ProgramService.get_program(db, program_id, current_user.id)
    return [ProgramDayResponse.model_validate(d) for d in program.days if not d.is_deleted]


@router.post("/{program_id}/days", response_model=ProgramDayResponse, status_code=status.HTTP_201_CREATED)
async def add_day(
    program_id: uuid.UUID,
    payload: CreateProgramDayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramDayResponse:
    day = await ProgramService.add_day(db, program_id, current_user.id, payload)
    return ProgramDayResponse.model_validate(day)


@router.get("/{program_id}/days/{day_id}", response_model=ProgramDayResponse)
async def get_day(
    program_id: uuid.UUID,
    day_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramDayResponse:
    day = await ProgramService.get_day(db, day_id, current_user.id)
    return ProgramDayResponse.model_validate(day)


@router.put("/{program_id}/days/{day_id}", response_model=ProgramDayResponse)
async def update_day(
    program_id: uuid.UUID,
    day_id: uuid.UUID,
    payload: UpdateProgramDayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramDayResponse:
    day = await ProgramService.update_day(db, day_id, current_user.id, payload)
    return ProgramDayResponse.model_validate(day)


@router.delete("/{program_id}/days/{day_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_day(
    program_id: uuid.UUID,
    day_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ProgramService.remove_day(db, day_id, current_user.id)


# ==========================================================================
# Exercices des jours de programme
# ==========================================================================
@router.get(
    "/{program_id}/days/{day_id}/exercises",
    response_model=list[ProgramDayExerciseResponse],
)
async def list_day_exercises(
    program_id: uuid.UUID,
    day_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProgramDayExerciseResponse]:
    day = await ProgramService.get_day(db, day_id, current_user.id)
    return [ProgramDayExerciseResponse.model_validate(e) for e in day.exercises if not e.is_deleted]


@router.post(
    "/{program_id}/days/{day_id}/exercises",
    response_model=ProgramDayExerciseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_exercise_to_day(
    program_id: uuid.UUID,
    day_id: uuid.UUID,
    payload: AddExerciseToDayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramDayExerciseResponse:
    pde = await ProgramService.add_exercise_to_day(db, day_id, current_user.id, payload)
    return ProgramDayExerciseResponse.model_validate(pde)


@router.put(
    "/{program_id}/days/{day_id}/exercises/{pde_id}",
    response_model=ProgramDayExerciseResponse,
)
async def update_day_exercise(
    program_id: uuid.UUID,
    day_id: uuid.UUID,
    pde_id: uuid.UUID,
    payload: UpdateDayExerciseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgramDayExerciseResponse:
    pde = await ProgramService.update_day_exercise(db, pde_id, current_user.id, payload)
    return ProgramDayExerciseResponse.model_validate(pde)


@router.delete(
    "/{program_id}/days/{day_id}/exercises/{pde_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def remove_day_exercise(
    program_id: uuid.UUID,
    day_id: uuid.UUID,
    pde_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ProgramService.remove_day_exercise(db, pde_id, current_user.id)


@router.post(
    "/{program_id}/days/{day_id}/exercises/reorder",
    response_model=list[ProgramDayExerciseResponse],
)
async def reorder_day_exercises(
    program_id: uuid.UUID,
    day_id: uuid.UUID,
    payload: ReorderExercisesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProgramDayExerciseResponse]:
    pdes = await ProgramService.reorder_exercises(db, day_id, current_user.id, payload)
    return [ProgramDayExerciseResponse.model_validate(p) for p in pdes]
