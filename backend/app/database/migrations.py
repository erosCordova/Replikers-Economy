from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import (
    MigrationContext,
)
from alembic.script import (
    ScriptDirectory,
)
from sqlalchemy.engine import Engine


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


class DatabaseMigrationError(
    RuntimeError
):
    pass


@dataclass(
    frozen=True
)
class DatabaseRevisionStatus:
    current_heads: tuple[str, ...]
    expected_heads: tuple[str, ...]
    is_current: bool


def build_alembic_config() -> Config:
    ini_path = (
        BACKEND_ROOT
        / "alembic.ini"
    )

    script_path = (
        BACKEND_ROOT
        / "alembic"
    )

    if not ini_path.is_file():
        raise DatabaseMigrationError(
            "No se encontro alembic.ini."
        )

    if not script_path.is_dir():
        raise DatabaseMigrationError(
            "No se encontro el directorio "
            "de migraciones Alembic."
        )

    config = Config(
        str(ini_path)
    )

    config.set_main_option(
        "script_location",
        str(script_path),
    )

    return config


def expected_database_heads() -> tuple[str, ...]:
    config = (
        build_alembic_config()
    )

    script = (
        ScriptDirectory
        .from_config(
            config
        )
    )

    heads = tuple(
        sorted(
            script.get_heads()
        )
    )

    if not heads:
        raise DatabaseMigrationError(
            "Alembic no tiene una "
            "revision head definida."
        )

    return heads


def current_database_heads(
    engine: Engine,
) -> tuple[str, ...]:
    with engine.connect() as connection:
        context = (
            MigrationContext
            .configure(
                connection
            )
        )

        return tuple(
            sorted(
                context
                .get_current_heads()
            )
        )


def database_revision_status(
    engine: Engine,
) -> DatabaseRevisionStatus:
    expected = (
        expected_database_heads()
    )

    current = (
        current_database_heads(
            engine
        )
    )

    return DatabaseRevisionStatus(
        current_heads=current,
        expected_heads=expected,
        is_current=(
            current == expected
        ),
    )


def assert_database_migrations_current(
    engine: Engine,
) -> DatabaseRevisionStatus:
    status = (
        database_revision_status(
            engine
        )
    )

    if status.is_current:
        return status

    current_text = (
        ", ".join(
            status.current_heads
        )
        if status.current_heads
        else "sin revision"
    )

    expected_text = (
        ", ".join(
            status.expected_heads
        )
    )

    raise DatabaseMigrationError(
        "La base de datos no esta "
        "actualizada con Alembic. "
        f"Revision actual: {current_text}. "
        f"Revision esperada: "
        f"{expected_text}. "
        "Ejecuta 'python -m alembic "
        "upgrade head' antes de iniciar "
        "la aplicacion."
    )
