"""Modèle ProgressionLog — enregistre la sortie du moteur par session et par exercice."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class ProgressionStatus(str, enum.Enum):
    PROGRESSING = "PROGRESSING"
    PLATEAU_DETECTED = "PLATEAU_DETECTED"
    RESET_APPLIED = "RESET_APPLIED"
    PR_ACHIEVED = "PR_ACHIEVED"


class ProgressionLog(BaseModel):
    __tablename__ = "progression_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    program_day_exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("program_day_exercises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ProgressionStatus] = mapped_column(
        Enum(ProgressionStatus, name="progression_status"), nullable=False
    )
    suggested_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    reset_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    consecutive_plateau_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[user_id], lazy="selectin"
    )
    program_day_exercise: Mapped["ProgramDayExercise"] = relationship(  # noqa: F821
        "ProgramDayExercise", back_populates="progression_logs", lazy="selectin"
    )
    session: Mapped["WorkoutSession"] = relationship(  # noqa: F821
        "WorkoutSession", back_populates="progression_logs", lazy="selectin"
    )
