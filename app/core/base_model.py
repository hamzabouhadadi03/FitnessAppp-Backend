"""Mixin de modèle de base partagé pour toutes les tables de la base de données.

Toutes les tables héritent de la suppression douce, des clés primaires UUID et des horodatages d'audit depuis ce mixin.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimestampMixin:
    """Fournit les colonnes created_at et updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Fournit les colonnes de suppression douce. NE JAMAIS supprimer définitivement les données utilisateur."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default="false",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class UUIDPrimaryKeyMixin:
    """Clé primaire UUID — prévient les attaques par énumération d'identifiants séquentiels."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class BaseModel(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Base abstraite pour tous les modèles de domaine.

    Fournit : clé primaire UUID, created_at, updated_at, is_deleted, deleted_at.
    """

    __abstract__ = True
