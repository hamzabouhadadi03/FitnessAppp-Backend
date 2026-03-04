"""Service de gamification — statistiques, séries de jours, records personnels, score de progression."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gamification.models import PersonalRecord
from app.gamification.schemas import (
    ActivityHeatmapItem,
    GlobalStatsResponse,
    ProgressScoreResponse,
    StreakResponse,
)
from app.workouts.models import RPELevel, WorkoutSession, WorkoutSet


class GamificationService:
    # ------------------------------------------------------------------
    # Statistiques globales
    # ------------------------------------------------------------------
    @staticmethod
    async def get_global_stats(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> GlobalStatsResponse:
        # Comptage des sessions
        session_result = await db.execute(
            select(
                func.count(WorkoutSession.id).label("total"),
                func.count(WorkoutSession.completed_at).label("completed"),
                func.min(WorkoutSession.started_at).label("first"),
                func.max(WorkoutSession.started_at).label("last"),
            ).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.is_deleted.is_(False),
            )
        )
        session_row = session_result.one()

        # Volume total et nombre de séries
        volume_result = await db.execute(
            select(
                func.sum(WorkoutSet.weight_kg * WorkoutSet.reps_done).label("volume"),
                func.count(WorkoutSet.id).label("sets"),
            )
            .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSet.is_deleted.is_(False),
                WorkoutSession.is_deleted.is_(False),
                WorkoutSet.is_warmup.is_(False),
            )
        )
        volume_row = volume_result.one()

        # RPE le plus fréquent
        rpe_result = await db.execute(
            select(WorkoutSet.rpe, func.count(WorkoutSet.id).label("cnt"))
            .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSet.is_deleted.is_(False),
                WorkoutSet.is_warmup.is_(False),
            )
            .group_by(WorkoutSet.rpe)
            .order_by(func.count(WorkoutSet.id).desc())
            .limit(1)
        )
        rpe_row = rpe_result.one_or_none()

        return GlobalStatsResponse(
            total_sessions=session_row.total or 0,
            total_completed_sessions=session_row.completed or 0,
            total_volume_kg=float(volume_row.volume or 0),
            total_sets=volume_row.sets or 0,
            avg_rpe=rpe_row.rpe.value if rpe_row else None,
            most_trained_exercise=None,  # TODO: ajouter la jointure avec le nom de l'exercice
            first_session_date=session_row.first,
            last_session_date=session_row.last,
        )

    # ------------------------------------------------------------------
    # Série de jours consécutifs
    # ------------------------------------------------------------------
    @staticmethod
    async def get_streak(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> StreakResponse:
        # Récupérer toutes les dates des sessions terminées, triées par ordre décroissant
        result = await db.execute(
            select(WorkoutSession.completed_at)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.completed_at.isnot(None),
                WorkoutSession.is_deleted.is_(False),
            )
            .order_by(WorkoutSession.completed_at.desc())
        )
        dates = [row[0].date() for row in result.all() if row[0]]

        if not dates:
            return StreakResponse(current_streak_days=0, longest_streak_days=0, last_session_date=None)

        unique_dates = sorted(set(dates), reverse=True)
        today = datetime.now(tz=timezone.utc).date()

        # Série actuelle
        current = 0
        expected = today
        for d in unique_dates:
            if d == expected or d == expected - timedelta(days=1):
                current += 1
                expected = d - timedelta(days=1)
            else:
                break

        # Série la plus longue
        longest = 1
        run = 1
        for i in range(1, len(unique_dates)):
            if (unique_dates[i - 1] - unique_dates[i]).days == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1

        last_dt = result = await db.execute(
            select(WorkoutSession.completed_at)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.completed_at.isnot(None),
                WorkoutSession.is_deleted.is_(False),
            )
            .order_by(WorkoutSession.completed_at.desc())
            .limit(1)
        )
        last_row = last_dt.scalar_one_or_none()

        return StreakResponse(
            current_streak_days=current,
            longest_streak_days=longest,
            last_session_date=last_row,
        )

    # ------------------------------------------------------------------
    # Records personnels
    # ------------------------------------------------------------------
    @staticmethod
    async def get_personal_records(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[PersonalRecord]:
        result = await db.execute(
            select(PersonalRecord)
            .where(
                PersonalRecord.user_id == user_id,
                PersonalRecord.is_deleted.is_(False),
            )
            .order_by(PersonalRecord.achieved_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Score de progression (0-100)
    # ------------------------------------------------------------------
    @staticmethod
    async def get_progress_score(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> ProgressScoreResponse:
        """Score mensuel composite : charge (40%) + régularité (40%) + progression (20%)."""
        now = datetime.now(tz=timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_str = now.strftime("%Y-%m")

        # Régularité : sessions ce mois-ci par rapport à l'objectif
        session_count_result = await db.execute(
            select(func.count(WorkoutSession.id))
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.completed_at.isnot(None),
                WorkoutSession.started_at >= month_start,
                WorkoutSession.is_deleted.is_(False),
            )
        )
        sessions_this_month = session_count_result.scalar_one() or 0
        # Objectif : 4 sessions/semaine * 4 semaines = 16 (simplifié)
        consistency_score = min(100, int((sessions_this_month / 16) * 100))

        # Charge : volume total ce mois-ci par rapport au mois précédent
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        current_vol_result = await db.execute(
            select(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps_done))
            .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= month_start,
                WorkoutSet.is_deleted.is_(False),
                WorkoutSession.is_deleted.is_(False),
                WorkoutSet.is_warmup.is_(False),
            )
        )
        current_vol = float(current_vol_result.scalar_one() or 0)

        prev_vol_result = await db.execute(
            select(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps_done))
            .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= prev_month_start,
                WorkoutSession.started_at < month_start,
                WorkoutSet.is_deleted.is_(False),
                WorkoutSession.is_deleted.is_(False),
                WorkoutSet.is_warmup.is_(False),
            )
        )
        prev_vol = float(prev_vol_result.scalar_one() or 1)
        load_pct = (current_vol / prev_vol) * 100 if prev_vol > 0 else 0
        load_score = min(100, int(load_pct))

        # Progression : records personnels atteints ce mois-ci
        pr_result = await db.execute(
            select(func.count(PersonalRecord.id))
            .where(
                PersonalRecord.user_id == user_id,
                PersonalRecord.achieved_at >= month_start,
                PersonalRecord.is_deleted.is_(False),
            )
        )
        prs_this_month = pr_result.scalar_one() or 0
        progression_score = min(100, prs_this_month * 20)

        # Score composite (pondéré)
        score = int(load_score * 0.4 + consistency_score * 0.4 + progression_score * 0.2)

        return ProgressScoreResponse(
            score=min(100, score),
            load_score=load_score,
            consistency_score=consistency_score,
            progression_score=progression_score,
            month=month_str,
        )

    # ------------------------------------------------------------------
    # Carte thermique d'activité (12 dernières semaines)
    # ------------------------------------------------------------------
    @staticmethod
    async def get_activity_history(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[list[ActivityHeatmapItem]]:
        twelve_weeks_ago = datetime.now(tz=timezone.utc) - timedelta(weeks=12)

        result = await db.execute(
            select(
                func.date(WorkoutSession.started_at).label("session_date"),
                func.count(WorkoutSession.id).label("cnt"),
            )
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= twelve_weeks_ago,
                WorkoutSession.is_deleted.is_(False),
            )
            .group_by(func.date(WorkoutSession.started_at))
            .order_by(func.date(WorkoutSession.started_at))
        )
        rows = result.all()

        session_map: dict[date, int] = {r.session_date: r.cnt for r in rows}

        # Volume par jour
        vol_result = await db.execute(
            select(
                func.date(WorkoutSession.started_at).label("session_date"),
                func.sum(WorkoutSet.weight_kg * WorkoutSet.reps_done).label("volume"),
            )
            .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= twelve_weeks_ago,
                WorkoutSet.is_deleted.is_(False),
                WorkoutSession.is_deleted.is_(False),
            )
            .group_by(func.date(WorkoutSession.started_at))
        )
        vol_map: dict[date, float] = {r.session_date: float(r.volume or 0) for r in vol_result.all()}

        # Construire la grille de 12 semaines
        today = datetime.now(tz=timezone.utc).date()
        start = today - timedelta(weeks=12)
        current = start - timedelta(days=start.weekday())

        weeks: list[list[ActivityHeatmapItem]] = []
        while current <= today:
            week: list[ActivityHeatmapItem] = []
            for i in range(7):
                d = current + timedelta(days=i)
                week.append(
                    ActivityHeatmapItem(
                        date=d,
                        session_count=session_map.get(d, 0),
                        total_volume_kg=vol_map.get(d, 0.0),
                    )
                )
            weeks.append(week)
            current += timedelta(weeks=1)

        return weeks
