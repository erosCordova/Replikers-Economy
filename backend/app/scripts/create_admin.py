from getpass import getpass

from sqlalchemy import select

from app.auth.security import (
    hash_password,
)
from app.database.migrations import (
    DatabaseMigrationError,
    assert_database_migrations_current,
)
from app.database.session import (
    SessionLocal,
    engine,
)
from app.models.user import User


def main():
    try:
        assert_database_migrations_current(
            engine
        )

    except DatabaseMigrationError as exc:
        print(
            "No se puede crear "
            "el administrador."
        )

        print(
            str(exc)
        )

        return

    print(
        "=== Crear administrador ==="
    )

    full_name = input(
        "Nombre del administrador: "
    ).strip()

    email = input(
        "Correo del administrador: "
    ).strip().lower()

    if not full_name:
        print(
            "El nombre es obligatorio."
        )
        return

    if not email:
        print(
            "El correo es obligatorio."
        )
        return

    password = getpass(
        "Contraseña: "
    )

    password_confirm = getpass(
        "Confirmar contraseña: "
    )

    if len(password) < 8:
        print(
            "La contraseña debe tener "
            "al menos 8 caracteres."
        )
        return

    if password != password_confirm:
        print(
            "Las contraseñas no coinciden."
        )
        return

    db = SessionLocal()

    try:
        existing = db.scalar(
            select(User)
            .where(
                User.email == email
            )
        )

        if existing:
            print(
                "Ya existe un usuario "
                "con ese correo."
            )
            return

        admin = User(
            full_name=full_name,
            email=email,
            password_hash=
                hash_password(
                    password
                ),
            role="admin",
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print()
        print(
            "Administrador creado "
            "correctamente."
        )

        print(
            f"Correo: {email}"
        )

        print(
            "Rol: admin"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
