"""Routes de gamification — statistiques, séries de jours, records personnels, score de progression, historique d'activité."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.gamification.schemas import (
    ActivityHistoryResponse,
    GlobalStatsResponse,
    PersonalRecordResponse,
    ProgressScoreResponse,
    StreakResponse,
)
from app.gamification.service import GamificationService
from app.users.models import User

router = APIRouter(prefix="/gamification", tags=["Gamification"])


@router.get("/stats", response_model=GlobalStatsResponse, summary="Get global user stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlobalStatsResponse:
    return await GamificationService.get_global_stats(db, current_user.id)


@router.get("/streak", response_model=StreakResponse, summary="Get discipline streak")
async def get_streak(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreakResponse:
    return await GamificationService.get_streak(db, current_user.id)


@router.get(
    "/personal-records",
    response_model=list[PersonalRecordResponse],
    summary="Get all-time personal records per exercise",
)
async def get_personal_records(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PersonalRecordResponse]:
    prs = await GamificationService.get_personal_records(db, current_user.id)
    return [
        PersonalRecordResponse(
            id=pr.id,
            exercise_id=pr.exercise_id,
            exercise_name=pr.exercise.name if pr.exercise else "Unknown",
            weight_kg=pr.weight_kg,
            reps=pr.reps,
            achieved_at=pr.achieved_at,
            session_id=pr.session_id,
        )
        for pr in prs
    ]


@router.get(
    "/progress-score",
    response_model=ProgressScoreResponse,
    summary="Get monthly progression score (0-100)",
)
async def get_progress_score(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgressScoreResponse:
    return await GamificationService.get_progress_score(db, current_user.id)


@router.get(
    "/activity-history",
    response_model=ActivityHistoryResponse,
    summary="Get weekly activity heatmap data (last 12 weeks)",
)
async def get_activity_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityHistoryResponse:
    weeks = await GamificationService.get_activity_history(db, current_user.id)
    return ActivityHistoryResponse(weeks=weeks)
