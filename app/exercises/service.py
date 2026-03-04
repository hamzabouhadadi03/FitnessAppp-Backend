"""Service d'exercices — gère la bibliothèque d'exercices (globale + personnalisée par utilisateur)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.exercises.models import Exercise, ExerciseCategory
from app.exercises.schemas import CreateExerciseRequest, UpdateExerciseRequest

logger = get_logger(__name__)

_DEFAULT_PAGE_SIZE = 50


class ExerciseService:
    @staticmethod
    async def list_exercises(
        db: AsyncSession,
        user_id: uuid.UUID,
        category: ExerciseCategory | None = None,
        muscle_group: str | None = None,
        cursor: str | None = None,
        limit: int = _DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Exercise], str | None, int]:
        """Retourne les exercices visibles par cet utilisateur (bibliothèque + ses exercices personnalisés)."""
        base_query = select(Exercise).where(
            Exercise.is_deleted.is_(False),
        ).where(
            # Exercices de la bibliothèque (non personnalisés) OU exercices créés par cet utilisateur
            (Exercise.is_custom.is_(False)) | (Exercise.created_by_user_id == user_id)
        )

        if category:
            base_query = base_query.where(Exercise.category == category)
        if muscle_group:
            base_query = base_query.where(Exercise.muscle_group.ilike(f"%{muscle_group}%"))

        # Pagination par curseur basée sur created_at + id
        if cursor:
            try:
                cursor_ts, cursor_id = cursor.split("_")
                cursor_dt = datetime.fromisoformat(cursor_ts)
                base_query = base_query.where(
                    (Exercise.created_at < cursor_dt)
                    | ((Exercise.created_at == cursor_dt) & (Exercise.id < uuid.UUID(cursor_id)))
                )
            except (ValueError, AttributeError):
                pass  # Curseur invalide — recommencer depuis le début

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        base_query = base_query.order_by(Exercise.created_at.desc(), Exercise.id.desc())
        base_query = base_query.limit(limit + 1)

        result = await db.execute(base_query)
        exercises = list(result.scalars().all())

        next_cursor: str | None = None
        if len(exercises) > limit:
            exercises = exercises[:limit]
            last = exercises[-1]
            next_cursor = f"{last.created_at.isoformat()}_{last.id}"

        return exercises, next_cursor, total

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        exercise_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Exercise:
        result = await db.execute(
            select(Exercise).where(
                Exercise.id == exercise_id,
                Exercise.is_deleted.is_(False),
                (Exercise.is_custom.is_(False)) | (Exercise.created_by_user_id == user_id),
            )
        )
        exercise = result.scalar_one_or_none()
        if not exercise:
            raise NotFoundError("Exercise")
        return exercise

    @staticmethod
    async def create_custom(
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: CreateExerciseRequest,
    ) -> Exercise:
        exercise = Exercise(
            name=payload.name,
            category=payload.category,
            muscle_group=payload.muscle_group,
            description=payload.description,
            is_custom=True,
            created_by_user_id=user_id,
        )
        db.add(exercise)
        await db.flush()
        await db.refresh(exercise)
        logger.info("custom_exercise_created", user_id=str(user_id))
        return exercise

    @staticmethod
    async def update_custom(
        db: AsyncSession,
        exercise_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: UpdateExerciseRequest,
    ) -> Exercise:
        exercise = await ExerciseService.get_by_id(db, exercise_id, user_id)

        if not exercise.is_custom or exercise.created_by_user_id != user_id:
            raise ForbiddenError()

        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(exercise, field, value)

        db.add(exercise)
        await db.flush()
        await db.refresh(exercise)
        return exercise

    @staticmethod
    async def soft_delete(
        db: AsyncSession,
        exercise_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        exercise = await ExerciseService.get_by_id(db, exercise_id, user_id)

        if not exercise.is_custom or exercise.created_by_user_id != user_id:
            raise ForbiddenError()

        exercise.is_deleted = True
        exercise.deleted_at = datetime.now(tz=timezone.utc)
        db.add(exercise)
        await db.flush()
        logger.info("exercise_soft_deleted", exercise_id=str(exercise_id))
