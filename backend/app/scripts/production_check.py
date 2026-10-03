from sqlalchemy import text

from app.core.config import settings
from app.database.migrations import (
    assert_database_migrations_current,
)
from app.database.session import engine


def main():
    try:
        settings.assert_production_ready()

        with engine.connect() as connection:
            connection.execute(
                text("SELECT 1")
            )

        assert_database_migrations_current(
            engine
        )

    except Exception:
        print(
            "PRODUCTION_CHECK ................... ERROR"
        )

        raise SystemExit(1)

    print(
        "PRODUCTION_CONFIG .................. OK"
    )

    print(
        "DATABASE_ENGINE .................... "
        + engine.dialect.name
    )

    print(
        "DATABASE_CONNECTION ................. OK"
    )

    print(
        "ALEMBIC_REVISION .................... OK"
    )

    print(
        "ECONOMY_MODE ........................ "
        + settings.ECONOMY_MODE
    )

    print(
        "REAL_PAYMENTS ....................... DISABLED"
    )

    print(
        "PRODUCTION_CHECK .................... OK"
    )


if __name__ == "__main__":
    main()
