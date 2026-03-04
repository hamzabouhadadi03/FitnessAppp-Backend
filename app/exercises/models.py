"""Modèle de la bibliothèque d'exercices."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class ExerciseCategory(str, enum.Enum):
    COMPOUND_CHEST = "COMPOUND_CHEST"
    SHOULDERS = "SHOULDERS"
    TRICEPS = "TRICEPS"
    ISOLATION_CHEST = "ISOLATION_CHEST"
    COMPOUND_BACK = "COMPOUND_BACK"
    BICEPS = "BICEPS"
    ISOLATION_BACK = "ISOLATION_BACK"
    COMPOUND_LEGS = "COMPOUND_LEGS"
    ISOLATION_LEGS = "ISOLATION_LEGS"
    CORE = "CORE"
    CARDIO = "CARDIO"


class Exercise(BaseModel):
    __tablename__ = "exercises"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[ExerciseCategory] = mapped_column(
        Enum(ExerciseCategory, name="exercise_category"), nullable=False
    )
    muscle_group: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_custom: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relations
    created_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by_user_id], lazy="selectin"
    )
    program_day_exercises: Mapped[list["ProgramDayExercise"]] = relationship(  # noqa: F821
        "ProgramDayExercise", back_populates="exercise", lazy="selectin"
    )
    personal_records: Mapped[list["PersonalRecord"]] = relationship(  # noqa: F821
        "PersonalRecord", back_populates="exercise", lazy="selectin"
    )
