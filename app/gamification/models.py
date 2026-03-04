"""Modèle PersonalRecord pour le module de gamification."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class PersonalRecord(BaseModel):
    __tablename__ = "personal_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercises.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    achieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relations
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="personal_records", lazy="selectin"
    )
    exercise: Mapped["Exercise"] = relationship(  # noqa: F821
        "Exercise", back_populates="personal_records", lazy="selectin"
    )
    session: Mapped["WorkoutSession | None"] = relationship(  # noqa: F821
        "WorkoutSession", foreign_keys=[session_id], lazy="selectin"
    )
