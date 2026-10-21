from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.database.url import (
    is_sqlite_url,
    normalize_database_url,
)


DATABASE_URL = (
    normalize_database_url(
        settings.DATABASE_URL
    )
)


def build_engine() -> Engine:
    engine_kwargs: dict = {
        "pool_pre_ping":
            settings.DB_POOL_PRE_PING,
    }

    connect_args: dict = {}

    if is_sqlite_url(
        DATABASE_URL
    ):
        connect_args[
            "check_same_thread"
        ] = False

    else:
        # PostgreSQL remoto usa conexiones
        # de vida corta. Esto evita que cada
        # instancia local de Uvicorn reserve
        # varias sesiones del pool de Supabase.
        engine_kwargs[
            "poolclass"
        ] = NullPool

    return create_engine(
        DATABASE_URL,
        connect_args=
            connect_args,
        **engine_kwargs,
    )


engine = build_engine()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)
