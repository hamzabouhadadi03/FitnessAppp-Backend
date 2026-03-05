"""Routes de progression — analyse, plateaux, réinitialisations, vue d'ensemble."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.progression.schemas import (
    AnalysisResponse,
    PlateauResponse,
    ProgressionLogResponse,
    ProgressionOverviewItem,
    ValidateResetRequest,
    ValidateResetResponse,
)
from app.progression.service import ProgressionService
from app.users.models import User

router = APIRouter(prefix="/progression", tags=["Progression"])


@router.get(
    "/logs",
    response_model=list[ProgressionLogResponse],
    summary="List all progression logs for the authenticated user",
)
async def list_progression_logs(
    program_day_exercise_id: uuid.UUID | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProgressionLogResponse]:
    """Retourne les journaux de progression de l'utilisateur.

    Filtrable par `program_day_exercise_id` pour l'historique d'un exercice spécifique.
    """
    from sqlalchemy import select
    from app.progression.models import ProgressionLog

    query = (
        select(ProgressionLog)
        .where(
            ProgressionLog.user_id == current_user.id,
            ProgressionLog.is_deleted.is_(False),
        )
        .order_by(ProgressionLog.created_at.desc())
        .limit(min(limit, 200))
    )
    if program_day_exercise_id:
        query = query.where(
            ProgressionLog.program_day_exercise_id == program_day_exercise_id
        )
    result = await db.execute(query)
    logs = list(result.scalars().all())
    return [ProgressionLogResponse.model_validate(log) for log in logs]


@router.get(
    "/analysis/{program_day_exercise_id}",
    response_model=AnalysisResponse,
    summary="Get progression history and current suggestion for an exercise",
)
async def get_analysis(
    program_day_exercise_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    data = await ProgressionService.get_analysis(db, program_day_exercise_id, current_user.id)
    return AnalysisResponse(
        program_day_exercise_id=data["program_day_exercise_id"],
        current_weight_kg=data["current_weight_kg"],
        logs=[ProgressionLogResponse.model_validate(log) for log in data["logs"]],
        latest_status=data["latest_status"],
        suggested_weight_kg=data["suggested_weight_kg"],
        consecutive_plateau_count=data["consecutive_plateau_count"],
    )


@router.post(
    "/reset/validate",
    response_model=ValidateResetResponse,
    summary="User validates a plateau reset suggestion",
)
async def validate_reset(
    payload: ValidateResetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidateResetResponse:
    from app.core.exceptions import BusinessLogicError

    if not payload.confirmed:
        raise BusinessLogicError("Reset must be explicitly confirmed (confirmed=true)")

    log = await ProgressionService.validate_reset(db, current_user.id, payload.program_day_exercise_id)
    return ValidateResetResponse(
        program_day_exercise_id=payload.program_day_exercise_id,
        new_weight_kg=log.suggested_weight_kg or 0.0,
        reset_percentage=log.reset_percentage or 6.0,
        message=log.notes or "Reset applied.",
    )


@router.get(
    "/plateaus",
    response_model=list[PlateauResponse],
    summary="List all current plateau detections for the user",
)
async def get_plateaus(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlateauResponse]:
    logs = await ProgressionService.get_plateaus(db, current_user.id)
    responses = []
    for log in logs:
        pde = log.program_day_exercise
        exercise_name = pde.exercise.name if pde and pde.exercise else "Unknown"
        current_w = log.suggested_weight_kg or 0.0
        reset_suggestion = round((current_w * (1 - (log.reset_percentage or 6.0) / 100)) * 2) / 2
        responses.append(
            PlateauResponse(
                program_day_exercise_id=log.program_day_exercise_id,
                exercise_name=exercise_name,
                current_weight_kg=current_w,
                suggested_reset_weight_kg=reset_suggestion,
                consecutive_plateau_count=log.consecutive_plateau_count,
                last_detected_at=log.created_at,
            )
        )
    return responses


@router.get(
    "/overview",
    response_model=list[ProgressionOverviewItem],
    summary="Global progression summary per exercise",
)
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProgressionOverviewItem]:
    from sqlalchemy import func, select
    from app.progression.models import ProgressionLog

    # Dernier journal par exercice pour cet utilisateur
    subq = (
        select(
            ProgressionLog.program_day_exercise_id,
            func.max(ProgressionLog.created_at).label("latest_at"),
        )
        .where(
            ProgressionLog.user_id == current_user.id,
            ProgressionLog.is_deleted.is_(False),
        )
        .group_by(ProgressionLog.program_day_exercise_id)
        .subquery()
    )

    result = await db.execute(
        select(ProgressionLog)
        .join(
            subq,
            (ProgressionLog.program_day_exercise_id == subq.c.program_day_exercise_id)
            & (ProgressionLog.created_at == subq.c.latest_at),
        )
        .where(ProgressionLog.user_id == current_user.id)
    )
    latest_logs = list(result.scalars().all())

    # Compter les sessions par exercice
    count_result = await db.execute(
        select(
            ProgressionLog.program_day_exercise_id,
            func.count(ProgressionLog.id).label("total"),
        )
        .where(
            ProgressionLog.user_id == current_user.id,
            ProgressionLog.is_deleted.is_(False),
        )
        .group_by(ProgressionLog.program_day_exercise_id)
    )
    session_counts = {row[0]: row[1] for row in count_result.all()}

    # Premier journal par exercice — récupéré pour calculer l'évolution du poids
    # (first_at par pde_id, puis jointure correcte sur program_day_exercise_id + created_at)
    first_subq = (
        select(
            ProgressionLog.program_day_exercise_id,
            func.min(ProgressionLog.created_at).label("first_at"),
        )
        .where(
            ProgressionLog.user_id == current_user.id,
            ProgressionLog.is_deleted.is_(False),
        )
        .group_by(ProgressionLog.program_day_exercise_id)
        .subquery()
    )

    first_result = await db.execute(
        select(ProgressionLog)
        .join(
            first_subq,
            (ProgressionLog.program_day_exercise_id == first_subq.c.program_day_exercise_id)
            & (ProgressionLog.created_at == first_subq.c.first_at),
        )
        .where(ProgressionLog.user_id == current_user.id)
    )
    first_logs = {log.program_day_exercise_id: log for log in first_result.scalars().all()}

    items = []
    for log in latest_logs:
        pde = log.program_day_exercise
        exercise_name = pde.exercise.name if pde and pde.exercise else "Unknown"
        current_w = log.suggested_weight_kg or 0.0
        # Évolution du poids depuis la 1ère session : current - first
        first_log = first_logs.get(log.program_day_exercise_id)
        first_w = first_log.suggested_weight_kg or 0.0 if first_log else current_w
        weight_change = round((current_w - first_w) * 2) / 2  # Arrondi au 0.5 kg
        items.append(
            ProgressionOverviewItem(
                program_day_exercise_id=log.program_day_exercise_id,
                exercise_name=exercise_name,
                current_weight_kg=current_w,
                status=log.status,
                total_sessions=session_counts.get(log.program_day_exercise_id, 0),
                weight_change_kg=weight_change,
            )
        )
    return items
