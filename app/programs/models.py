"""Modèles Program, ProgramDay et ProgramDayExercise."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.users.models import SplitType


class Program(BaseModel):
    __tablename__ = "programs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    split_type: Mapped[SplitType] = mapped_column(
        Enum(SplitType, name="split_type"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    weeks_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relations
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="programs", lazy="selectin"
    )
    days: Mapped[list["ProgramDay"]] = relationship(
        "ProgramDay", back_populates="program", lazy="selectin", order_by="ProgramDay.day_order"
    )


class ProgramDay(BaseModel):
    __tablename__ = "program_days"

    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_name: Mapped[str] = mapped_column(String(100), nullable=False)
    day_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relations
    program: Mapped["Program"] = relationship(
        "Program", back_populates="days", lazy="selectin"
    )
    exercises: Mapped[list["ProgramDayExercise"]] = relationship(
        "ProgramDayExercise",
        back_populates="program_day",
        lazy="selectin",
        order_by="ProgramDayExercise.order_in_day",
    )
    workout_sessions: Mapped[list["WorkoutSession"]] = relationship(  # noqa: F821
        "WorkoutSession", back_populates="program_day", lazy="selectin"
    )


class ProgramDayExercise(BaseModel):
    __tablename__ = "program_day_exercises"

    program_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("program_days.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercises.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sets_target: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    reps_min: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    reps_max: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    order_in_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relations
    program_day: Mapped["ProgramDay"] = relationship(
        "ProgramDay", back_populates="exercises", lazy="selectin"
    )
    exercise: Mapped["Exercise"] = relationship(  # noqa: F821
        "Exercise", back_populates="program_day_exercises", lazy="selectin"
    )
    workout_sets: Mapped[list["WorkoutSet"]] = relationship(  # noqa: F821
        "WorkoutSet", back_populates="program_day_exercise", lazy="selectin"
    )
    progression_logs: Mapped[list["ProgressionLog"]] = relationship(  # noqa: F821
        "ProgressionLog", back_populates="program_day_exercise", lazy="selectin"
    )
