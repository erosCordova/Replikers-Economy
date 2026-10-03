from __future__ import annotations


def normalize_database_url(
    database_url: str,
) -> str:
    """
    Normaliza URLs para SQLAlchemy 2 + psycopg 3.

    SQLite se conserva sin modificaciones.

    PostgreSQL:
        postgres://
        postgresql://

    se convierten a:
        postgresql+psycopg://
    """

    clean_url = (
        database_url.strip()
    )

    if not clean_url:
        raise ValueError(
            "DATABASE_URL no puede estar vacio."
        )

    if clean_url.startswith(
        "postgresql+psycopg://"
    ):
        return clean_url

    if clean_url.startswith(
        "postgresql://"
    ):
        return (
            "postgresql+psycopg://"
            + clean_url[
                len("postgresql://"):
            ]
        )

    if clean_url.startswith(
        "postgres://"
    ):
        return (
            "postgresql+psycopg://"
            + clean_url[
                len("postgres://"):
            ]
        )

    return clean_url


def is_sqlite_url(
    database_url: str,
) -> bool:
    return (
        normalize_database_url(
            database_url
        )
        .lower()
        .startswith(
            "sqlite"
        )
    )


def is_postgresql_url(
    database_url: str,
) -> bool:
    return (
        normalize_database_url(
            database_url
        )
        .lower()
        .startswith(
            "postgresql+psycopg://"
        )
    )
