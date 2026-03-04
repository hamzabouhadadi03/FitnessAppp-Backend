"""Service séances d'entraînement — gestion des sessions et des séries, déclenche le moteur de progression."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import verify_ownership
from app.core.exceptions import BusinessLogicError, NotFoundError
from app.core.logging import get_logger
from app.workouts.models import WorkoutSession, WorkoutSet
from app.workouts.schemas import (
    AddSetRequest,
    CompleteSessionRequest,
    StartSessionRequest,
    UpdateSetRequest,
)

logger = get_logger(__name__)
_DEFAULT_PAGE_SIZE = 20


class WorkoutService:
    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    @staticmethod
    async def list_sessions(
        db: AsyncSession,
        user_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = _DEFAULT_PAGE_SIZE,
    ) -> tuple[list[WorkoutSession], str | None, int]:
        base_q = select(WorkoutSession).where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.is_deleted.is_(False),
        )

        if cursor:
            try:
                cursor_ts, cursor_id = cursor.split("_")
                cursor_dt = datetime.fromisoformat(cursor_ts)
                base_q = base_q.where(
                    (WorkoutSession.started_at < cursor_dt)
                    | (
                        (WorkoutSession.started_at == cursor_dt)
                        & (WorkoutSession.id < uuid.UUID(cursor_id))
                    )
                )
            except (ValueError, AttributeError):
                pass

        count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
        total = count_result.scalar_one()

        base_q = (
            base_q.order_by(WorkoutSession.started_at.desc(), WorkoutSession.id.desc())
            .limit(limit + 1)
        )
        result = await db.execute(base_q)
        sessions = list(result.scalars().all())

        next_cursor: str | None = None
        if len(sessions) > limit:
            sessions = sessions[:limit]
            last = sessions[-1]
            next_cursor = f"{last.started_at.isoformat()}_{last.id}"

        return sessions, next_cursor, total

    @staticmethod
    async def get_session(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkoutSession:
        result = await db.execute(
            select(WorkoutSession).where(
                WorkoutSession.id == session_id,
                WorkoutSession.is_deleted.is_(False),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("WorkoutSession")
        verify_ownership(session.user_id, user_id)
        return session

    @staticmethod
    async def start_session(
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: StartSessionRequest,
    ) -> WorkoutSession:
        started_at = payload.started_at or datetime.now(tz=timezone.utc)
        session = WorkoutSession(
            user_id=user_id,
            program_day_id=payload.program_day_id,
            started_at=started_at,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        logger.info("workout_session_started")
        return session

    @staticmethod
    async def complete_session(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: CompleteSessionRequest,
    ) -> WorkoutSession:
        session = await WorkoutService.get_session(db, session_id, user_id)

        if session.completed_at is not None:
            raise BusinessLogicError("Session already completed")

        session.completed_at = datetime.now(tz=timezone.utc)
        session.notes = payload.notes
        session.session_rpe_overall = payload.session_rpe_overall
        db.add(session)
        await db.flush()
        await db.refresh(session)

        # Déclencher le moteur de progression de manière asynchrone
        await WorkoutService._run_progression_engine(db, session, user_id)

        logger.info("workout_session_completed")
        return session

    @staticmethod
    async def _run_progression_engine(
        db: AsyncSession,
        session: WorkoutSession,
        user_id: uuid.UUID,
    ) -> None:
        """Déclenche le moteur de progression pour tous les exercices de cette session."""
        # Import différé pour éviter les dépendances circulaires
        from app.progression.service import ProgressionService

        try:
            await ProgressionService.process_completed_session(db, session, user_id)
        except Exception:
            # Ne pas laisser l'échec du moteur de progression affecter la finalisation de la session
            logger.exception("progression_engine_error_during_session_complete")

    @staticmethod
    async def soft_delete_session(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        session = await WorkoutService.get_session(db, session_id, user_id)
        session.is_deleted = True
        session.deleted_at = datetime.now(tz=timezone.utc)
        db.add(session)
        await db.flush()

    # ------------------------------------------------------------------
    # Séries
    # ------------------------------------------------------------------
    @staticmethod
    async def add_set(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: AddSetRequest,
    ) -> WorkoutSet:
        session = await WorkoutService.get_session(db, session_id, user_id)
        if session.completed_at is not None:
            raise BusinessLogicError("Cannot add sets to a completed session")

        workout_set = WorkoutSet(
            session_id=session_id,
            program_day_exercise_id=payload.program_day_exercise_id,
            set_number=payload.set_number,
            weight_kg=payload.weight_kg,
            reps_done=payload.reps_done,
            rpe=payload.rpe,
            is_warmup=payload.is_warmup,
        )
        db.add(workout_set)
        await db.flush()
        await db.refresh(workout_set)
        return workout_set

    @staticmethod
    async def get_set(
        db: AsyncSession,
        set_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkoutSet:
        # Vérifier d'abord la propriété de la session
        await WorkoutService.get_session(db, session_id, user_id)

        result = await db.execute(
            select(WorkoutSet).where(
                WorkoutSet.id == set_id,
                WorkoutSet.session_id == session_id,
                WorkoutSet.is_deleted.is_(False),
            )
        )
        workout_set = result.scalar_one_or_none()
        if not workout_set:
            raise NotFoundError("WorkoutSet")
        return workout_set

    @staticmethod
    async def update_set(
        db: AsyncSession,
        set_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: UpdateSetRequest,
    ) -> WorkoutSet:
        session = await WorkoutService.get_session(db, session_id, user_id)
        if session.completed_at is not None:
            raise BusinessLogicError("Cannot update sets in a completed session")

        workout_set = await WorkoutService.get_set(db, set_id, session_id, user_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(workout_set, field, value)
        db.add(workout_set)
        await db.flush()
        await db.refresh(workout_set)
        return workout_set

    @staticmethod
    async def remove_set(
        db: AsyncSession,
        set_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        session = await WorkoutService.get_session(db, session_id, user_id)
        if session.completed_at is not None:
            raise BusinessLogicError("Cannot remove sets from a completed session")

        workout_set = await WorkoutService.get_set(db, set_id, session_id, user_id)
        workout_set.is_deleted = True
        workout_set.deleted_at = datetime.now(tz=timezone.utc)
        db.add(workout_set)
        await db.flush()
