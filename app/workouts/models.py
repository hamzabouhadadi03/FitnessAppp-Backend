"""Modèles WorkoutSession et WorkoutSet."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class RPELevel(str, enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class WorkoutSession(BaseModel):
    __tablename__ = "workout_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    program_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("program_days.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_rpe_overall: Mapped[RPELevel | None] = mapped_column(
        Enum(RPELevel, name="rpe_level"), nullable=True
    )

    # Relations
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="workout_sessions", lazy="selectin"
    )
    program_day: Mapped["ProgramDay"] = relationship(  # noqa: F821
        "ProgramDay", back_populates="workout_sessions", lazy="selectin"
    )
    sets: Mapped[list["WorkoutSet"]] = relationship(
        "WorkoutSet",
        back_populates="session",
        lazy="selectin",
        order_by="WorkoutSet.set_number",
    )
    progression_logs: Mapped[list["ProgressionLog"]] = relationship(  # noqa: F821
        "ProgressionLog", back_populates="session", lazy="selectin"
    )


class WorkoutSet(BaseModel):
    __tablename__ = "workout_sets"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    program_day_exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("program_day_exercises.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    reps_done: Mapped[int] = mapped_column(Integer, nullable=False)
    rpe: Mapped[RPELevel] = mapped_column(
        Enum(RPELevel, name="rpe_level"), nullable=False
    )
    is_warmup: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    # Relations
    session: Mapped["WorkoutSession"] = relationship(
        "WorkoutSession", back_populates="sets", lazy="selectin"
    )
    program_day_exercise: Mapped["ProgramDayExercise"] = relationship(  # noqa: F821
        "ProgramDayExercise", back_populates="workout_sets", lazy="selectin"
    )
