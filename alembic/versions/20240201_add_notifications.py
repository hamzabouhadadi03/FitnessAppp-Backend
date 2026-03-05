"""Add device_tokens and user_notification_prefs tables.

Revision ID: 002_add_notifications
Revises    : 001_initial_schema
Create Date: 2024-02-01 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_add_notifications"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the enum type only if it doesn't exist (asyncpg-safe approach)
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'platform_type') THEN
                CREATE TYPE platform_type AS ENUM ('IOS', 'ANDROID');
            END IF;
        END $$;
    """))

    # ── device_tokens ─────────────────────────────────────────────────────
    # Use String column to avoid SQLAlchemy auto-create enum in create_table,
    # then alter it to the proper enum type
    op.create_table(
        "device_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(500), nullable=False, unique=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("app_version", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Alter the platform column to use the enum type
    op.execute(sa.text(
        "ALTER TABLE device_tokens ALTER COLUMN platform TYPE platform_type "
        "USING platform::platform_type"
    ))

    op.create_index("ix_device_tokens_token", "device_tokens", ["token"])
    op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"])

    # ── user_notification_prefs ───────────────────────────────────────────
    op.create_table(
        "user_notification_prefs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "workout_reminder_enabled",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "reminder_hour", sa.Integer, nullable=False, server_default="9"
        ),
        sa.Column(
            "reminder_days",
            sa.Text,
            nullable=False,
            server_default="""'["Mon","Tue","Wed","Thu","Fri"]'""",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_notification_prefs_user_id",
        "user_notification_prefs",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("user_notification_prefs")
    op.drop_table("device_tokens")
    op.execute(sa.text("DROP TYPE IF EXISTS platform_type"))
