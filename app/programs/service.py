"""Service programmes — CRUD pour les programmes, les jours et les exercices dans les jours."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import verify_ownership
from app.core.exceptions import BusinessLogicError, NotFoundError
from app.core.logging import get_logger
from app.programs.models import Program, ProgramDay, ProgramDayExercise
from app.programs.schemas import (
    AddExerciseToDayRequest,
    CreateProgramDayRequest,
    CreateProgramRequest,
    ReorderExercisesRequest,
    UpdateDayExerciseRequest,
    UpdateProgramDayRequest,
    UpdateProgramRequest,
)

logger = get_logger(__name__)
_DEFAULT_PAGE_SIZE = 20


class ProgramService:
    # ------------------------------------------------------------------
    # Programmes
    # ------------------------------------------------------------------
    @staticmethod
    async def list_programs(
        db: AsyncSession,
        user_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = _DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Program], str | None, int]:
        base_q = select(Program).where(
            Program.user_id == user_id,
            Program.is_deleted.is_(False),
        )
        if cursor:
            try:
                cursor_ts, cursor_id = cursor.split("_")
                cursor_dt = datetime.fromisoformat(cursor_ts)
                base_q = base_q.where(
                    (Program.created_at < cursor_dt)
                    | ((Program.created_at == cursor_dt) & (Program.id < uuid.UUID(cursor_id)))
                )
            except (ValueError, AttributeError):
                pass

        count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
        total = count_result.scalar_one()

        base_q = base_q.order_by(Program.created_at.desc(), Program.id.desc()).limit(limit + 1)
        result = await db.execute(base_q)
        programs = list(result.scalars().all())

        next_cursor: str | None = None
        if len(programs) > limit:
            programs = programs[:limit]
            last = programs[-1]
            next_cursor = f"{last.created_at.isoformat()}_{last.id}"

        return programs, next_cursor, total

    @staticmethod
    async def get_program(
        db: AsyncSession,
        program_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Program:
        result = await db.execute(
            select(Program).where(
                Program.id == program_id,
                Program.is_deleted.is_(False),
            )
        )
        program = result.scalar_one_or_none()
        if not program:
            raise NotFoundError("Program")
        verify_ownership(program.user_id, user_id)
        return program

    @staticmethod
    async def create_program(
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: CreateProgramRequest,
    ) -> Program:
        program = Program(
            user_id=user_id,
            name=payload.name,
            split_type=payload.split_type,
            weeks_duration=payload.weeks_duration,
        )
        db.add(program)
        await db.flush()
        await db.refresh(program)
        logger.info("program_created")
        return program

    @staticmethod
    async def update_program(
        db: AsyncSession,
        program_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: UpdateProgramRequest,
    ) -> Program:
        program = await ProgramService.get_program(db, program_id, user_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(program, field, value)
        db.add(program)
        await db.flush()
        await db.refresh(program)
        return program

    @staticmethod
    async def soft_delete_program(
        db: AsyncSession,
        program_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        program = await ProgramService.get_program(db, program_id, user_id)
        program.is_deleted = True
        program.deleted_at = datetime.now(tz=timezone.utc)
        db.add(program)
        await db.flush()

    @staticmethod
    async def activate_program(
        db: AsyncSession,
        program_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Program:
        # Désactiver tous les autres programmes de cet utilisateur
        await db.execute(
            update(Program)
            .where(Program.user_id == user_id, Program.is_deleted.is_(False))
            .values(is_active=False)
        )
        program = await ProgramService.get_program(db, program_id, user_id)
        program.is_active = True
        db.add(program)
        await db.flush()
        await db.refresh(program)
        logger.info("program_activated")
        return program

    # ------------------------------------------------------------------
    # Jours de programme
    # ------------------------------------------------------------------
    @staticmethod
    async def get_day(
        db: AsyncSession,
        day_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProgramDay:
        result = await db.execute(
            select(ProgramDay).where(
                ProgramDay.id == day_id,
                ProgramDay.is_deleted.is_(False),
            )
        )
        day = result.scalar_one_or_none()
        if not day:
            raise NotFoundError("ProgramDay")
        verify_ownership(day.program.user_id, user_id)
        return day

    @staticmethod
    async def add_day(
        db: AsyncSession,
        program_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: CreateProgramDayRequest,
    ) -> ProgramDay:
        await ProgramService.get_program(db, program_id, user_id)
        day = ProgramDay(
            program_id=program_id,
            day_name=payload.day_name,
            day_order=payload.day_order,
        )
        db.add(day)
        await db.flush()
        await db.refresh(day)
        return day

    @staticmethod
    async def update_day(
        db: AsyncSession,
        day_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: UpdateProgramDayRequest,
    ) -> ProgramDay:
        day = await ProgramService.get_day(db, day_id, user_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(day, field, value)
        db.add(day)
        await db.flush()
        await db.refresh(day)
        return day

    @staticmethod
    async def remove_day(
        db: AsyncSession,
        day_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        day = await ProgramService.get_day(db, day_id, user_id)
        day.is_deleted = True
        day.deleted_at = datetime.now(tz=timezone.utc)
        db.add(day)
        await db.flush()

    # ------------------------------------------------------------------
    # Exercices des jours de programme
    # ------------------------------------------------------------------
    @staticmethod
    async def get_pde(
        db: AsyncSession,
        pde_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProgramDayExercise:
        result = await db.execute(
            select(ProgramDayExercise).where(
                ProgramDayExercise.id == pde_id,
                ProgramDayExercise.is_deleted.is_(False),
            )
        )
        pde = result.scalar_one_or_none()
        if not pde:
            raise NotFoundError("ProgramDayExercise")
        verify_ownership(pde.program_day.program.user_id, user_id)
        return pde

    @staticmethod
    async def add_exercise_to_day(
        db: AsyncSession,
        day_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: AddExerciseToDayRequest,
    ) -> ProgramDayExercise:
        await ProgramService.get_day(db, day_id, user_id)

        if payload.reps_min > payload.reps_max:
            raise BusinessLogicError("reps_min cannot be greater than reps_max")

        pde = ProgramDayExercise(
            program_day_id=day_id,
            exercise_id=payload.exercise_id,
            sets_target=payload.sets_target,
            reps_min=payload.reps_min,
            reps_max=payload.reps_max,
            order_in_day=payload.order_in_day,
        )
        db.add(pde)
        await db.flush()
        await db.refresh(pde)
        return pde

    @staticmethod
    async def update_day_exercise(
        db: AsyncSession,
        pde_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: UpdateDayExerciseRequest,
    ) -> ProgramDayExercise:
        pde = await ProgramService.get_pde(db, pde_id, user_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(pde, field, value)
        db.add(pde)
        await db.flush()
        await db.refresh(pde)
        return pde

    @staticmethod
    async def remove_day_exercise(
        db: AsyncSession,
        pde_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        pde = await ProgramService.get_pde(db, pde_id, user_id)
        pde.is_deleted = True
        pde.deleted_at = datetime.now(tz=timezone.utc)
        db.add(pde)
        await db.flush()

    @staticmethod
    async def reorder_exercises(
        db: AsyncSession,
        day_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ReorderExercisesRequest,
    ) -> list[ProgramDayExercise]:
        await ProgramService.get_day(db, day_id, user_id)

        result = await db.execute(
            select(ProgramDayExercise).where(
                ProgramDayExercise.program_day_id == day_id,
                ProgramDayExercise.is_deleted.is_(False),
            )
        )
        existing = {pde.id: pde for pde in result.scalars().all()}

        for order, pde_id in enumerate(payload.exercise_ids):
            if pde_id in existing:
                existing[pde_id].order_in_day = order
                db.add(existing[pde_id])

        await db.flush()
        return sorted(existing.values(), key=lambda x: x.order_in_day)
