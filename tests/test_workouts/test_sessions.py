"""Integration tests for workout session endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.exercises.models import Exercise, ExerciseCategory
from app.programs.models import Program, ProgramDay, ProgramDayExercise
from app.users.models import SplitType, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
async def test_program(db_session: AsyncSession, test_user: User) -> Program:
    program = Program(
        user_id=test_user.id,
        name="Test Program",
        split_type=SplitType.PUSH_PULL_LEGS,
    )
    db_session.add(program)
    await db_session.flush()
    return program


@pytest.fixture
async def test_day(db_session: AsyncSession, test_program: Program) -> ProgramDay:
    day = ProgramDay(
        program_id=test_program.id,
        day_name="Push Day",
        day_order=0,
    )
    db_session.add(day)
    await db_session.flush()
    return day


@pytest.fixture
async def test_exercise(db_session: AsyncSession) -> Exercise:
    exercise = Exercise(
        name="Bench Press",
        category=ExerciseCategory.COMPOUND_CHEST,
        muscle_group="Chest",
        description="Barbell bench press",
        is_custom=False,
    )
    db_session.add(exercise)
    await db_session.flush()
    return exercise


@pytest.fixture
async def test_pde(
    db_session: AsyncSession,
    test_day: ProgramDay,
    test_exercise: Exercise,
) -> ProgramDayExercise:
    pde = ProgramDayExercise(
        program_day_id=test_day.id,
        exercise_id=test_exercise.id,
        sets_target=3,
        reps_min=8,
        reps_max=12,
        order_in_day=0,
    )
    db_session.add(pde)
    await db_session.flush()
    return pde


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestCreateSession:
    async def test_create_session_authenticated(
        self,
        client: AsyncClient,
        test_day: ProgramDay,
    ) -> None:
        """Authenticated user can start a new workout session."""
        response = await client.post(
            "/api/v1/workouts/sessions",
            json={"program_day_id": str(test_day.id)},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["program_day_id"] == str(test_day.id)
        assert data["completed_at"] is None

    async def test_create_session_unauthenticated_fails(
        self,
        unauthenticated_client: AsyncClient,
        test_day: ProgramDay,
    ) -> None:
        """Unauthenticated request must fail with 401."""
        response = await unauthenticated_client.post(
            "/api/v1/workouts/sessions",
            json={"program_day_id": str(test_day.id)},
        )

        assert response.status_code == 401


class TestAddSet:
    async def test_add_set_to_session(
        self,
        client: AsyncClient,
        test_day: ProgramDay,
        test_pde: ProgramDayExercise,
    ) -> None:
        """User can add a working set to an active session."""
        # Create session first
        session_resp = await client.post(
            "/api/v1/workouts/sessions",
            json={"program_day_id": str(test_day.id)},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]

        # Add a set
        set_resp = await client.post(
            f"/api/v1/workouts/sessions/{session_id}/sets",
            json={
                "program_day_exercise_id": str(test_pde.id),
                "set_number": 1,
                "weight_kg": 100.0,
                "reps_done": 10,
                "rpe": "MEDIUM",
                "is_warmup": False,
            },
        )

        assert set_resp.status_code == 201
        set_data = set_resp.json()
        assert set_data["weight_kg"] == 100.0
        assert set_data["reps_done"] == 10
        assert set_data["rpe"] == "MEDIUM"

    async def test_cannot_add_set_to_nonexistent_session(
        self,
        client: AsyncClient,
        test_pde: ProgramDayExercise,
    ) -> None:
        """Adding a set to a non-existent session returns 404."""
        fake_session_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/workouts/sessions/{fake_session_id}/sets",
            json={
                "program_day_exercise_id": str(test_pde.id),
                "set_number": 1,
                "weight_kg": 100.0,
                "reps_done": 10,
                "rpe": "MEDIUM",
                "is_warmup": False,
            },
        )

        assert response.status_code == 404


class TestOwnershipIsolation:
    async def test_cannot_access_other_user_session(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        test_day: ProgramDay,
    ) -> None:
        """User A cannot see User B's session — must return 403."""
        from app.workouts.models import WorkoutSession

        # Create a session owned by other_user
        other_session = WorkoutSession(
            user_id=other_user.id,
            program_day_id=test_day.id,
            started_at=datetime.now(tz=timezone.utc),
        )
        db_session.add(other_session)
        await db_session.flush()

        response = await client.get(f"/api/v1/workouts/sessions/{other_session.id}")

        assert response.status_code == 403

    async def test_cannot_add_set_to_other_user_session(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        test_day: ProgramDay,
        test_pde: ProgramDayExercise,
    ) -> None:
        """User A cannot add sets to User B's session."""
        from app.workouts.models import WorkoutSession

        other_session = WorkoutSession(
            user_id=other_user.id,
            program_day_id=test_day.id,
            started_at=datetime.now(tz=timezone.utc),
        )
        db_session.add(other_session)
        await db_session.flush()

        response = await client.post(
            f"/api/v1/workouts/sessions/{other_session.id}/sets",
            json={
                "program_day_exercise_id": str(test_pde.id),
                "set_number": 1,
                "weight_kg": 100.0,
                "reps_done": 10,
                "rpe": "MEDIUM",
            },
        )

        assert response.status_code == 403


class TestCompleteSession:
    async def test_complete_session_triggers_progression_engine(
        self,
        client: AsyncClient,
        test_day: ProgramDay,
        test_pde: ProgramDayExercise,
        db_session: AsyncSession,
    ) -> None:
        """Completing a session should trigger the progression engine without error."""
        # Start session
        session_resp = await client.post(
            "/api/v1/workouts/sessions",
            json={"program_day_id": str(test_day.id)},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]

        # Add sets
        for i in range(3):
            await client.post(
                f"/api/v1/workouts/sessions/{session_id}/sets",
                json={
                    "program_day_exercise_id": str(test_pde.id),
                    "set_number": i + 1,
                    "weight_kg": 80.0,
                    "reps_done": 12,
                    "rpe": "MEDIUM",
                    "is_warmup": False,
                },
            )

        # Complete the session
        complete_resp = await client.put(
            f"/api/v1/workouts/sessions/{session_id}/complete",
            json={"session_rpe_overall": "MEDIUM"},
        )

        assert complete_resp.status_code == 200
        data = complete_resp.json()
        assert data["completed_at"] is not None

    async def test_cannot_complete_already_completed_session(
        self,
        client: AsyncClient,
        test_day: ProgramDay,
    ) -> None:
        """Completing an already-completed session returns 400."""
        session_resp = await client.post(
            "/api/v1/workouts/sessions",
            json={"program_day_id": str(test_day.id)},
        )
        session_id = session_resp.json()["id"]

        # Complete once
        await client.put(
            f"/api/v1/workouts/sessions/{session_id}/complete",
            json={},
        )

        # Try to complete again
        response = await client.put(
            f"/api/v1/workouts/sessions/{session_id}/complete",
            json={},
        )

        assert response.status_code == 400
