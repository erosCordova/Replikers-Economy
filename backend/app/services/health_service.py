from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.database.migrations import (
    database_revision_status,
)
from app.database.session import engine


@dataclass(
    frozen=True
)
class ReadinessResult:
    ready: bool
    database: str
    migrations: str


def check_readiness(
    db_engine: Engine | None = None,
) -> ReadinessResult:
    target_engine = (
        db_engine
        or engine
    )

    try:
        with target_engine.connect() as connection:
            connection.execute(
                text("SELECT 1")
            )

    except Exception:
        return ReadinessResult(
            ready=False,
            database="unavailable",
            migrations="unknown",
        )

    try:
        revision = (
            database_revision_status(
                target_engine
            )
        )

    except Exception:
        return ReadinessResult(
            ready=False,
            database="ok",
            migrations="unavailable",
        )

    if not revision.is_current:
        return ReadinessResult(
            ready=False,
            database="ok",
            migrations="outdated",
        )

    return ReadinessResult(
        ready=True,
        database="ok",
        migrations="current",
    )
