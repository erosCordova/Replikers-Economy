from app.database.migrations import (
    DatabaseMigrationError,
    assert_database_migrations_current,
)
from app.database.session import (
    SessionLocal,
    engine,
)
from app.services.web_repliker_registry_service import (
    ECOSYSTEM_OWNER_EMAIL,
    ensure_web_repliker_registry,
)


def main() -> None:
    try:
        assert_database_migrations_current(
            engine
        )

    except DatabaseMigrationError as exc:
        print(
            "No se puede registrar el "
            "catálogo de Replikers."
        )
        print(str(exc))
        return

    db = SessionLocal()

    try:
        result = (
            ensure_web_repliker_registry(
                db
            )
        )

        print(
            "=== Catálogo Web Replikers ==="
        )

        print(
            f"Propietario interno: "
            f"{ECOSYSTEM_OWNER_EMAIL}"
        )

        print(
            f"Owner creado: "
            f"{result.owner_created}"
        )

        print(
            f"Replikers creados: "
            f"{result.replikers_created}"
        )

        print(
            f"Replikers actualizados: "
            f"{result.replikers_updated}"
        )

        print(
            f"Skills creadas: "
            f"{result.skills_created}"
        )

        print(
            f"Skills actualizadas: "
            f"{result.skills_updated}"
        )

        print(
            f"Skills eliminadas: "
            f"{result.skills_removed}"
        )

        print(
            f"Total Replikers oficiales: "
            f"{result.total_replikers}"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
