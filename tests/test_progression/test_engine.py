"""Unit tests for the progression engine — pure algorithm, no I/O.

All tests are fully deterministic. No DB, no network.
"""
from __future__ import annotations

import uuid

import pytest

from app.progression.engine import (
    ExerciseSessionData,
    ProgressionResult,
    ProgressionStatus,
    PreviousSessionData,
    RPELevel,
    SetData,
    analyze_session,
    apply_validated_reset,
    round_to_nearest_half,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_sets(
    weight_kg: float,
    reps_done: int,
    rpe: RPELevel = RPELevel.MEDIUM,
    count: int = 3,
    is_warmup: bool = False,
) -> list[SetData]:
    return [SetData(weight_kg=weight_kg, reps_done=reps_done, rpe=rpe, is_warmup=is_warmup) for _ in range(count)]


def make_data(
    sets: list[SetData],
    reps_min: int = 8,
    reps_max: int = 12,
    current_weight: float = 100.0,
    prev_sessions: list[PreviousSessionData] | None = None,
    all_time_best: float = 0.0,
) -> ExerciseSessionData:
    return ExerciseSessionData(
        program_day_exercise_id=uuid.uuid4(),
        sets=sets,
        reps_min_target=reps_min,
        reps_max_target=reps_max,
        previous_sessions=prev_sessions or [],
        current_weight_kg=current_weight,
        all_time_best_weight_kg=all_time_best,
    )


def _prev(status: ProgressionStatus = ProgressionStatus.PROGRESSING, weight: float = 100.0) -> PreviousSessionData:
    return PreviousSessionData(
        session_id=uuid.uuid4(),
        avg_weight_kg=weight,
        all_sets_reached_upper_bound=True,
        status=status,
    )


# ---------------------------------------------------------------------------
# STEP 1 — Weight rounding utility
# ---------------------------------------------------------------------------
class TestWeightRounding:
    def test_round_to_nearest_half_exact(self) -> None:
        assert round_to_nearest_half(100.0) == 100.0

    def test_round_to_nearest_half_rounds_up(self) -> None:
        assert round_to_nearest_half(100.3) == 100.5

    def test_round_to_nearest_half_rounds_down(self) -> None:
        assert round_to_nearest_half(100.1) == 100.0

    def test_round_to_nearest_half_midpoint(self) -> None:
        assert round_to_nearest_half(100.25) == 100.5

    def test_round_to_nearest_half_zero(self) -> None:
        assert round_to_nearest_half(0.0) == 0.0

    def test_round_to_nearest_half_small_weight(self) -> None:
        assert round_to_nearest_half(2.6) == 2.5

    def test_round_to_nearest_half_typical_progression(self) -> None:
        # 100 * 1.025 = 102.5 — should stay 102.5
        new_weight = round_to_nearest_half(100.0 * 1.025)
        assert new_weight == 102.5


# ---------------------------------------------------------------------------
# STEP 3 — Progression decision
# ---------------------------------------------------------------------------
class TestProgressionWhenAllSetsReachUpperBound:
    def test_progression_when_all_sets_reach_upper_bound(self) -> None:
        """Weight should increase 2.5% when all sets hit the rep ceiling at MEDIUM RPE."""
        sets = make_sets(100.0, reps_done=12, rpe=RPELevel.MEDIUM, count=3)
        result = analyze_session(make_data(sets, reps_max=12, current_weight=100.0))

        assert result.status in (ProgressionStatus.PROGRESSING, ProgressionStatus.PR_ACHIEVED)
        assert result.suggested_weight_kg == 102.5
        assert result.increase_percentage == 2.5
        assert result.consecutive_plateau_count == 0

    def test_no_progression_when_rpe_hard_even_if_all_sets_complete(self) -> None:
        """No weight increase when RPE is HARD, even if all sets completed."""
        sets = make_sets(100.0, reps_done=12, rpe=RPELevel.HARD, count=3)
        result = analyze_session(make_data(sets, reps_max=12, current_weight=100.0))

        assert result.suggested_weight_kg == 100.0
        assert result.increase_percentage == 0.0
        assert "consolidat" in result.message.lower()

    def test_progression_easy_rpe_increases_weight(self) -> None:
        """EASY RPE with all sets complete also triggers 2.5% increase."""
        sets = make_sets(100.0, reps_done=12, rpe=RPELevel.EASY, count=3)
        result = analyze_session(make_data(sets, reps_max=12, current_weight=100.0))

        assert result.suggested_weight_kg == 102.5
        assert result.increase_percentage == 2.5

    def test_suggested_weight_rounded_to_half(self) -> None:
        """Suggested weight is always rounded to nearest 0.5kg."""
        sets = make_sets(97.0, reps_done=12, rpe=RPELevel.MEDIUM, count=3)
        result = analyze_session(make_data(sets, reps_max=12, current_weight=97.0))

        assert result.suggested_weight_kg % 0.5 == 0.0


# ---------------------------------------------------------------------------
# STEP 4 — Plateau detection
# ---------------------------------------------------------------------------
class TestPlateauDetected:
    def test_plateau_detected_after_3_sessions_of_failure(self) -> None:
        """PLATEAU_DETECTED after consecutive_plateau_count reaches 3."""
        from unittest.mock import patch
        from app.progression import engine as eng

        # Inject plateau count of 2 (would be 3 after this session)
        original = eng._extract_plateau_count
        eng._extract_plateau_count = lambda _: 2  # type: ignore[assignment]
        try:
            # This session: a set failed
            sets = [
                SetData(100.0, reps_done=5, rpe=RPELevel.HARD),  # below min (8)
                SetData(100.0, reps_done=6, rpe=RPELevel.HARD),
                SetData(100.0, reps_done=5, rpe=RPELevel.HARD),
            ]
            result = analyze_session(make_data(sets, reps_min=8, reps_max=12, current_weight=100.0))
        finally:
            eng._extract_plateau_count = original  # type: ignore[assignment]

        assert result.status == ProgressionStatus.PLATEAU_DETECTED
        assert result.consecutive_plateau_count == 3
        assert result.reset_percentage == 6.0
        assert result.suggested_weight_kg == round_to_nearest_half(100.0 * 0.94)

    def test_plateau_message_mentions_sessions(self) -> None:
        """Plateau message should reference the session count."""
        from app.progression import engine as eng

        original = eng._extract_plateau_count
        eng._extract_plateau_count = lambda _: 2  # type: ignore[assignment]
        try:
            sets = make_sets(100.0, reps_done=5, rpe=RPELevel.HARD)
            result = analyze_session(make_data(sets, reps_min=8))
        finally:
            eng._extract_plateau_count = original  # type: ignore[assignment]

        assert "plateau" in result.message.lower()

    def test_no_plateau_before_3_sessions(self) -> None:
        """Should not be PLATEAU_DETECTED with only 2 failed sessions."""
        from app.progression import engine as eng

        original = eng._extract_plateau_count
        eng._extract_plateau_count = lambda _: 1  # type: ignore[assignment]
        try:
            sets = make_sets(100.0, reps_done=5, rpe=RPELevel.HARD)
            result = analyze_session(make_data(sets, reps_min=8))
        finally:
            eng._extract_plateau_count = original  # type: ignore[assignment]

        assert result.status != ProgressionStatus.PLATEAU_DETECTED


# ---------------------------------------------------------------------------
# STEP 5 — Reset applied
# ---------------------------------------------------------------------------
class TestResetApplied:
    def test_reset_applied_reduces_weight_by_6_percent(self) -> None:
        """apply_validated_reset must reduce weight by 6% and round to 0.5kg."""
        result = apply_validated_reset(current_weight_kg=100.0, reset_percentage=6.0)

        assert result.status == ProgressionStatus.RESET_APPLIED
        assert result.suggested_weight_kg == 94.0
        assert result.reset_percentage == 6.0
        assert result.consecutive_plateau_count == 0
        assert "reset" in result.message.lower()

    def test_reset_rounds_to_nearest_half(self) -> None:
        result = apply_validated_reset(97.0, 6.0)
        assert result.suggested_weight_kg % 0.5 == 0.0

    def test_reset_clears_plateau_count(self) -> None:
        result = apply_validated_reset(100.0, 6.0)
        assert result.consecutive_plateau_count == 0


# ---------------------------------------------------------------------------
# STEP 2 — PR detection
# ---------------------------------------------------------------------------
class TestPRDetection:
    def test_pr_detection_when_weight_exceeds_all_time_best(self) -> None:
        """PR_ACHIEVED when a set weight exceeds the previous all-time best."""
        sets = make_sets(110.0, reps_done=12, rpe=RPELevel.MEDIUM)
        result = analyze_session(
            make_data(sets, reps_max=12, current_weight=110.0, all_time_best=105.0)
        )

        assert result.status == ProgressionStatus.PR_ACHIEVED
        assert result.is_pr is True

    def test_no_pr_when_weight_equals_best(self) -> None:
        """Exactly matching all-time best does NOT count as a PR."""
        sets = make_sets(100.0, reps_done=12, rpe=RPELevel.MEDIUM)
        result = analyze_session(
            make_data(sets, reps_max=12, current_weight=100.0, all_time_best=100.0)
        )

        assert result.is_pr is False

    def test_pr_with_all_sets_complete_still_progresses(self) -> None:
        """PR should be combined with normal progression (weight still increases)."""
        sets = make_sets(110.0, reps_done=12, rpe=RPELevel.MEDIUM)
        result = analyze_session(
            make_data(sets, reps_max=12, current_weight=110.0, all_time_best=105.0)
        )

        assert result.suggested_weight_kg > 110.0  # Should increase
        assert result.is_pr is True


# ---------------------------------------------------------------------------
# STEP 6 — Special RPE adjustments
# ---------------------------------------------------------------------------
class TestFastProgression:
    def test_fast_progression_when_rpe_easy_two_sessions(self) -> None:
        """When last 2 sessions were PROGRESSING and current RPE is EASY, increase by 5%."""
        prev = [_prev(ProgressionStatus.PROGRESSING), _prev(ProgressionStatus.PROGRESSING)]
        sets = make_sets(100.0, reps_done=12, rpe=RPELevel.EASY)
        result = analyze_session(
            make_data(sets, reps_max=12, current_weight=100.0, prev_sessions=prev)
        )

        assert result.increase_percentage == 5.0
        assert result.suggested_weight_kg == round_to_nearest_half(100.0 * 1.05)

    def test_no_fast_progression_if_only_one_previous_session(self) -> None:
        """Fast progression requires 2 consecutive PROGRESSING sessions."""
        prev = [_prev(ProgressionStatus.PROGRESSING)]
        sets = make_sets(100.0, reps_done=12, rpe=RPELevel.EASY)
        result = analyze_session(
            make_data(sets, reps_max=12, current_weight=100.0, prev_sessions=prev)
        )

        assert result.increase_percentage == 2.5

    def test_no_fast_progression_when_rpe_medium(self) -> None:
        """Fast progression only applies when RPE is EASY."""
        prev = [_prev(ProgressionStatus.PROGRESSING), _prev(ProgressionStatus.PROGRESSING)]
        sets = make_sets(100.0, reps_done=12, rpe=RPELevel.MEDIUM)
        result = analyze_session(
            make_data(sets, reps_max=12, current_weight=100.0, prev_sessions=prev)
        )

        assert result.increase_percentage == 2.5

    def test_consolidation_when_hard_rpe_at_upper_bound(self) -> None:
        """HARD RPE at exactly the upper bound — consolidate, don't increase."""
        sets = make_sets(100.0, reps_done=12, rpe=RPELevel.HARD)
        result = analyze_session(make_data(sets, reps_max=12, current_weight=100.0))

        assert result.suggested_weight_kg == 100.0
        assert result.increase_percentage == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_only_warmup_sets_returns_no_change(self) -> None:
        """If only warmup sets are logged, engine maintains weight."""
        sets = [SetData(60.0, reps_done=12, rpe=RPELevel.EASY, is_warmup=True)]
        result = analyze_session(make_data(sets, current_weight=100.0))

        assert result.suggested_weight_kg == 100.0
        assert result.consecutive_plateau_count == 0

    def test_sets_in_range_no_increase(self) -> None:
        """Reps in min-max range but not at max — no weight increase."""
        sets = make_sets(100.0, reps_done=10, rpe=RPELevel.MEDIUM)  # 8-12 range, did 10
        result = analyze_session(make_data(sets, reps_min=8, reps_max=12, current_weight=100.0))

        assert result.suggested_weight_kg == 100.0
        assert result.increase_percentage == 0.0
