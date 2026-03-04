"""Modèle de domaine utilisateur."""
from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class UserGoal(str, enum.Enum):
    HYPERTROPHY = "HYPERTROPHY"
    STRENGTH = "STRENGTH"
    MIXED = "MIXED"


class UserLevel(str, enum.Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class SplitType(str, enum.Enum):
    FULL_BODY = "FULL_BODY"
    UPPER_LOWER = "UPPER_LOWER"
    PUSH_PULL_LEGS = "PUSH_PULL_LEGS"
    CUSTOM = "CUSTOM"


class User(BaseModel):
    __tablename__ = "users"

    auth0_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    goal: Mapped[UserGoal | None] = mapped_column(
        Enum(UserGoal, name="user_goal"), nullable=True
    )
    level: Mapped[UserLevel | None] = mapped_column(
        Enum(UserLevel, name="user_level"), nullable=True
    )
    frequency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_split: Mapped[SplitType | None] = mapped_column(
        Enum(SplitType, name="split_type"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    # Relations
    programs: Mapped[list["Program"]] = relationship(  # noqa: F821
        "Program", back_populates="user", lazy="selectin"
    )
    workout_sessions: Mapped[list["WorkoutSession"]] = relationship(  # noqa: F821
        "WorkoutSession", back_populates="user", lazy="selectin"
    )
    personal_records: Mapped[list["PersonalRecord"]] = relationship(  # noqa: F821
        "PersonalRecord", back_populates="user", lazy="selectin"
    )
