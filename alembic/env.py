"""Environnement Alembic pour les migrations SQLAlchemy asynchrones."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Importer tous les modèles pour qu'Alembic puisse les détecter
from app.core.base_model import BaseModel  # noqa: F401
from app.core.config import get_settings

# Modèles de domaine — doivent être importés pour alimenter les métadonnées
from app.users.models import User  # noqa: F401
from app.exercises.models import Exercise  # noqa: F401
from app.programs.models import Program, ProgramDay, ProgramDayExercise  # noqa: F401
from app.workouts.models import WorkoutSession, WorkoutSet  # noqa: F401
from app.progression.models import ProgressionLog  # noqa: F401
from app.gamification.models import PersonalRecord  # noqa: F401

settings = get_settings()

# Objet de configuration Alembic
config = context.config

# Interpréter le fichier de configuration pour la journalisation Python
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Définir les métadonnées pour l'autogénération
target_metadata = BaseModel.metadata

# Remplacer sqlalchemy.url par les paramètres de l'application
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Lance les migrations en mode 'hors ligne' (aucune connexion à la base de données nécessaire)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Lance les migrations en utilisant un moteur asynchrone."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Lance les migrations en mode 'en ligne'."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
