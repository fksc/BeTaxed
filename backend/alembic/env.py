import asyncio
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.models import Base
from app.settings import get_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Dated revision ids like `20260825_01_contracts_notifications` are 35 chars.
# Alembic 1.15 still creates alembic_version.version_num as VARCHAR(32).
_VERSION_NUM_LENGTH = 64


def get_url() -> str:
    return get_database_url()


def _ensure_version_num_width(connection: Connection) -> None:
    row = connection.execute(
        text(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'alembic_version'
              AND column_name = 'version_num'
            """
        )
    ).fetchone()
    if row is None:
        connection.execute(
            text(
                f"""
                CREATE TABLE alembic_version (
                    version_num VARCHAR({_VERSION_NUM_LENGTH}) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
                """
            )
        )
        return
    current = row[0]
    if current is not None and current < _VERSION_NUM_LENGTH:
        connection.execute(
            text(
                f"ALTER TABLE alembic_version "
                f"ALTER COLUMN version_num TYPE VARCHAR({_VERSION_NUM_LENGTH})"
            )
        )


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        _ensure_version_num_width(connection)
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
