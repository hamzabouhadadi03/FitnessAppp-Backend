"""Service de progression — fait le lien entre la base de données et le moteur pur."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessLogicError, NotFoundError
from app.core.logging import get_logger
from app.gamification.models import PersonalRecord
from app.progression.engine import (
    ExerciseSessionData,
    ProgressionResult,
    PreviousSessionData,
    RPELevel as EngineRPE,
    ProgressionStatus as EngineStatus,
    SetData,
    analyze_session,
    apply_validated_reset,
)
from app.progression.models import ProgressionLog, ProgressionStatus
from app.programs.models import ProgramDayExercise
from app.workouts.models import WorkoutSession, WorkoutSet

logger = get_logger(__name__)

_MAX_PREVIOUS_SESSIONS = 5


class ProgressionService:
    # ------------------------------------------------------------------
    # Appelé automatiquement lors de la finalisation d'une session d'entraînement
    # ------------------------------------------------------------------
    @staticmethod
    async def process_completed_session(
        db: AsyncSession,
        session: WorkoutSession,
        user_id: uuid.UUID,
    ) -> list[ProgressionLog]:
        """Lance le moteur de progression pour chaque exercice de la session terminée."""
        # Regrouper les séries par program_day_exercise_id
        sets_by_pde: dict[uuid.UUID, list[WorkoutSet]] = defaultdict(list)
        for ws in session.sets:
            if not ws.is_deleted:
                sets_by_pde[ws.program_day_exercise_id].append(ws)

        logs: list[ProgressionLog] = []

        for pde_id, sets in sets_by_pde.items():
            try:
                log = await ProgressionService._process_exercise(
                    db, session, user_id, pde_id, sets
                )
                if log:
                    logs.append(log)
            except Exception:
                logger.exception("progression_exercise_error", pde_id=str(pde_id))

        return logs

    @staticmethod
    async def _process_exercise(
        db: AsyncSession,
        session: WorkoutSession,
        user_id: uuid.UUID,
        pde_id: uuid.UUID,
        sets: list[WorkoutSet],
    ) -> ProgressionLog | None:
        # Charger la configuration ProgramDayExercise
        result = await db.execute(
            select(ProgramDayExercise).where(
                ProgramDayExercise.id == pde_id,
                ProgramDayExercise.is_deleted.is_(False),
            )
        )
        pde = result.scalar_one_or_none()
        if not pde:
            return None

        # Charger les journaux de progression précédents pour cet exercice (5 derniers)
        prev_logs_result = await db.execute(
            select(ProgressionLog)
            .where(
                ProgressionLog.user_id == user_id,
                ProgressionLog.program_day_exercise_id == pde_id,
                ProgressionLog.is_deleted.is_(False),
            )
            .order_by(ProgressionLog.created_at.desc())
            .limit(_MAX_PREVIOUS_SESSIONS)
        )
        prev_logs = list(prev_logs_result.scalars().all())

        # Charger le meilleur poids de tous les temps pour la détection de record personnel
        pr_result = await db.execute(
            select(PersonalRecord)
            .where(
                PersonalRecord.user_id == user_id,
                PersonalRecord.exercise_id == pde.exercise_id,
                PersonalRecord.is_deleted.is_(False),
            )
            .order_by(PersonalRecord.weight_kg.desc())
            .limit(1)
        )
        best_pr = pr_result.scalar_one_or_none()
        all_time_best = best_pr.weight_kg if best_pr else 0.0

        # Poids actuel = poids maximum utilisé dans les séries de travail
        working_sets = [s for s in sets if not s.is_warmup]
        current_weight = max((s.weight_kg for s in working_sets), default=0.0)

        # Construire les données d'entrée du moteur
        prev_sessions = []
        for prev_log in prev_logs:
            prev_sessions.append(
                PreviousSessionData(
                    session_id=prev_log.session_id,
                    avg_weight_kg=prev_log.suggested_weight_kg or current_weight,
                    all_sets_reached_upper_bound=(
                        prev_log.status == ProgressionStatus.PROGRESSING
                        and (prev_log.reset_percentage or 0) == 0
                        and (prev_log.suggested_weight_kg or 0) > current_weight
                    ),
                    status=EngineStatus(prev_log.status.value),
                )
            )

        engine_sets = [
            SetData(
                weight_kg=s.weight_kg,
                reps_done=s.reps_done,
                rpe=EngineRPE(s.rpe.value),
                is_warmup=s.is_warmup,
            )
            for s in sets
        ]

        # Reporter le compteur de plateaux depuis le dernier journal
        last_plateau_count = prev_logs[0].consecutive_plateau_count if prev_logs else 0

        data = ExerciseSessionData(
            program_day_exercise_id=pde_id,
            sets=engine_sets,
            reps_min_target=pde.reps_min,
            reps_max_target=pde.reps_max,
            previous_sessions=prev_sessions,
            current_weight_kg=current_weight,
            all_time_best_weight_kg=all_time_best,
        )

        # Ajuster l'entrée du compteur de plateaux (fonction auxiliaire du moteur)
        result_engine = _run_engine_with_plateau_count(data, last_plateau_count)

        # Persister le journal de progression
        log = ProgressionLog(
            user_id=user_id,
            program_day_exercise_id=pde_id,
            session_id=session.id,
            status=ProgressionStatus(result_engine.status.value),
            suggested_weight_kg=result_engine.suggested_weight_kg,
            reset_percentage=result_engine.reset_percentage if result_engine.reset_percentage > 0 else None,
            consecutive_plateau_count=result_engine.consecutive_plateau_count,
            notes=result_engine.message,
        )
        db.add(log)
        await db.flush()

        # Créer un enregistrement de record personnel si le moteur en a détecté un
        if result_engine.is_pr:
            await ProgressionService._record_pr(
                db, user_id, pde.exercise_id, sets, session.id
            )

        return log

    @staticmethod
    async def _record_pr(
        db: AsyncSession,
        user_id: uuid.UUID,
        exercise_id: uuid.UUID,
        sets: list[WorkoutSet],
        session_id: uuid.UUID,
    ) -> None:
        best_set = max(
            (s for s in sets if not s.is_warmup),
            key=lambda s: s.weight_kg,
            default=None,
        )
        if not best_set:
            return

        pr = PersonalRecord(
            user_id=user_id,
            exercise_id=exercise_id,
            weight_kg=best_set.weight_kg,
            reps=best_set.reps_done,
            achieved_at=datetime.now(tz=timezone.utc),
            session_id=session_id,
        )
        db.add(pr)
        await db.flush()
        logger.info("personal_record_saved", exercise_id=str(exercise_id))

    # ------------------------------------------------------------------
    # Méthode privée : vérifier que le PDE appartient bien à l'utilisateur
    # Empêche la fuite d'information sur les exercices d'autres utilisateurs
    # ------------------------------------------------------------------
    @staticmethod
    async def _verify_pde_ownership(
        db: AsyncSession,
        pde_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        from app.core.dependencies import verify_ownership
        result = await db.execute(
            select(ProgramDayExercise).where(
                ProgramDayExercise.id == pde_id,
                ProgramDayExercise.is_deleted.is_(False),
            )
        )
        pde = result.scalar_one_or_none()
        if not pde:
            raise NotFoundError("ProgramDayExercise")
        # Vérifier que le programme parent appartient bien à l'utilisateur
        verify_ownership(pde.program_day.program.user_id, user_id)

    # ------------------------------------------------------------------
    # Requêtes
    # ------------------------------------------------------------------
    @staticmethod
    async def get_analysis(
        db: AsyncSession,
        pde_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict:
        # Vérification de propriété avant tout accès aux données
        await ProgressionService._verify_pde_ownership(db, pde_id, user_id)
        logs_result = await db.execute(
            select(ProgressionLog)
            .where(
                ProgressionLog.program_day_exercise_id == pde_id,
                ProgressionLog.user_id == user_id,
                ProgressionLog.is_deleted.is_(False),
            )
            .order_by(ProgressionLog.created_at.desc())
            .limit(50)
        )
        logs = list(logs_result.scalars().all())

        latest = logs[0] if logs else None

        return {
            "program_day_exercise_id": pde_id,
            "current_weight_kg": latest.suggested_weight_kg if latest else None,
            "logs": logs,
            "latest_status": latest.status if latest else None,
            "suggested_weight_kg": latest.suggested_weight_kg if latest else None,
            "consecutive_plateau_count": latest.consecutive_plateau_count if latest else 0,
        }

    @staticmethod
    async def get_plateaus(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[ProgressionLog]:
        result = await db.execute(
            select(ProgressionLog)
            .where(
                ProgressionLog.user_id == user_id,
                ProgressionLog.status == ProgressionStatus.PLATEAU_DETECTED,
                ProgressionLog.is_deleted.is_(False),
            )
            .order_by(ProgressionLog.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def validate_reset(
        db: AsyncSession,
        user_id: uuid.UUID,
        pde_id: uuid.UUID,
    ) -> ProgressionLog:
        """L'utilisateur confirme la réinitialisation — l'appliquer et journaliser RESET_APPLIED."""
        # Vérification de propriété avant tout accès aux données
        await ProgressionService._verify_pde_ownership(db, pde_id, user_id)
        # Trouver le journal PLATEAU_DETECTED le plus récent pour cet exercice
        result = await db.execute(
            select(ProgressionLog)
            .where(
                ProgressionLog.user_id == user_id,
                ProgressionLog.program_day_exercise_id == pde_id,
                ProgressionLog.status == ProgressionStatus.PLATEAU_DETECTED,
                ProgressionLog.is_deleted.is_(False),
            )
            .order_by(ProgressionLog.created_at.desc())
            .limit(1)
        )
        plateau_log = result.scalar_one_or_none()
        if not plateau_log:
            raise NotFoundError("Plateau detection")

        current_weight = plateau_log.suggested_weight_kg or 0.0
        reset_pct = plateau_log.reset_percentage or 6.0

        # Le moteur applique la réinitialisation
        reset_result = apply_validated_reset(current_weight, reset_pct)

        # Persister le journal RESET_APPLIED
        reset_log = ProgressionLog(
            user_id=user_id,
            program_day_exercise_id=pde_id,
            session_id=plateau_log.session_id,
            status=ProgressionStatus.RESET_APPLIED,
            suggested_weight_kg=reset_result.suggested_weight_kg,
            reset_percentage=reset_result.reset_percentage,
            consecutive_plateau_count=0,
            notes=reset_result.message,
        )
        db.add(reset_log)
        await db.flush()
        await db.refresh(reset_log)
        logger.info("plateau_reset_applied", pde_id=str(pde_id))
        return reset_log


# ---------------------------------------------------------------------------
# Fonction auxiliaire : injecter le compteur de plateaux dans l'exécution du moteur
# ---------------------------------------------------------------------------
def _run_engine_with_plateau_count(
    data: ExerciseSessionData,
    last_plateau_count: int,
) -> ProgressionResult:
    """Lance le moteur en injectant le compteur de plateaux persisté depuis la base de données."""
    from app.progression import engine as eng

    # On remplace temporairement la fonction auxiliaire pour retourner le vrai compteur.
    # Cela garde le moteur pur tout en injectant l'état provenant de la base de données.
    original = eng._extract_plateau_count

    def _patched(prev: list[PreviousSessionData]) -> int:
        return last_plateau_count

    eng._extract_plateau_count = _patched  # type: ignore[assignment]
    try:
        result = analyze_session(data)
    finally:
        eng._extract_plateau_count = original  # type: ignore[assignment]

    return result
