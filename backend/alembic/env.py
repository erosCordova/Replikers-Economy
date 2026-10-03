from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import (
    create_engine,
    pool,
)

from app.core.config import settings
from app.database.base import Base
from app.database.url import (
    is_sqlite_url,
    normalize_database_url,
)

# Importar todos los modelos registra
# las tablas dentro de Base.metadata.
import app.models  # noqa: F401


config = context.config


if (
    config.config_file_name
    is not None
):
    fileConfig(
        config.config_file_name
    )


target_metadata = (
    Base.metadata
)


def database_url() -> str:
    return normalize_database_url(
        settings.DATABASE_URL
    )


def configure_context(
    *,
    connection=None,
    url: str | None = None,
):
    options = {
        "target_metadata":
            target_metadata,

        "compare_type":
            True,

        "compare_server_default":
            True,

        "render_as_batch":
            is_sqlite_url(
                url
                or database_url()
            ),
    }

    if connection is not None:
        options[
            "connection"
        ] = connection

    if url is not None:
        options[
            "url"
        ] = url

    context.configure(
        **options,
    )


def run_migrations_offline():
    url = database_url()

    configure_context(
        url=url,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    url = database_url()

    connectable = create_engine(
        url,
        poolclass=
            pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            configure_context(
                connection=
                    connection,
                url=url,
            )

            with context.begin_transaction():
                context.run_migrations()

    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()

else:
    run_migrations_online()
