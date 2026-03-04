"""Schéma initial — toutes les tables.

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Types énumérés
    # ------------------------------------------------------------------
    op.execute("CREATE TYPE user_goal AS ENUM ('HYPERTROPHY', 'STRENGTH', 'MIXED')")
    op.execute("CREATE TYPE user_level AS ENUM ('BEGINNER', 'INTERMEDIATE', 'ADVANCED')")
    op.execute("CREATE TYPE split_type AS ENUM ('FULL_BODY', 'UPPER_LOWER', 'PUSH_PULL_LEGS', 'CUSTOM')")
    op.execute(
        "CREATE TYPE exercise_category AS ENUM ("
        "'COMPOUND_CHEST', 'SHOULDERS', 'TRICEPS', 'ISOLATION_CHEST', "
        "'COMPOUND_BACK', 'BICEPS', 'ISOLATION_BACK', "
        "'COMPOUND_LEGS', 'ISOLATION_LEGS', 'CORE', 'CARDIO')"
    )
    op.execute("CREATE TYPE rpe_level AS ENUM ('EASY', 'MEDIUM', 'HARD')")
    op.execute(
        "CREATE TYPE progression_status AS ENUM ("
        "'PROGRESSING', 'PLATEAU_DETECTED', 'RESET_APPLIED', 'PR_ACHIEVED')"
    )

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("auth0_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("goal", postgresql.ENUM("HYPERTROPHY", "STRENGTH", "MIXED", name="user_goal", create_type=False), nullable=True),
        sa.Column("level", postgresql.ENUM("BEGINNER", "INTERMEDIATE", "ADVANCED", name="user_level", create_type=False), nullable=True),
        sa.Column("frequency", sa.Integer(), nullable=True),
        sa.Column("preferred_split", postgresql.ENUM("FULL_BODY", "UPPER_LOWER", "PUSH_PULL_LEGS", "CUSTOM", name="split_type", create_type=False), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_onboarded", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_auth0_sub", "users", ["auth0_sub"])
    op.create_index("ix_users_email", "users", ["email"])

    # ------------------------------------------------------------------
    # exercises
    # ------------------------------------------------------------------
    op.create_table(
        "exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", postgresql.ENUM(
            "COMPOUND_CHEST", "SHOULDERS", "TRICEPS", "ISOLATION_CHEST",
            "COMPOUND_BACK", "BICEPS", "ISOLATION_BACK",
            "COMPOUND_LEGS", "ISOLATION_LEGS", "CORE", "CARDIO",
            name="exercise_category", create_type=False
        ), nullable=False),
        sa.Column("muscle_group", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_exercises_name", "exercises", ["name"])
    op.create_index("ix_exercises_created_by_user_id", "exercises", ["created_by_user_id"])

    # ------------------------------------------------------------------
    # programs
    # ------------------------------------------------------------------
    op.create_table(
        "programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("split_type", postgresql.ENUM("FULL_BODY", "UPPER_LOWER", "PUSH_PULL_LEGS", "CUSTOM", name="split_type", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("weeks_duration", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_programs_user_id", "programs", ["user_id"])

    # ------------------------------------------------------------------
    # program_days
    # ------------------------------------------------------------------
    op.create_table(
        "program_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_name", sa.String(100), nullable=False),
        sa.Column("day_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_program_days_program_id", "program_days", ["program_id"])

    # ------------------------------------------------------------------
    # program_day_exercises
    # ------------------------------------------------------------------
    op.create_table(
        "program_day_exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("program_day_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("program_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sets_target", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("reps_min", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("reps_max", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("order_in_day", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_program_day_exercises_program_day_id", "program_day_exercises", ["program_day_id"])
    op.create_index("ix_program_day_exercises_exercise_id", "program_day_exercises", ["exercise_id"])

    # ------------------------------------------------------------------
    # workout_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "workout_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_day_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("program_days.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("session_rpe_overall", postgresql.ENUM("EASY", "MEDIUM", "HARD", name="rpe_level", create_type=False), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workout_sessions_user_id", "workout_sessions", ["user_id"])
    op.create_index("ix_workout_sessions_program_day_id", "workout_sessions", ["program_day_id"])

    # ------------------------------------------------------------------
    # workout_sets
    # ------------------------------------------------------------------
    op.create_table(
        "workout_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_day_exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("program_day_exercises.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("reps_done", sa.Integer(), nullable=False),
        sa.Column("rpe", postgresql.ENUM("EASY", "MEDIUM", "HARD", name="rpe_level", create_type=False), nullable=False),
        sa.Column("is_warmup", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workout_sets_session_id", "workout_sets", ["session_id"])
    op.create_index("ix_workout_sets_program_day_exercise_id", "workout_sets", ["program_day_exercise_id"])

    # ------------------------------------------------------------------
    # progression_logs
    # ------------------------------------------------------------------
    op.create_table(
        "progression_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_day_exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("program_day_exercises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", postgresql.ENUM(
            "PROGRESSING", "PLATEAU_DETECTED", "RESET_APPLIED", "PR_ACHIEVED",
            name="progression_status", create_type=False
        ), nullable=False),
        sa.Column("suggested_weight_kg", sa.Float(), nullable=True),
        sa.Column("reset_percentage", sa.Float(), nullable=True),
        sa.Column("consecutive_plateau_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_progression_logs_user_id", "progression_logs", ["user_id"])
    op.create_index("ix_progression_logs_program_day_exercise_id", "progression_logs", ["program_day_exercise_id"])
    op.create_index("ix_progression_logs_session_id", "progression_logs", ["session_id"])

    # ------------------------------------------------------------------
    # personal_records
    # ------------------------------------------------------------------
    op.create_table(
        "personal_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workout_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_personal_records_user_id", "personal_records", ["user_id"])
    op.create_index("ix_personal_records_exercise_id", "personal_records", ["exercise_id"])


def downgrade() -> None:
    op.drop_table("personal_records")
    op.drop_table("progression_logs")
    op.drop_table("workout_sets")
    op.drop_table("workout_sessions")
    op.drop_table("program_day_exercises")
    op.drop_table("program_days")
    op.drop_table("programs")
    op.drop_table("exercises")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS progression_status")
    op.execute("DROP TYPE IF EXISTS rpe_level")
    op.execute("DROP TYPE IF EXISTS exercise_category")
    op.execute("DROP TYPE IF EXISTS split_type")
    op.execute("DROP TYPE IF EXISTS user_level")
    op.execute("DROP TYPE IF EXISTS user_goal")
